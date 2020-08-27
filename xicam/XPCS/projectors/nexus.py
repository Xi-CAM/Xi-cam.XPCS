from databroker.core import BlueskyRun
from ..ingestors import g2_projection_key, g2_error_projection_key


# XICAM projectors should be returning "Hints", where a Hint contains the (lazy) data
def project_nxXPCS(run_catalog: BlueskyRun):
    projection = next(
        filter(lambda projection: projection['name'] == 'nxXPCS', run_catalog.metadata['start']['projections']))

    stream = projection['projection'][g2_projection_key]['stream']
    g2_field = projection['projection'][g2_projection_key]['field']
    g2_error_field = projection['projection'][g2_error_projection_key]['field']
    g2 = getattr(run_catalog, stream).to_dask().rename({g2_field: g2_projection_key,
                                                        g2_error_field: g2_error_projection_key})
    return g2
    # ImageHint{xarray}

    # return (g2/g2_err, masks, roi)
