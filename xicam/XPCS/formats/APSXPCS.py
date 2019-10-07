import time
from pathlib import Path

import event_model
import h5py
from intake_bluesky.in_memory import BlueskyInMemoryCatalog

from xicam.core.msg import WARNING, notifyMessage
from xicam.plugins.datahandlerplugin import DataHandlerPlugin


# TODO : DataHandlerPlugin deprecated for CatalogPlugin
class APSXPCS(DataHandlerPlugin):
    """
    Handles ingestion of APS XPCS .hdf files.

    Internally, these .hdf files will hold a reference to a .bin image file,
    which will be loaded as well.
    """
    name = 'APSXPCS'
    DEFAULT_EXTENTIONS = ['.hdf', '.h5']

    def __init__(self, path):
        super(APSXPCS, self).__init__()
        self.path = path

    def __call__(self, data_key='', slc=0, **kwargs):
        # TODO -- change to show image data once image data is being ingested
        h5 = h5py.File(self.path, 'r')
        if data_key == 'norm-0-g2':
            return h5['exchange'][data_key][:,:,slc].transpose()
        return h5['exchange'][data_key][slc]

    @classmethod
    def ingest(cls, paths):
        updated_doc = dict()
        # TODO -- update for multiple paths (pending dbheader interface)
        if len(paths) > 1:
            paths = [paths[0]]
            message = 'Opening multiple already-processed data sources is not yet supported. '
            message += f'Opening the first image, {paths[0]}...'
            notifyMessage(message, level=WARNING)
            print(f'PATHS: {paths}')
        for name, doc in cls._createDocument(paths):
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

    @classmethod
    def _createDocument(cls, paths):
        # TODO -- add frames after being able to read in bin images
        for path in paths:
            timestamp = time.time()

            run_bundle = event_model.compose_run()
            yield 'start', run_bundle.start_doc

            source = 'APS XPCS'  # TODO -- find embedded source info?
            frame_data_keys = {'frame': {'source': source, 'dtype': 'number', 'shape': []}}
            frame_stream_name = 'primary'
            frame_stream_bundle = run_bundle.compose_descriptor(data_keys=frame_data_keys,
                                                                name=frame_stream_name)
            yield 'descriptor', frame_stream_bundle.descriptor_doc

            # 'name' is used as an identifier for results when plotting
            reduced_data_keys = {
                'g2': {'source': source, 'dtype': 'number', 'shape': [61]},
                'g2_err': {'source': source, 'dtype': 'number', 'shape': [61]},
                'lag_steps': {'source': source, 'dtype': 'number', 'shape': [61]},
                'fit_curve': {'source': source, 'dtype': 'number', 'shape': [61]},
                'name': {'source': source, 'dtype': 'string', 'shape': []}
            }
            result_stream_name = 'reduced'
            reduced_stream_bundle = run_bundle.compose_descriptor(data_keys=reduced_data_keys,
                                                                  name=result_stream_name)
            yield 'descriptor', reduced_stream_bundle.descriptor_doc

            h5 = h5py.File(path, 'r')
            frames = []
            # TODO -- use the processed data timestamp?
            for frame in frames:
                yield 'event', frame_stream_bundle.compose_event(data={'frame', frame},
                                                                 timestamps={'frame', timestamp})

            lag_steps = h5['exchange']['tau'][()]
            roi_list = h5['xpcs']['dqlist'][()].squeeze()
            for g2, err, fit_curve, roi in zip(h5['exchange']['norm-0-g2'][()].T,
                                    h5['exchange']['norm-0-stderr'][()].T,
                                    h5['exchange']['g2avgFIT1'][()].T,
                                    roi_list):
                yield 'event', reduced_stream_bundle.compose_event(
                    data={'g2': g2,
                          'g2_err': err,
                          'lag_steps': lag_steps,
                          'fit_curve': fit_curve,
                          'name': f'q = {roi:.3g}'},
                    # TODO -- timestamps from h5?
                    timestamps={'g2': timestamp,
                                'g2_err': timestamp,
                                'lag_steps': timestamp,
                                'fit_curve': timestamp,
                                'name': timestamp})

            yield 'stop', run_bundle.compose_stop()
