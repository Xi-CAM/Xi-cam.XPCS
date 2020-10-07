from typing import List
from databroker.core import BlueskyRun
from xicam.core.intents import Intent, PlotIntent, ImageIntent
from ..ingestors import g2_projection_key, g2_error_projection_key, g2_roi_names_key
from scipy.misc import face


# TODO: Hint -> Intent

# hint -> xicam.intent
# projection -> xicam.intent
# def discover_intents(BlueskyRun) -> List[Intent] # inspects intents and projections to create intents

def project_nxXPCS(run_catalog: BlueskyRun) -> List[Intent]:
    projection = next(
        filter(lambda projection: projection['name'] == 'nxXPCS', run_catalog.metadata['start']['projections']))

    # TODO: project masks, rois
    stream = projection['projection'][g2_projection_key]['stream']
    g2_field = projection['projection'][g2_projection_key]['field']
    g2_error_field = projection['projection'][g2_error_projection_key]['field']
    g2_roi_name_field = projection['projection'][g2_roi_names_key]['field']

    # Use singly-sourced key name
    g2 = getattr(run_catalog, stream).to_dask().rename({g2_field: g2_projection_key,
                                                        g2_error_field: g2_error_projection_key,
                                                        g2_roi_name_field: g2_roi_names_key})
    # return [
    #     # PlotIntent(y=g2_curve, x=g2_curve['g2'], category=g2_projection_key.split("/")[-1])
    #     # for g2_curve in g2[g2_projection_key]
    #     PlotIntent(y=g2_curve, x=g2_curve['g2'], labels={"left": "g2", "bottom": "tau"})
    #     for g2_curve in g2[g2_projection_key]
    # ]
    l = []
    for i in range(len(g2[g2_projection_key])):
        g2_curve = g2[g2_projection_key][i]
        # g2_roi_name = g2[g2_roi_names_key][i].values[0]
        g2_roi_name = g2[g2_roi_names_key].values[i]  # FIXME: talk to Dan about how to properly define string data keys
        l.append(PlotIntent(item_name=g2_roi_name,
                            y=g2_curve,
                            x=g2_curve['g2'],
                            labels={"left": "g2", "bottom": "tau"}))

    l.append(ImageIntent(image=face(True), item_name='SAXS 2D'),)
    return l
    # TODO: additionally return intents for masks, rois
