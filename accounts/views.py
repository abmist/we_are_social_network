from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required

from accounts.forms import UserRegistrationForm, UserLoginForm
from django.core.urlresolvers import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.context_processors import csrf
from django.conf import settings
import datetime
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from models import User
import stripe
import arrow
import json
from django.http import Http404, HttpResponseRedirect

from forms import UpdateProfileForm



stripe.api_key = settings.STRIPE_SECRET


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                customer = stripe.Customer.create(

                    email=form.cleaned_data['email'],
                    card=form.cleaned_data['stripe_id'],
                    plan='REG_MONTHLY',
                )
            except stripe.error.CardError, e:
                messages.error(request, "Your card was declined!")

            if customer:
                user = form.save()
                user.stripe_id = customer.id
                user.subscription_end = arrow.now().replace(weeks=+4).datetime
                user.save()

                user = auth.authenticate(email=request.POST.get('email'), password=request.POST.get('password1'))

                if 'user_profile_picture' in request.FILES:
                    profile.user_profile_picture = request.FILES['user_profile_picture']

                if user:
                    auth.login(request, user)
                    messages.success(request, "You have successfully registered")
                    return redirect(reverse('profile'))

                else:
                    messages.error(request, "We were unable to log you in at this time")
            else:
                messages.error(request, "We were unable to take payment from the card provided")
    else:
        today = datetime.date.today()
        form = UserRegistrationForm(initial={'expiry_month': today.month, 'expiry_year': today.year})

    args = {'form': form, 'publishable': settings.STRIPE_PUBLISHABLE}
    args.update(csrf(request))
    return render(request, 'register.html', args)


@login_required(login_url='/accounts/login/')
def cancel_subscription(request):
    try:
        customer = stripe.Customer.retrieve(request.user.stripe_id)

        customer.cancel_subscription(at_period_end=True)
    except Exception, e:
        messages.error(request, e)

    return redirect('profile')


@csrf_exempt
def subscriptions_webhook(request):
    event_json = json.loads(request.body)

    # Verify the event by fetching it from Stripe

    try:
        # firstly verify this is a real event generated by Stripe.com
        # commented out for testing - uncomment when live
        # event = stripe.Event.retrieve(event_json['object']['id'])

        cust = event_json['object']['customer']
        paid = event_json['object']['paid']
        user = User.objects.get(stripe_id=cust)

        if user and paid:
            user.subscription_end = arrow.now().replace(weeks=+4).datetime  # add 4 weeks from now
            user.save()

    except stripe.InvalidRequestError, e:
        return HttpResponse(status=404)

    return HttpResponse(status=200)


@login_required(login_url='/login/')
def profile(request):
    return render(request, 'profile.html')


def login(request):
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            user = auth.authenticate(email=request.POST.get('email'),
                                     password=request.POST.get('password'))

            if user is not None:
                auth.login(request, user)
                messages.error(request, "")
                return redirect(reverse('profile'))
            else:
                form.add_error(None, "Your email or password was not recognised")

    else:
        form = UserLoginForm()

    args = {'form': form}
    args.update(csrf(request))
    return render(request, 'login.html', args)


def logout(request):
    auth.logout(request)
    messages.success(request, '')
    return render(request, 'index.html')

#End


@login_required
def get_users(request):
    return render(request, "members.html", {'user_list': User.objects.all()})

@login_required
def get_user_details(request, user_id):
    try:
        user = User.objects.filter(pk=user_id)
    except User.DoesNotExist:
        raise Http404("Noooo")
    return render(request, "member_detail.html", {'details': user })


# Just a test. I'll delete it too.
def update_profile(request):
    args = {}

    if request.method == 'POST':
        update_profile_form = UpdateProfileForm(request.POST, instance=request.user)

        if update_profile_form.is_valid():
            update_profile_form.save()
            return HttpResponseRedirect(reverse('profile'))

    else:
        update_profile_form = UpdateProfileForm()

    args['update_profile_form'] = update_profile_form
    return render(request, 'update_profile.html', args)