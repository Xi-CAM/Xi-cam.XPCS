import time
import numpy as np
import h5py
import event_model
from pathlib import Path
import dask.array as da
from xarray import DataArray
import mimetypes

print("MIMETYPE ADDED")
mimetypes.add_type('application/x-hdf5', '.nxs')

g2_projection_key = 'entry/XPCS/data/g2'
g2_error_projection_key = 'entry/XPCS/data/g2_errors'
# TODO: is masks really a good term? Rings? Intervalls? (ROIs?)
g2_mask_projection_key = 'entry/XPCS/data/masks'
g2_rois_projection_key = 'entry/XPCS/data/rois'

SAXS_1D_I_projection_key = 'entry/SAXS_1D/data/I'
SAXS_1D_Q_projection_key = 'entry/SAXS_1D/data/Q'
SAXS_2D_I_projection_key = 'entry/SAXS_2D/data/I'
SAXS_2D_mask_projection_key = 'entry/SAXS_2D/data/mask'

# TODO: add var for rest of projection keys

projections = [{'name': 'nxXPCS',
                'version': '0.1.0',
                'projection':
                    {g2_projection_key: {'type': 'linked',
                                         'stream': 'primary',
                                         'location': 'event',
                                         'field': 'g2_curves'},
                     g2_error_projection_key: {'type': 'linked',
                                               'stream': 'primary',
                                               'location': 'event',
                                               'field': 'g2_error_bars'},
                     g2_mask_projection_key: {'type': 'linked',
                                               'stream': 'primary',
                                               'location': 'event',
                                               'field': 'masks'},
                     g2_rois_projection_key: {'type': 'linked',
                                              'stream': 'primary',
                                              'location': 'event',
                                              'field': 'rois'},
                     SAXS_1D_I_projection_key: {'type': 'linked',
                                                'stream': 'primary',
                                                'location': 'event',
                                                'field': 'I'},
                     SAXS_1D_Q_projection_key: {'type': 'linked',
                                                'stream': 'primary',
                                                'location': 'event',
                                                'field': 'q'},
                     SAXS_2D_I_projection_key: {'type': 'linked',
                                                'stream': 'primary',
                                                'location': 'event',
                                                'field': 'I_2D'},
                     SAXS_2D_mask_projection_key: {'type': 'linked',
                                                'stream': 'primary',
                                                'location': 'event',
                                                'field': 'pixel_mask'}
                     }

                }]


def ingest_nxXPCS(paths):
    assert len(paths) == 1
    path = paths[0]

    h5 = h5py.File(path, 'r')

    g2 = h5['entry/XPCS/data/g2']
    # NOTE: g2.shape[0] =  number of g2 values in a single g2 curve
    #       g2.shape[1] =  number of g2 curves
    g2_errors = h5['entry/XPCS/data/g2_errors']
    masks = h5['entry/XPCS/data/masks']
    rois = h5['entry/XPCS/data/rois']
    SAXS_1D_I = h5['entry/SAXS_1D/data/I'][()]
    SAXS_1D_Q = h5['entry/SAXS_1D/data/Q'][()]
    SAXS_1D = np.column_stack((SAXS_1D_I, SAXS_1D_Q))
    SAXS_2D_I = da.from_array(h5['entry/SAXS_2D/data/I'])
    SAXS_2D_mask = h5['entry/SAXS_2D/data/mask'][()]

    # create xarrays
    SAXS_1D = DataArray(SAXS_1D_I, dims=('q'), coords=(SAXS_1D_Q))

    # Compose run start
    run_bundle = event_model.compose_run()  # type: event_model.ComposeRunBundle
    start_doc = run_bundle.start_doc
    start_doc["sample_name"] = Path(paths[0]).resolve().stem
    start_doc["projections"] = projections
    yield 'start', start_doc

    # Compose descriptor
    source = 'nxXPCS'
    frame_data_keys = {'g2_curves': {'source': source,
                                     'dtype': 'array',
                                     'dims': ('g2',),
                                     'shape': (g2.shape[0],)},
                       'g2_error_bars': {'source': source,
                                         'dtype': 'array',
                                         'dims': ('g2_errors',),
                                         'shape': (g2_errors.shape[0],)},
                       'SAXS_1D': {'source': source,
                             'dtype': 'array',
                             'dims': ('SAXS_1D',),
                             'shape': (SAXS_1D.shape,)},
                       # 'Q': {'source': source,
                       #       'dtype': 'array',
                       #       'dims': ('SAXS_1D_I',),
                       #       'shape': (SAXS_1D_Q.shape[0],)},
                       'I_2D': {'source': source,
                             'dtype': 'array',
                             'dims': ('SAXS_2D_I',),
                             'shape': (SAXS_2D_I.shape,)},
                       'pixel_mask': {'source': source,
                             'dtype': 'array',
                             'dims': ('SAXS_2D_mask',),
                             'shape': (SAXS_2D_mask.shape,)},
                       }

    frame_stream_bundle = run_bundle.compose_descriptor(data_keys=frame_data_keys,
                                                        name='primary',
                                                        # configuration=_metadata(path)
                                                        )
    yield 'descriptor', frame_stream_bundle.descriptor_doc

    t = time.time()
    yield 'event', frame_stream_bundle.compose_event(data={'SAXS_1D': SAXS_1D},
                                                     timestamps={'SAXS_1D': t})
    num_events = g2.shape[1]
    for i in range(num_events):
        t = time.time()
        yield 'event', frame_stream_bundle.compose_event(data={'g2_curves': g2[:, i], 'g2_error_bars': g2_errors[:, i]},
                                                         timestamps={'g2_curves': t, 'g2_error_bars': t})

    yield 'stop', run_bundle.compose_stop()
