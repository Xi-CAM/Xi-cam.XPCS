import time
import numpy as np
import h5py
import event_model
from pathlib import Path
import dask.array as da
from xarray import DataArray
import mimetypes

mimetypes.add_type('application/x-hdf5', '.nxs')
mimetypes.add_type('application/x-hdf5', '.nx')

g2_projection_key = '/entry/XPCS/data/g2'
tau_projection_key = '/entry/XPCS/data/tau'
g2_error_projection_key = '/entry/XPCS/data/g2_stderr'
dqlist_key = '/entry/XPCS/instrument/mask/dqlist'

# XPCS_mask_names_key = '/entry/XPCS/data/masks'

SAXS_2D_I_projection_key = '/entry/SAXS_2D/data/I'
SAXS_1D_I_projection_key = '/entry/SAXS_1D/data/I'
SAXS_1D_Q_projection_key = '/entry/SAXS_1D/data/Q'
SAXS_1D_I_partial_projection_key = '/entry/SAXS_1D/data/I_partial'

raw_data_projection_key = '/entry/data/raw'
# TODO: add var for rest of projection keys

projections = [{'name': 'nxXPCS',
                'version': '0.1.0',
                'projection':
                    {g2_projection_key: {'type': 'linked',
                                         'stream': 'primary',
                                         'location': 'event',
                                         'field': 'g2_curves'},
                     tau_projection_key: {'type': 'linked',
                                          'stream': 'primary',
                                          'location': 'event',
                                          'field': 'g2_tau'},
                     g2_error_projection_key: {'type': 'linked',
                                               'stream': 'primary',
                                               'location': 'event',
                                               'field': 'g2_error_bars'},
                     # XPCS_mask_names_key: {'type': 'linked',
                     #                           'stream': 'primary',
                     #                           'location': 'event',
                     #                           'field': 'masks'},
                     dqlist_key: {'type': 'linked',
                                         'stream': 'primary',
                                         'location': 'event',
                                         'field': 'g2_dqlist'},
                     SAXS_2D_I_projection_key: {'type': 'linked',
                                                'stream': 'SAXS_2D',
                                                'location': 'event',
                                                'field': 'SAXS_2D'},
                     SAXS_1D_I_projection_key: {'type': 'linked',
                                                'stream': 'SAXS_1D',
                                                'location': 'event',
                                                'field': 'SAXS_1D_I'},
                     SAXS_1D_Q_projection_key: {'type': 'linked',
                                                'stream': 'SAXS_1D',
                                                'location': 'event',
                                                'field': 'SAXS_1D_Q'},
                     SAXS_1D_I_partial_projection_key: {'type': 'linked',
                                                'stream': 'SAXS_1D_I_partial',
                                                'location': 'event',
                                                'field': 'SAXS_1D_I_partial'},
                     raw_data_projection_key: {'type': 'linked',
                                                'stream': 'raw',
                                                'location': 'event',
                                                'field': 'raw'},

                     }

                }]


def ingest_nxXPCS(paths):
    assert len(paths) == 1
    path = paths[0]

    h5 = h5py.File(path, 'r')

    # Compose run start
    run_bundle = event_model.compose_run()  # type: event_model.ComposeRunBundle
    start_doc = run_bundle.start_doc
    start_doc["sample_name"] = Path(paths[0]).resolve().stem
    start_doc["projections"] = projections
    yield 'start', start_doc
    source = 'nxXPCS'

    #gather data from h5 file
    g2 = h5[g2_projection_key]
    tau = h5[tau_projection_key][0]
    g2_errors = h5[g2_error_projection_key]
    # masks = h5['entry/XPCS/data/masks']
    # rois = h5['entry/XPCS/data/rois']
    dqlist = h5[dqlist_key]
    # dqlist = list(map(lambda bytestring: bytestring.decode('UTF-8'), h5[dqlist_key][()]))
    SAXS_2D_I = da.from_array(h5[SAXS_2D_I_projection_key])
    SAXS_1D_I = h5[SAXS_1D_I_projection_key][0]
    SAXS_1D_Q = h5[SAXS_1D_Q_projection_key][0]
    SAXS_1D_I_partial = da.from_array(h5[SAXS_1D_I_partial_projection_key])

    try:
        raw_data = h5[raw_data_projection_key]
        raw_data_keys = {'raw': {'source': source,
                                 'dtype': 'array',
                                 'dims': ('N', 'q_x', 'q_y'),
                                 'shape': raw_data.shape}}
        raw_data_stream_bundle = run_bundle.compose_descriptor(data_keys=raw_data_keys,
                                                               name='raw'
                                                               # configuration=_metadata(path)
                                                               )
        yield 'descriptor', raw_data_stream_bundle.descriptor_doc
        t = time.time()
        yield 'event', raw_data_stream_bundle.compose_event(data={'raw': raw_data},
                                                            timestamps={'raw': t})
    except KeyError:
        pass


    g2_data_keys = {'g2_curves': {'source': source,
                              'dtype': 'array',
                              'dims': ('g2',),
                              'shape': (g2.shape[0],)},
                    'g2_tau': {'source': source,
                               'dtype': 'array',
                               'dims': ('tau',),
                               'shape': tau.shape},
                    'g2_error_bars': {'source': source,
                                      'dtype': 'array',
                                      'dims': ('g2_errors',),
                                      'shape': (g2.shape[0],)},
                    'g2_dqlist': {'source': source,
                               'dtype': 'array',
                               'dims': ('dqlist',),
                                  #TODO check what shape is needed here?
                               'shape': (dqlist.shape[0],)},
                    }

    SAXS_2D_keys = {'SAXS_2D': {'source': source,
                             'dtype': 'array',
                             'dims': ('q_x', 'q_y'),
                             'shape': SAXS_2D_I.shape}}

    SAXS_1D_keys = {'SAXS_1D_I': {'source': source,
                                  'dtype': 'array',
                                  'dims': ('I',),
                                  'shape': SAXS_1D_I.shape},
                    'SAXS_1D_Q': {'source': source,
                                  'dtype': 'array',
                                  'dims': ('Q',),
                                  'shape': SAXS_1D_Q.shape},
                    }

    SAXS_1D_I_partial_keys = {'SAXS_1D_I_partial': {'source': source,
                             'dtype': 'array',
                             'dims': ('N', 'I'),
                             'shape': SAXS_1D_I_partial.shape},
                    }


    #TODO: How to add multiple streams?
    g2_stream_bundle = run_bundle.compose_descriptor(data_keys=g2_data_keys,
                                                        name='primary'
                                                        # configuration=_metadata(path)
                                                        )
    SAXS_2D_stream_bundle = run_bundle.compose_descriptor(data_keys=SAXS_2D_keys,
                                                        name='SAXS_2D'
                                                        # configuration=_metadata(path)
                                                        )
    SAXS_1D_stream_bundle = run_bundle.compose_descriptor(data_keys=SAXS_1D_keys,
                                                        name='SAXS_1D'
                                                        # configuration=_metadata(path)
                                                        )
    SAXS_1D_I_partial_stream_bundle = run_bundle.compose_descriptor(data_keys=SAXS_1D_I_partial_keys,
                                                        name='SAXS_1D_I_partial'
                                                        # configuration=_metadata(path)
                                                        )


    yield 'descriptor', g2_stream_bundle.descriptor_doc
    yield 'descriptor', SAXS_2D_stream_bundle.descriptor_doc
    yield 'descriptor', SAXS_1D_stream_bundle.descriptor_doc
    yield 'descriptor', SAXS_1D_I_partial_stream_bundle.descriptor_doc


    num_events = g2.shape[1]
    for i in range(num_events):
        t = time.time()
        yield 'event', g2_stream_bundle.compose_event(data={'g2_curves': g2[:, i],
                                                             'g2_tau': tau,
                                                             'g2_error_bars': g2_errors[:, i],
                                                             'g2_dqlist': dqlist[:, i]
                                                            },
                                                      timestamps={'g2_curves': t,
                                                                  'g2_tau': t,
                                                                  'g2_error_bars': t,
                                                                  'g2_dqlist': t
                                                                  })
    t = time.time()
    yield 'event', SAXS_2D_stream_bundle.compose_event(data={'SAXS_2D': SAXS_2D_I},
                                                       timestamps={'SAXS_2D': t})
    t = time.time()
    yield 'event', SAXS_1D_stream_bundle.compose_event(data={'SAXS_1D_I': SAXS_1D_I,
                                                             'SAXS_1D_Q': SAXS_1D_Q},
                                                       timestamps={'SAXS_1D_I': t,
                                                                   'SAXS_1D_Q': t})
    # num_curves = SAXS_1D_I_partial.shape[1]
    # for i in range(num_curves):
    t = time.time()
    yield 'event', SAXS_1D_I_partial_stream_bundle.compose_event(data={'SAXS_1D_I_partial': SAXS_1D_I_partial},
                                                                 timestamps={'SAXS_1D_I_partial': t})

    yield 'stop', run_bundle.compose_stop()
