from xicam.plugins import ProcessingPlugin, Input, Output, InputOutput
import numpy as np
import skbeam.core.correlation as corr
from astropy.modeling import fitting, Fittable1DModel, Parameter


class ScatteringModel(Fittable1DModel):
    inputs = ('lag_steps',)
    outputs = ('g2',)

    relaxation_rate = Parameter()

    def __init__(self, beta, **kwargs):
        self.beta = beta
        super(ScatteringModel, self).__init__(**kwargs)

    def evaluate(self, lag_steps, relaxation_rate):
        return corr.auto_corr_scat_factor(lag_steps, self.beta, relaxation_rate)


class FitScatteringFactor(ProcessingPlugin):
    name = "Fit Scattering Factor"
    g2 = InputOutput(description="normalized intensity-intensity time autocorrelation", type=np.array)
    lag_steps = InputOutput(description="delay time", type=np.array, default=[])
    beta = Input(description="optical contrast (speckle contrast), a sample-independent beamline parameter",
                  type=float, name="speckle contrast", default=0.1)
    relaxation_rate = Output(description="relaxation time associated with the samples dynamics",
                             type=float)

    def evaluate(self):
        relaxation_rate = 0.5  # Some initial guess
        model = ScatteringModel(relaxation_rate=relaxation_rate, beta=self.beta.value)
        # model(relaxation_rate)

        fitter = fitting.LevMarLSQFitter()
        fit = fitter(model, self.lag_steps.value, self.g2.value)
        print(fitter.fit_info['message'])
        print(fitter.fit_info)
        self.relaxation_rate.value = fit.relaxation_rate.value
