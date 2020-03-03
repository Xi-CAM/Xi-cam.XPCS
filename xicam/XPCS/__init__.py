from xicam.plugins import GUILayout, GUIPlugin, manager as pluginmanager

class XPCS(GUIPlugin):
    name = 'XPCS'

    def __init__(self):
        saxsplugin = pluginmanager.get_plugin_by_name('SAXS', 'GUIPlugin')

        self.stages = saxsplugin.stages['Correlate']

        self.appendCatalog = saxsplugin.appendCatalog
        self.appendHeader = saxsplugin.appendHeader

        super(XPCS, self).__init__()
