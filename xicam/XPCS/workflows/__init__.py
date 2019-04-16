from ..processing.onetime import OneTimeCorrelation
from xicam.core.execution import Workflow


class XPCSWorkflow(Workflow):
    ...


class TwoTime(XPCSWorkflow):
    ...


class OneTime(XPCSWorkflow):
    def __init__(self):
        super(OneTime, self).__init__(name='One Time Correlation')
        onetime = OneTimeCorrelation()
        self.addProcess(onetime)
