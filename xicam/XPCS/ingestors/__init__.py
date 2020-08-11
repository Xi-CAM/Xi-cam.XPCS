import time
import h5py
import event_model
from pathlib import Path
import dask.array as da
from xarray import DataArray

projections = [{'name': 'nxXPCS',
                'version': '0.1.0',
                'projection':
                    {'entry/XPCS/data/g2': {'type': 'linked',
                                            'stream': 'primary',
                                            'location': 'event',
                                            'field': 'g2'},
                     'entry/XPCS/data/g2_errors': {'type': 'linked',
                                                   'stream': 'primary',
                                                   'location': 'event',
                                                   'field': 'g2_errors'},
                     'entry/XPCS/data/masks': {'type': 'linked',
                                               'stream': 'primary',
                                               'location': 'event',
                                               'field': 'masks'},
                     'entry/XPCS/data/rois': {'type': 'linked',
                                              'stream': 'primary',
                                              'location': 'event',
                                              'field': 'g2'}, }

                }]


def ingest_nxXPCS(paths):
    assert len(paths) == 1
    path = paths[0]

    h5 = h5py.File(path, 'r')

    g2 = h5['entry/XPCS/data/g2']
    g2_errors = h5['entry/XPCS/data/g2_errors']
    masks = h5['entry/XPCS/data/masks']
    rois = h5['entry/XPCS/data/rois']

    # Compose run start
    run_bundle = event_model.compose_run()  # type: event_model.ComposeRunBundle
    start_doc = run_bundle.start_doc
    start_doc["sample_name"] = Path(paths[0]).resolve().stem
    start_doc["projections"] = projections
    yield 'start', start_doc

    # Compose descriptor
    source = 'nxXPCS'
    frame_data_keys = {'g2': {'source': source,
                              'dtype': 'array',
                              'dims': ('g2',),
                              'shape': (g2.shape[0],)},
                       'g2_errors': {'source': source,
                                     'dtype': 'array',
                                     'dims': ('g2_errors',),
                                     'shape': (g2.shape[0],)}
                       }

    frame_stream_bundle = run_bundle.compose_descriptor(data_keys=frame_data_keys,
                                                        name='primary',
                                                        # configuration=_metadata(path)
                                                        )
    yield 'descriptor', frame_stream_bundle.descriptor_doc

    num_events = g2.shape[1]

    for i in range(num_events):
        t = time.time()
        yield 'event', frame_stream_bundle.compose_event(data={'g2': g2[:, i], 'g2_errors': g2_errors[:, i]},
                                                         timestamps={'g2': t, 'g2_errors': t})

    yield 'stop', run_bundle.compose_stop()
