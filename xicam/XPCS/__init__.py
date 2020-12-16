from xicam.gui.plugins.ensembleguiplugin import EnsembleGUIPlugin
from xicam.plugins import GUILayout, GUIPlugin, manager as pluginmanager
from . import ingestors


class XPCS(EnsembleGUIPlugin):
    name = 'XPCS'

    def __init__(self):
        super(XPCS, self).__init__()
        saxsplugin = pluginmanager.get_plugin_by_name('SAXS', 'GUIPlugin')

        self.stages = saxsplugin.stages

        self.appendCatalog = saxsplugin.appendCatalog
