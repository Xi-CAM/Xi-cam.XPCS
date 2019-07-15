from xicam.plugins import ProcessingPlugin
from ..processing.onetime import OneTimeCorrelation
from ..processing.fitting import Fitting
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
        self.onetime = OneTimeCorrelation()
        self.addProcess(self.onetime)
        self.fitting = Fitting()
        self.addProcess(self.fitting)
        self.autoConnectAll()

    @property
    def parameters(self):
        children = []
        parameter = self.onetime.parameter
        # parameter.removeChild(parameter.child('data'))
        children += self.onetime.parameter.children()
        children += self.fitting.parameter.children()
        parameters = []
        white_list = ['num_levels', 'num_bufs', 'beta']
        for child in children:
            if child.name() in white_list:
                parameters.append(child)
        return parameters


class FourierAutocorrelator(XPCSWorkflow):
    name = 'Fourier Correlation'

    def __init__(self):
        super(FourierAutocorrelator, self).__init__()
        fourier = FourierCorrelation()
        self.addProcess(fourier)

