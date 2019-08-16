import numpy as np
from skbeam.core.correlation import two_time_corr

from xicam.plugins import Input, Output, ProcessingPlugin


class TwoTimeCorrelation(ProcessingPlugin):
    labels = Input(description=('labeled array of the same shape as the image stack;'
                                'each ROI is represented by a distinct label (i.e., integer)'),
                   type=np.ndarray,
                   visible=False)
    data = Input(description='dimensions are: (rr, cc), iterable of 2D arrays',
                 type=np.ndarray,
                 visible=False)
    num_frames = Input(description='number of images to use default is number of images',
                       type=int)
    # TODO -- how to handle runtime default?
    num_bufs = Input(description='maximum lag step to compute in each generation of downsampling (must be even)',
                     type=int,
                     default=1)
    num_levels = Input(description=('how many generations of downsampling to perform, '
                                    'i.e., the depth of the binomial tree of averaged frames default is one'),
                       type=int,
                       default=1)

    g2 = Output(description='the normalized correlation shape is (num_rois, len(lag_steps), len(lag_steps))',
                type=np.ndarray)
    lag_steps = Output(description='the times at which the correlation was computed',
                       type=np.ndarray)

    def evaluate(self):
        if self.num_frames.value == 0:
            self.num_frames.value = len(self.data.value)

        corr = two_time_corr(self.labels.value.astype(np.int),
                             np.asarray(self.data.value),
                             self.num_frames.value,
                             self.num_bufs.value,
                             self.num_levels.value)
        self.g2.value = corr.g2
        self.lag_steps.value = corr.lag_steps
