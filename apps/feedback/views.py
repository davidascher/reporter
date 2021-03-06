from django.conf import settings
from django.core.exceptions import ValidationError
from django import http
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

import jingo
from tower import ugettext as _

from input.urlresolvers import reverse
from .forms import HappyForm, SadForm
from .models import Opinion
from .validators import validate_ua


def enforce_user_agent(f):
    """
    View decorator enforcing feedback from the latest beta users only.

    Can be disabled with settings.ENFORCE_USER_AGENT = False.
    """
    def wrapped(request, *args, **kwargs):
        # Validate User-Agent request header.
        ua = request.META.get('HTTP_USER_AGENT', None)
        try:
            validate_ua(ua)
        except ValidationError:
            if request.method == 'GET':
                return http.HttpResponseRedirect(reverse('feedback.need_beta'))
            else:
                return http.HttpResponseBadRequest(
                    _('User-Agent request header must be set.'))

        # if we made it here, it's a latest beta user
        return f(request, ua=ua, *args, **kwargs)

    return wrapped


@vary_on_headers('User-Agent')
@enforce_user_agent
@cache_page(settings.CACHE_DEFAULT_PERIOD)
def give_feedback(request, ua, positive):
    """Feedback page (positive or negative)."""

    # Positive or negative feedback form?
    Formtype = positive and HappyForm or SadForm

    if request.method == 'POST':
        form = Formtype(request.POST)
        if form.is_valid():
            # Remove URL if checkbox disabled.
            if not form.cleaned_data.get('add_url', False):
                form.cleaned_data['url'] = ''

            # Save to the DB.
            new_opinion = Opinion(
                positive=positive, url=form.cleaned_data.get('url', ''),
                description=form.cleaned_data['description'],
                user_agent=ua)
            new_opinion.save()

            return http.HttpResponseRedirect(reverse('feedback.thanks'))

    else:
        # URL is fed in by the feedback extension.
        url = request.GET.get('url', '')
        form = Formtype(initial={'url': url, 'add_url': False})

    data = {'form': form, 'positive': positive}
    return jingo.render(request, 'feedback/feedback.html', data)
