from xarray import Dataset
from .canvases import ImageIntentCanvas, PlotIntentCanvas


class Intent:
    def __init__(self, name="", category=""):
        self._name = name
        self._category = category

    @property
    def name(self):
        return self._name

    @property
    def category(self):
        return self._category


# class MatplotlibImageCanvas(ImageIntentCanvas):
#     def render(self, ...):
#         matplotlib.imshow(...)


class ImageIntent(Intent):
    canvas = ImageIntentCanvas
    # TODO: move toward environment dict (see below)
    # canvas = {"qt": ImageIntentCanvas, "matplotlib": matplotlib.imshow} # canvasmanager will know how to map to these keys

    def __init__(self, image, *args, **kwargs):
        super(ImageIntent, self).__init__(*args, **kwargs)
        self.image = image


class PlotIntent(Intent):
    # Model that we can pull intents (EnsembleModel)
    # View interprets these intents by init'ng canvas into its display
    canvas = PlotIntentCanvas

    def __init__(self, x: Dataset, y: Dataset, *args, **kwargs):
        super(PlotIntent, self).__init__(*args, **kwargs)
        self.x = x
        self.y = y

    @property
    def name(self):
        return self.x.name + ", " + self.y.name
