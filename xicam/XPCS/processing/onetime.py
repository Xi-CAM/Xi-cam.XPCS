from xicam.plugins import ProcessingPlugin, Input, Output, InOut
import skbeam.core.correlation as corr
import numpy as np


class OneTimeCorrelation(ProcessingPlugin):
    data = Input(description='Array of two or more dimensions.', type=np.ndarray)

    labels = Input(description="""Labeled array of the same shape as the image stack.
        Each ROI is represented by sequential integers starting at one.  For
        example, if you have four ROIs, they must be labeled 1, 2, 3,
        4. Background is labeled as 0""", type=np.array)
    num_levels = Input(description="""how many generations of downsampling to perform, i.e., the depth of
        the binomial tree of averaged frames""", type=int, default=7)
    num_bufs = Input(description="""must be even
        maximum lag step to compute in each generation of downsampling""", type=int, default=8)

    g2 = Output(description="""the normalized correlation shape is (len(lag_steps), num_rois)""", type=np.array)

    def evaluate(self):
        self.g2.value, lag_steps = corr.multi_tau_auto_corr(self.num_levels.value,
                                                            self.num_bufs.value,
                                                            self.labels.value.astype(np.int),
                                                            np.array(self.data.value))
        # seems to only work with ints
