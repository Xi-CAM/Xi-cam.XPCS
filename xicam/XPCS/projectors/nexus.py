from typing import List
from databroker.core import BlueskyRun
from ..hints import Intent, PlotIntent
from ..ingestors import g2_projection_key, g2_error_projection_key


# TODO: Hint -> Intent

# hint -> xicam.intent
# projection -> xicam.intent
# def discover_intents(BlueskyRun) -> List[Intent] # inspects hints and projections to create intents

def project_nxXPCS(run_catalog: BlueskyRun) -> List[Intent]:
    projection = next(
        filter(lambda projection: projection['name'] == 'nxXPCS', run_catalog.metadata['start']['projections']))

    # TODO: project masks, rois
    stream = projection['projection'][g2_projection_key]['stream']
    g2_field = projection['projection'][g2_projection_key]['field']
    g2_error_field = projection['projection'][g2_error_projection_key]['field']
    # Use singly-sourced key name
    g2 = getattr(run_catalog, stream).to_dask().rename({g2_field: g2_projection_key,
                                                        g2_error_field: g2_error_projection_key})
    return [
        PlotIntent(y=g2_curve, x=g2_curve['g2'], category=g2_projection_key.split("/")[-1])
        for g2_curve in g2[g2_projection_key]
    ]
    # TODO: additionally return hints for masks, rois
