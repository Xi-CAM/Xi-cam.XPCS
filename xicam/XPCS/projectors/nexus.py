from typing import List
from databroker.core import BlueskyRun
from ..hints import Hint, PlotHint, ImageHint
from ..ingestors import g2_projection_key, g2_error_projection_key, SAXS_2D_I_projection_key, SAXS_1D_I_projection_key, \
                        SAXS_1D_Q_projection_key


def project_nxXPCS(run_catalog: BlueskyRun) -> List[Hint]:
    projection = next(
        filter(lambda projection: projection['name'] == 'nxXPCS', run_catalog.metadata['start']['projections']))

    # TODO: project masks, rois
    g2_stream = projection['projection'][g2_projection_key]['stream']
    g2_field = projection['projection'][g2_projection_key]['field']
    g2_error_field = projection['projection'][g2_error_projection_key]['field']
    # Use singly-sourced key name
    g2 = getattr(run_catalog, g2_stream).to_dask().rename({g2_field: g2_projection_key,
                                                           g2_error_field: g2_error_projection_key})

    SAXS_2D_I_stream = projection['projection'][SAXS_2D_I_projection_key]['stream']
    SAXS_2D_I_field = projection['projection'][SAXS_2D_I_projection_key]['field']
    SAXS_2D_I = getattr(run_catalog, SAXS_2D_I_stream).to_dask().rename({SAXS_2D_I_field: SAXS_2D_I_projection_key})

    SAXS_1D_I_stream = projection['projection'][SAXS_1D_I_projection_key]['stream']
    SAXS_1D_I_field = projection['projection'][SAXS_1D_I_projection_key]['field']
    SAXS_1D_I = getattr(run_catalog, SAXS_1D_I_stream).to_dask().rename({SAXS_1D_I_field: SAXS_1D_I_projection_key})

    SAXS_1D_Q_stream = projection['projection'][SAXS_1D_Q_projection_key]['stream']
    SAXS_1D_Q_field = projection['projection'][SAXS_1D_Q_projection_key]['field']
    SAXS_1D_Q = getattr(run_catalog, SAXS_1D_Q_stream).to_dask().rename({SAXS_1D_Q_field: SAXS_1D_Q_projection_key})

    return [
        PlotHint(y=g2_curve, x=g2_curve['g2'], category=g2_projection_key.split("/")[-1])
        for g2_curve in g2[g2_projection_key]
    ], ImageHint(image=SAXS_2D_I, category='SAXS_2D'), PlotHint(y=SAXS_1D_I, x=SAXS_1D_Q, category='SAXS_1D')
    # TODO: additionally return hints for masks, rois
