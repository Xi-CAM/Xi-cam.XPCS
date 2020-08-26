from databroker.core import BlueskyRun


def project_nxXPCS(run_catalog:BlueskyRun):
    _, projection = next(
        filter(lambda projection: projection['name'] == 'nxXPCS', run_catalog.metadata['start']['projections']))

    stream, field = projection['projection']['entry/XPCS/data/g2']
