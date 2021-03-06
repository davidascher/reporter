from django.conf import settings
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.utils.hashcompat import md5_constructor

import jingo
from view_cache_utils import cache_page_with_prefix

from feedback import stats
from feedback.models import Term

from .client import Client, SearchError
from .forms import ReporterSearchForm


def search_view_cache_key(request):
    """Generate a cache key for a search view based on its GET parameters."""
    return md5_constructor(str(request.GET)).hexdigest()


@cache_page_with_prefix(settings.CACHE_DEFAULT_PERIOD, search_view_cache_key)
def index(request):
    form = ReporterSearchForm(request.GET)
    data = {'form': form}
    pp = settings.SEARCH_PERPAGE

    if form.is_valid():
        query = form.cleaned_data.get('q', '')
        search_opts = form.cleaned_data
        page = search_opts.get('page', 1)

        try:
            c = Client()
            opinions = c.query(query, **search_opts)
        except SearchError, e:
            return jingo.render(request, 'search/unavailable.html',
                                {'search_error': e}, status=500)

    else:
        query = ''
        opinions = None

    if opinions:
        pager = Paginator(opinions, pp)
        # If page request (9999) is out of range, deliver last page of results.
        try:
            data['page'] = pager.page(page)
        except (EmptyPage, InvalidPage):
            data['page'] = pager.page(pager.num_pages)

        data['opinions'] = data['page'].object_list
        data['sent'] = stats.sentiment(qs=opinions)
        data['demo'] = stats.demographics(qs=opinions)

        frequent_terms = Term.objects.frequent(
            opinions=opinions)[:settings.TRENDS_COUNT]
        data['terms'] = stats.frequent_terms(qs=frequent_terms)

    return jingo.render(request, 'search/search.html', data)
