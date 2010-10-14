# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.txt.
from django.shortcuts import render_to_response
from django.template import RequestContext

from lizard_fewsjdbc.models import JdbcSource
from lizard_map.daterange import current_start_end_dates
from lizard_map.daterange import DateRangeForm
from lizard_map.workspace import WorkspaceManager


def homepage(request,
             javascript_click_handler='popup_click_handler',
             javascript_hover_handler='popup_hover_handler',
             template="lizard_fewsjdbc/homepage.html"):
    """
    Overview of all Jdbc Sources.
    """

    workspace_manager = WorkspaceManager(request)
    workspaces = workspace_manager.load_or_create()
    date_range_form = DateRangeForm(
        current_start_end_dates(request, for_form=True))

    return render_to_response(
        template,
        {'javascript_hover_handler': javascript_hover_handler,
         'javascript_click_handler': javascript_click_handler,
         'date_range_form': date_range_form,
         'jdbc_sources': JdbcSource.objects.all(),
         'workspaces': workspaces},
        context_instance=RequestContext(request))


def jdbc_source(request,
                jdbc_source_slug,
                javascript_click_handler='popup_click_handler',
                javascript_hover_handler='popup_hover_handler',
                template="lizard_fewsjdbc/jdbc_source.html"):
    """
    FEWS JDBC browser view. Filter list and parameter list is cached.
    """

    workspace_manager = WorkspaceManager(request)
    workspaces = workspace_manager.load_or_create()
    date_range_form = DateRangeForm(
        current_start_end_dates(request, for_form=True))
    filter_id = request.GET.get('filter_id', None)
    jdbc_source = JdbcSource.objects.get(slug=jdbc_source_slug)

    filter_tree = jdbc_source.get_filter_tree()

    # If the page is called with option filter_id, add parameter variables.
    fews_parameters = None
    fews_filter = None

    if filter_id is not None:
        named_parameters = jdbc_source.get_named_parameters(filter_id)

        if named_parameters:
            for named_parameter in named_parameters:
                fews_parameters = [
                    {'name': named_parameter['parameter'],
                     'id': named_parameter['parameterid']}]
            fews_filter = {'name': named_parameters[0]['name'],
                           'id': filter_id}

    return render_to_response(
        template,
        {'javascript_hover_handler': javascript_hover_handler,
         'javascript_click_handler': javascript_click_handler,
         'date_range_form': date_range_form,
         'tree_items': filter_tree,
         'parameters': fews_parameters,
         'filter': fews_filter,
         'jdbc_source_slug': jdbc_source_slug,
         'workspaces': workspaces},
        context_instance=RequestContext(request))
