# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.txt.
from django import http
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import simplejson as json
from django.views.generic import View, CreateView
from django.views.generic.edit import DeleteView
from lizard_fewsjdbc.forms import ThresholdUpdateForm, ThresholdCreateForm

from lizard_fewsjdbc.models import JdbcSource, Threshold
from lizard_map.views import AppView, AdapterMixin

import logging
from lizard_map.adapter import adapter_layer_arguments, adapter_serialize
from lizard_map.models import WorkspaceEditItem
from lizard_fewsjdbc.utils import format_number

logger = logging.getLogger(__name__)


class HomepageView(AppView):
    """Class based view for the fewsjdbc homepage."""

    template_name = 'lizard_fewsjdbc/homepage.html'

    def jdbc_sources(self):
        return JdbcSource.objects.all()


class JdbcSourceView(AppView):
    """Class based view for the fewsjdbc filters/parameters blocks
    contained in a given jdbc source."""

    template_name = "lizard_fewsjdbc/jdbc_source.html"
    filter_url_name = "lizard_fewsjdbc.jdbc_source"
    adapter_class = "adapter_fewsjdbc"
    edit_link = '/admin/lizard_fewsjdbc/'

    def get(self, request, *args, **kwargs):
        """This method is overridden in order to get at the GET parameters."""

        self.jdbc_source_slug = kwargs.get('jdbc_source_slug', '')
        self.jdbc_source = get_object_or_404(JdbcSource,
                                             slug=self.jdbc_source_slug)
        self.filter_id = request.GET.get('filter_id', None)
        self.ignore_cache = request.GET.get('ignore_cache', False)

        return super(JdbcSourceView, self).get(request, *args, **kwargs)

    def tree_items(self):
        """If there is no filter chosen yet, show the filter tree."""
        if self.filter_id is None:
            return self.jdbc_source.get_filter_tree(
                self.filter_url_name,
                ignore_cache=self.ignore_cache)
        else:
            return None

    def parameters(self):
        """If there is a filter chosen, show its parameters."""
        if not hasattr(self, '_parameters') and self.filter_id is not None:
            named_parameters = self.jdbc_source.get_named_parameters(
                self.filter_id, ignore_cache=self.ignore_cache)

            if named_parameters:
                self._parameters = [
                    {'name': '%s' % named_parameter['parameter'],
                     'workspace_name': ('%s (%s, %s)' %
                                        (named_parameter['parameter'],
                                        named_parameter['filter_name'],
                                        self.jdbc_source_slug)),
                     'id': named_parameter['parameterid'],
                     'filter_id': named_parameter['filter_id'],
                     'filter_name': named_parameter['filter_name']}
                    for named_parameter in named_parameters]
        if hasattr(self, '_parameters'):
            return self._parameters

    def filter(self):
        """Return the current filter."""
        if not hasattr(self, '_filter') and self.filter_id is not None:
            named_parameters = self.jdbc_source.get_named_parameters(
                self.filter_id, ignore_cache=self.ignore_cache)

            if named_parameters:
                self._filter = {'name': named_parameters[0]['filter_name'],
                                'id': self.filter_id}
        if hasattr(self, '_filter'):
            return self._filter

    def crumbs(self):
        crumbs = super(JdbcSourceView, self).crumbs()

        if self.jdbc_source_slug:
            # Sometimes people link from the app screens directly to
            # some JDBC source. In that case, it shouldn't be part of
            # the breadcrumbs.  If they don't, people first saw the
            # HomepageView and chose a source there, in that case we
            # should show it.
            #
            # We can tell the difference because our super() search
            # for an app screen that was used to get to this point. If
            # the source slug is part of self.url_after_app, then the
            # source slug wasn't used in the app's url.

            if self.jdbc_source_slug in self.url_after_app:
                crumbs += [{
                    'url': reverse('lizard_fewsjdbc.jdbc_source',
                                   kwargs={'jdbc_source_slug':
                                           self.jdbc_source_slug}),
                    'description': self.jdbc_source.name,
                    'title': self.jdbc_source.name}]

            # If there is a filter selected, we can add it to the URL too
            f = self.filter()
            if f:
                crumbs += [{
                    'url': ('%s?filter_id=%s' %
                            (reverse(
                                'lizard_fewsjdbc.jdbc_source',
                                kwargs={'jdbc_source_slug':
                                        self.jdbc_source_slug}),
                             f['id'])),
                    'description': f['name'],
                    'title': f['name']}]

        return crumbs


class ThresholdsView(AdapterMixin, AppView):
    """View for showing/adding/updating/deleting thresholds."""
    template_name = "lizard_fewsjdbc/thresholds/overview.html"

    def get_context_data(self, **kwargs):
        context = super(ThresholdsView, self).get_context_data(**kwargs)
        identifier = self.identifier()
        location = identifier["location"]
        workspace_item_id = self.request.GET.get("workspace_item_id")
        workspace_item = WorkspaceEditItem.objects.get(pk=workspace_item_id)
        layer_arguments = adapter_layer_arguments(
            workspace_item.adapter_layer_json)
        parameter_id = layer_arguments['parameter']
        filter_id = layer_arguments['filter']
        # get the threshold belonging to the location, filter and parameter ids
        thresholds = Threshold.objects.filter(
            location_id=location, filter_id=filter_id,
            parameter_id=parameter_id)
        context['location'] = location
        context['thresholds'] = thresholds
        adapter = workspace_item.adapter
        context['adapter'] = adapter
        image_graph_url = workspace_item.url(
            "lizard_map_adapter_image", [identifier])
        context['image_graph_url'] = image_graph_url
        flot_graph_data_url = workspace_item.url(
            "lizard_map_adapter_flot_graph_data", [identifier])
        context['flot_graph_data_url'] = flot_graph_data_url
        context['form'] = ThresholdCreateForm(initial={
            'workspace_item_id': workspace_item_id, 'location_id': location})
        return context

    def get(self, request, *args, **kwargs):
        return super(ThresholdsView, self).get(request, *args, **kwargs)

    def crumbs(self):
        crumbs = super(ThresholdsView, self).crumbs()
        return crumbs


class JSONResponseMixin(object):
    def render_to_response(self, context):
        "Returns a JSON response containing 'context' as payload"
        return self.get_json_response(self.convert_context_to_json(context))

    def get_json_response(self, content, **httpresponse_kwargs):
        "Construct an `HttpResponse` object."
        return http.HttpResponse(content, content_type='application/json',
                                 **httpresponse_kwargs)

    def convert_context_to_json(self, context):
        "Convert the context dictionary into a JSON object"
        # Note: This is *EXTREMELY* naive; in reality, you'll need
        # to do much more complex handling to ensure that arbitrary
        # objects -- such as Django model instances or querysets
        # -- can be serialized as JSON.
        return json.dumps(context)


class ThresholdUpdateView(JSONResponseMixin, View):
    """View for updating threshold instances."""
    def post(self, request, *args, **kwargs):
        form = ThresholdUpdateForm(request.POST)
        if form.is_valid():
            id = form.cleaned_data['threshold_id']
            try:
                threshold = Threshold.objects.get(pk=id)
            except ObjectDoesNotExist:
                raise Http404
            else:
                field_name = form.cleaned_data['field_name']
                value = form.cleaned_data['value']
                if field_name == 'value':
                    threshold.value = value
                    threshold.save()
                    return self.render_to_response(
                        format_number(threshold.value))
                elif field_name == 'name':
                    threshold.name = value
                    threshold.save()
                    return self.render_to_response(threshold.name)

        return self.render_to_response({'success': False}, status=403)


class ThresholdDeleteView(DeleteView):
    """View for deleting threshold instances."""
    model = Threshold

    def get(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

    def get_success_url(self):
        workspace_item_id = self.request.GET.get('workspace_item_id')
        location = self.request.GET.get('location')
        identifier = {'location': location}
        identifier_str = adapter_serialize(identifier)
        return '%s?workspace_item_id=%s&identifier=%s' % (
            reverse('lizard_fewsjdbc.thresholds'), workspace_item_id,
            identifier_str)


class ThresholdCreateView(CreateView):
    """View for creating threshold instances."""
    model = Threshold
    form_class = ThresholdCreateForm

    def form_valid(self, form):
        self.workspace_item_id = form.cleaned_data['workspace_item_id']
        self.location = form.cleaned_data['location_id']
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        identifier = {'location': self.location}
        identifier_str = adapter_serialize(identifier)
        return '%s?workspace_item_id=%s&identifier=%s' % (
            reverse('lizard_fewsjdbc.thresholds'), self.workspace_item_id,
            identifier_str)
