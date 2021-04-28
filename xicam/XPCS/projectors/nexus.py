from typing import List
import numpy as np
from databroker.core import BlueskyRun
from xicam.core.data.bluesky_utils import display_name
from xicam.SAXS.intents import SAXSImageIntent
from xicam.core.data import ProjectionNotFound
from xicam.core.intents import Intent, PlotIntent, ImageIntent, ErrorBarIntent
from ..ingestors import g2_projection_key, g2_error_projection_key, tau_projection_key, dqlist_key, \
                        SAXS_2D_I_projection_key, SAXS_1D_I_projection_key, SAXS_1D_Q_projection_key, \
                        SAXS_1D_I_partial_projection_key, raw_data_projection_key


def project_nxXPCS(run_catalog: BlueskyRun) -> List[Intent]:
    projection = next(
        filter(lambda projection: projection['name'] == 'nxXPCS', run_catalog.metadata['start'].get('projections', [])), None)

    if not projection:
        raise ProjectionNotFound("Could not find projection named 'nxXPCS'.")

    catalog_name = display_name(run_catalog).split(" ")[0]
    intents_list = []

    # TODO: project masks, rois
    #gather fields and streams from projections
    g2_stream = projection['projection'][g2_projection_key]['stream']
    g2_field = projection['projection'][g2_projection_key]['field']
    tau_field = projection['projection'][tau_projection_key]['field']
    g2_error_field = projection['projection'][g2_error_projection_key]['field']
    dqlist_field = projection['projection'][dqlist_key]['field']
    # Use singly-sourced key name
    g2 = getattr(run_catalog, g2_stream).to_dask().rename({g2_field: g2_projection_key,
                                                           tau_field: tau_projection_key,
                                                           g2_error_field: g2_error_projection_key,
                                                           dqlist_field: dqlist_key
                                                           })

    SAXS_2D_I_stream = projection['projection'][SAXS_2D_I_projection_key]['stream']
    SAXS_2D_I_field = projection['projection'][SAXS_2D_I_projection_key]['field']
    SAXS_2D_I = getattr(run_catalog, SAXS_2D_I_stream).to_dask().\
                        rename({SAXS_2D_I_field: SAXS_2D_I_projection_key})[SAXS_2D_I_projection_key]

    SAXS_1D_I_stream = projection['projection'][SAXS_1D_I_projection_key]['stream']
    SAXS_1D_I_field = projection['projection'][SAXS_1D_I_projection_key]['field']
    SAXS_1D_Q_stream = projection['projection'][SAXS_1D_Q_projection_key]['stream']
    SAXS_1D_Q_field = projection['projection'][SAXS_1D_Q_projection_key]['field']
    SAXS_1D_I = getattr(run_catalog, SAXS_1D_I_stream).to_dask().rename({SAXS_1D_I_field: SAXS_1D_I_projection_key})
    SAXS_1D_Q = getattr(run_catalog, SAXS_1D_Q_stream).to_dask().rename({SAXS_1D_Q_field: SAXS_1D_Q_projection_key})
    SAXS_1D_I = np.squeeze(SAXS_1D_I)
    SAXS_1D_Q = np.squeeze(SAXS_1D_Q)

    SAXS_1D_I_partial_stream = projection['projection'][SAXS_1D_I_partial_projection_key]['stream']
    SAXS_1D_I_partial_field = projection['projection'][SAXS_1D_I_partial_projection_key]['field']
    SAXS_1D_I_partial = getattr(run_catalog, SAXS_1D_I_partial_stream).to_dask().\
                                rename({SAXS_1D_I_partial_field: SAXS_1D_I_partial_projection_key})[SAXS_1D_I_partial_projection_key]
    SAXS_1D_I_partial = np.squeeze(SAXS_1D_I_partial)

    try:
        raw_data_stream = projection['projection'][raw_data_projection_key]['stream']
        raw_data_field = projection['projection'][raw_data_projection_key]['field']
        raw_data = getattr(run_catalog, raw_data_stream).to_dask().rename({raw_data_field: raw_data_projection_key})[raw_data_projection_key]
        raw_data = np.squeeze(raw_data)
        intents_list.append(SAXSImageIntent(image=raw_data, name="Raw frame {}".format(catalog_name), mixins=("SAXSImageIntentBlend",)), )
    except:
        print('No raw data available')


    for i in range(len(g2[g2_projection_key])):
        g2_curve = g2[g2_projection_key][i]
        tau = g2[tau_projection_key][i]
        error_height = g2[g2_error_projection_key][i]
        dqlist = g2[dqlist_key]
        # g2_roi_name = g2[g2_roi_names_key].values[i]  # FIXME: talk to Dan about how to properly define string data keys
        intents_list.append(ErrorBarIntent(name=f"q={dqlist[i].values[0]:.3}",
                            canvas_name='g₂ vs. τ',
                            match_key='g₂ vs. τ',
                            y=g2_curve,
                            x=tau,
                            xLogMode=True,
                            height=error_height,
                            labels={"left": "g₂", "bottom": "τ"},
                            mixins=["ToggleSymbols"]))


    #intents_list.append(ImageIntent(image=face(True), item_name='SAXS 2D'),)
    intents_list.append(SAXSImageIntent(image=SAXS_2D_I, name="AVG frame {}".format(catalog_name), mixins=("SAXSImageIntentBlend",)), )
    intents_list.append(PlotIntent(y=SAXS_1D_I[SAXS_1D_I_projection_key],
                        x=SAXS_1D_Q[SAXS_1D_Q_projection_key],
                        labels={"left": "I", "bottom": "Q"},
                        name='AVG SAXS curve {}'.format(catalog_name)))


    intents_list.append(PlotIntent(y=SAXS_1D_I_partial, x=SAXS_1D_Q[SAXS_1D_Q_projection_key],
                        labels = {"left": "I", "bottom": "Q"},
                        name='Stability Plot {}'.format(catalog_name)))
    return intents_list
    # TODO: additionally return intents for masks, rois
