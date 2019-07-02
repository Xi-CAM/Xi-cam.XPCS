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
        self.run_start['correlation_name'] = name
        # TODO -- need to handle having unique correlation names?
        #      TODO -- can this be solved by using combination of name + time in model?
        self.run_start['images'] = self._extractImages(header)

        self.event_descriptor = None
        self._data_keys = {
            'image': {
                'source': '<image_name>',
                'dtype': 'number'
            },
            'geometry' : {
                'source': '<device name>',
                'dtype': 'number'
            },
            'computed_parameters': {
                'source': '<image series>',
                'dtype': 'number'
            },
            'name' : {
                'source': '<name>',
                'dtype': 'string',
            }
        }
        self._name = 'primary'
        self._streams = {}
        self._event_counter = {self._name: 0}
        self.events = [] # this might not be needed, since the correlation document only needs 1 event

        self.run_stop = None # TODO -- should this be updated w/in XPCS.process?

        #TODO -- how to store N images?

    def _extractImages(self, header: NonDBHeader) -> List[str]:
        return [os.path.splitext(os.path.basename(path))[0] for path in header.startdoc['paths']]

    def setShape(self, shape):
        # Accept shape as nd.array.shape, then convert to list?
        self._data_keys['shape'] = shape

    def setDescriptor(self):
        # 'shape' must first be defined in the data keys
        if not 'shape' in self._data_keys:
            raise

        try:
            self.event_descriptor = em.compose_descriptor(
                start=self.run_start.start,
                event_counter=self._event_counter,
                streams=self._streams,
                name=self._name,
                data_keys=self._data_keys)
        except ValidationError:
            pass

    def createEvent(self, name, geometry, image_series, plots, computed_parameters):
        # There should only be one event in a XPCS correlation (when the algorithm is run)
        # TODO -- image_data not acquired properly
        timestamp = time.time()
        data = {}
        data['name'] = name
        data['geometry'] = geometry
        data['image_series'] = image_series
        data['plots'] = plots
        data['computed_parameters'] = computed_parameters
        timestamps = {}
        for key in data:
            timestamps[key] = timestamp
        self.events.append(
            em.compose_event(
                descriptor={'name': self._name,
                            'uid': self.event_descriptor.descriptor_doc['uid'],
                            'data_keys': self._data_keys},
                event_counter=self._event_counter,
                timestamps=timestamps,
                data=data))

        self._createStop()

    def createStop(self):
        em.compose_stop()
