import time
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
g2_roi_names_key = 'entry/data/masks/mask/mask_names'
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
                     'entry/XPCS/data/masks': {'type': 'linked',
                                               'stream': 'primary',
                                               'location': 'event',
                                               'field': 'masks'},
                     g2_roi_names_key: {'type': 'linked',
                                         'stream': 'primary',
                                         'location': 'event',
                                         'field': 'g2_roi_names'}, }

                }]


def ingest_nxXPCS(paths):
    assert len(paths) == 1
    path = paths[0]

    h5 = h5py.File(path, 'r')

    g2 = h5[g2_projection_key]
    g2_errors = h5[g2_error_projection_key]
    # masks = h5['entry/XPCS/data/masks']
    # rois = h5['entry/XPCS/data/rois']
    g2_roi_names = list(map(lambda bytestring: bytestring.decode('UTF-8'), h5[g2_roi_names_key][()]))

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
                                     'shape': (g2.shape[0],)},
                       'g2_roi_names': {'source': source,
                                        'dtype': 'string',
                                        'shape': tuple()}}

    frame_stream_bundle = run_bundle.compose_descriptor(data_keys=frame_data_keys,
                                                        name='primary',
                                                        # configuration=_metadata(path)
                                                        )
    yield 'descriptor', frame_stream_bundle.descriptor_doc

    num_events = g2.shape[1]

    for i in range(num_events):
        t = time.time()
        yield 'event', frame_stream_bundle.compose_event(data={'g2_curves': g2[:, i],
                                                               'g2_error_bars': g2_errors[:, i],
                                                               'g2_roi_names': g2_roi_names[i]},
                                                         timestamps={'g2_curves': t,
                                                                     'g2_error_bars': t,
                                                                     'g2_roi_names': t})

    yield 'stop', run_bundle.compose_stop()
