from pathlib import Path
import time

from intake_bluesky.in_memory import BlueskyInMemoryCatalog
import event_model
import h5py
import numpy as np

from xicam.plugins.DataHandlerPlugin import DataHandlerPlugin


class APSXPCS(DataHandlerPlugin):

    name = 'APSXPCS'
    DEFAULT_EXTENTIONS = ['.hdf', '.h5']

    def __init__(self, path):
        super(APSXPCS, self).__init__()
        self.path = path

    def __call__(self, data='', slc=0, **kwargs):
        h5 = h5py.File(self.path, 'r')
        # if slc is None:
        #     return np.zeros((1,100,100)).squeeze()
        if data == 'norm-0-g2':
            return h5['exchange'][data][:,:,slc].transpose()
        return h5['exchange'][data][slc]

    @classmethod
    def ingest(cls, paths):
        # update created document to store list of descriptors and list of events
        updated_doc = dict()
        # TODO -- update for multiple paths
        for name, doc in cls._createDocument(paths):
            #     print(name)
            if name == 'start':
                updated_doc[name] = doc
                # TODO -- should 'sample_name' and 'paths' be something different?
                doc['sample_name'] = cls.title(paths)
                doc['paths'] = paths
            if name == 'descriptor':
                if updated_doc.get('descriptors'):
                    updated_doc['descriptors'].append(doc)
                else:
                    updated_doc['descriptors'] = [doc]
            if name == 'event':
                if updated_doc.get('events'):
                    updated_doc['events'].append(doc)
                else:
                    updated_doc['events'] = [doc]
            if name == 'stop':
                updated_doc[name] = doc

        return updated_doc

    @classmethod
    def title(cls, paths):
        """Returns the title of the start_doc sample_name"""
        # return the file basename w/out extension
        # TODO -- handle multiple paths
        return Path(paths[0]).resolve().stem

    # TODO:
    # -- what should the name be for the non-'primary' descriptor be???
    # -- which data_keys are primary?
    @classmethod
    def _createDocument(cls, paths):

        for path in paths:
            timestamp = time.time()

            run_bundle = event_model.compose_run()
            yield 'start', run_bundle.start_doc
            source = 'APS XPCS'  # TODO -- find embedded source info?
            result_data_keys = {
                'g2': {'source': source, 'dtype': 'number', 'shape': []},
                'lag_steps': {'source': source, 'dtype': 'number', 'shape': []},
            }
            frame_data_keys = {'frame': {'source': source, 'dtype': 'number', 'shape': []}}
            result_stream_name = 'processed'
            frame_stream_name = 'primary'
            result_stream_bundle = run_bundle.compose_descriptor(data_keys=result_data_keys,
                                                                 name=result_stream_name)
            frame_stream_bundle = run_bundle.compose_descriptor(data_keys=frame_data_keys, name=frame_stream_name)

            yield 'descriptor', frame_stream_bundle.descriptor_doc
            yield 'descriptor', result_stream_bundle.descriptor_doc

            h5 = h5py.File(path, 'r')
            frames = []

            # TODO -- use the processed data timestamp?
            for frame in frames:
                yield 'event', frame_stream_bundle.compose_event(data={'frame', frame},
                                                                 timestamps={'frame', timestamp})
            lag_steps = h5['exchange']['tau'][()]
            for g2 in h5['exchange']['norm-0-g2'][()].T:
                yield 'event', result_stream_bundle.compose_event(data={'g2': g2,
                                                                        'lag_steps': lag_steps},
                                                                  # TODO -- timestamps from h5?
                                                                  timestamps={'g2': timestamp,
                                                                              'lag_steps': timestamp})

            yield 'stop', run_bundle.compose_stop()
