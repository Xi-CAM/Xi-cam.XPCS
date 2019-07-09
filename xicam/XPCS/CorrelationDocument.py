import time
import event_model as em
from jsonschema.exceptions import ValidationError

from typing import List
import os
from xicam.core.data import NonDBHeader


# TODO -- should this be internal XPCS private class?
class CorrelationDocument(object):

    def __init__(self, header: NonDBHeader, name):
        # Create start document with 'uid', 'time'
        self.run_start = em.compose_run()
        # Add custom fields to the start documents
        #   'correlation_name'
        #   'images' : List of image names used in the correlation
        self.run_start.start_doc['correlation_name'] = name
        # TODO -- need to handle having unique correlation names?
        #      TODO -- can this be solved by using combination of name + time in model?
        self.run_start.start_doc['images'] = self._extractImages(header)
        self._data_keys = {
            'image_series': {
                'source': '<image_series>',
                'dtype': 'string',
                'shape': []
            },
            'g2': {
                'source': '<>',
                'dtype': 'number',
                'shape': []
            },
            # 'geometry' : {
            #     'source': '<device name>',
            #     'dtype': 'number'
            # },
            # 'computed_parameters': {
            #     'source': '<image series>',
            #     'dtype': 'number'
            # },
            'name' : {
                'source': '<name>',
                'dtype': 'string',
                'shape': []
            }
        }
        self._name = 'primary'
        self.descriptor = None
        self.createDescriptor()  # Type: em.ComposeDescriptorBundle
        self._events = []
        self.run_stop = None # TODO -- should this be updated w/in XPCS.process?
        #TODO -- how to store N images?

    def _extractImages(self, header: NonDBHeader) -> List[str]:
        return [os.path.splitext(os.path.basename(path))[0] for path in header.startdoc['paths']]

    def setShape(self, data_key, shape):
        if self._data_keys.get(data_key):
            self._data_keys[data_key]['shape'] = shape

    def createDescriptor(self):
        try:
            self.descriptor = self.run_start.compose_descriptor(name=self._name, data_keys=self._data_keys)
        except ValidationError:
            # TODO handle validation errors
            raise ValidationError

    def createEvent(self, name='', image_series='', g2=None):
        # There should only be one event in a XPCS correlation (when the algorithm is run)
        # TODO -- image_data not acquired properly
        timestamp = time.time()
        data = dict()
        data['name'] = name
        # data['geometry'] = geometry
        data['image_series'] = image_series
        data['g2'] = g2
        # data['plots'] = plots
        # data['computed_parameters'] = computed_parameters
        timestamps = dict()
        for key in data:
            timestamps[key] = timestamp
        self._events.append(self.descriptor.compose_event(data=data, timestamps=timestamps))

    def createStop(self):
        self.run_stop = self.run_start.compose_stop()

    def data(self, data_key):
        for event in self._events:
            # TODO do we need to check that the event has a 'data' key (think event_model.compose_event does this for us)
            event_data = event['data']
            if data_key in event_data:
                yield event_data[data_key]
