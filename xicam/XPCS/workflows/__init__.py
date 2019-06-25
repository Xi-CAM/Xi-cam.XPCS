from ..processing.onetime import OneTimeCorrelation
from ..processing.fourierautocorrelator import FourierCorrelation
from xicam.core.execution import Workflow


class XPCSWorkflow(Workflow):
    ...


class TwoTime(XPCSWorkflow):
    name = '2-Time Correlation'


class OneTime(XPCSWorkflow):
    name = '1-Time Correlation'
    def __init__(self):
        super(OneTime, self).__init__()
        onetime = OneTimeCorrelation()
        self.addProcess(onetime)


class FourierAutocorrelator(XPCSWorkflow):
    name = 'Fourier Correlation'

    def __init__(self):
        super(FourierAutocorrelator, self).__init__()
        fourier = FourierCorrelation()
        self.addProcess(fourier)
