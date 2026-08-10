"""Public guide and rate-limited, email-only contact views."""

import hashlib
import smtplib

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .forms import ContactForm


def _client_key(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    address = forwarded.split(',', 1)[0].strip() or request.META.get('REMOTE_ADDR', 'unknown')
    digest = hashlib.sha256(address.encode('utf-8')).hexdigest()[:24]
    return f'public-contact-rate:{digest}'


@never_cache
def guide_view(request):
    return render(request, 'public/guide.html', {'contact_email': settings.CONTACT_EMAIL})


@never_cache
def legal_view(request):
    return render(request, 'public/legal.html', {'contact_email': settings.CONTACT_EMAIL})


@never_cache
def contact_view(request):
    form = ContactForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        # Silently accept bot-filled honeypots without sending anything.
        if form.cleaned_data['website']:
            messages.success(request, 'Your message has been accepted.')
            return redirect('contact')

        rate_key = _client_key(request)
        sent_count = int(cache.get(rate_key, 0))
        if sent_count >= settings.CONTACT_RATE_LIMIT_PER_HOUR:
            form.add_error(None, 'Too many messages were sent from this network. Try again later.')
        elif (
            settings.EMAIL_BACKEND.endswith('smtp.EmailBackend')
            and (not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD)
        ):
            form.add_error(
                None,
                f'Email delivery is not configured yet. Contact {settings.CONTACT_EMAIL} directly.',
            )
        else:
            sender_name = form.cleaned_data['name'].replace('\r', ' ').replace('\n', ' ').strip()
            reply_email = form.cleaned_data['reply_email']
            body = (
                'A visitor contacted you through Personal Learning OS.\n\n'
                f'Name: {sender_name}\n'
                f'Email: {reply_email}\n'
                f'Received: {timezone.localtime():%Y-%m-%d %H:%M:%S %Z}\n\n'
                f'{form.cleaned_data["message"]}\n'
            )
            email = EmailMessage(
                subject=f'[Learning OS contact] {sender_name}',
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.CONTACT_EMAIL],
                reply_to=[reply_email],
            )
            try:
                email.send(fail_silently=False)
            except (OSError, smtplib.SMTPException):
                form.add_error(
                    None,
                    f'Email delivery is temporarily unavailable. Contact {settings.CONTACT_EMAIL} directly.',
                )
            else:
                cache.set(rate_key, sent_count + 1, timeout=60 * 60)
                messages.success(request, 'Your message was sent to the administrator.')
                return redirect('contact')

    return render(request, 'public/contact.html', {
        'form': form,
        'contact_email': settings.CONTACT_EMAIL,
    })
