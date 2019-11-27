from xicam.plugins import GUILayout, GUIPlugin, manager as pluginmanager

class XPCS(GUIPlugin):
    name = 'XPCS'

    def __init__(self):
        saxsplugin = pluginmanager.getPluginByName('SAXS', 'GUIPlugin').plugin_object

        self.stages = saxsplugin.stages['Correlate']

        self.appendCatalog = saxsplugin.appendCatalog
        self.appendHeader = saxsplugin.appendHeader

        super(XPCS, self).__init__()
