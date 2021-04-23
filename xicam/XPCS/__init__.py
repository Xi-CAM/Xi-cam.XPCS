from xicam.SAXS.stages import CorrelationStage
from xicam.XPCS.projectors.nexus import project_nxXPCS

from . import ingestors


class XPCS(CorrelationStage):
    name = 'XPCS'

    def __init__(self):
        super(XPCS, self).__init__()
        # Add in appropriate projectors here
        # Add in first position so that it has priority
        self._projectors.insert(0, project_nxXPCS)
