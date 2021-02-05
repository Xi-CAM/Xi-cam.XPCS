from xarray import Dataset
from pyqtgraph import ImageView, PlotWidget


class Hint:
    def __init__(self, name="", category=""):
        self._name = name
        self._category = category

    @property
    def name(self):
        return self._name

    @property
    def category(self):
        return self._category


class ImageHintCanvas(ImageView):
    def __init__(self, *args, **kwargs):
        super(ImageHintCanvas, self).__init__(*args, **kwargs)

    def render(self, hint):
        self.setImage(hint.image)


class ImageHint(Hint):
    canvas = ImageHintCanvas

    def __init__(self, image, *args, **kwargs):
        super(ImageHint, self).__init__(*args, **kwargs)
        self.image = image


class PlotHintCanvas(PlotWidget):
    def __init__(self, *args, **kwargs):
        super(PlotHintCanvas, self).__init__(*args, **kwargs)

    def render(self, hint):
        self.plot(x=hint.x.compute(), y=hint.y.compute())


class PlotHint(Hint):
    # Model that we can pull hints (EnsembleModel)
    # View interprets these hints by init'ng canvas into its display
    canvas = PlotHintCanvas

    def __init__(self, x: Dataset, y: Dataset, *args, **kwargs):
        super(PlotHint, self).__init__(*args, **kwargs)
        self.x = x
        self.y = y

    @property
    def name(self):
        return self.x.name + ", " + self.y.name