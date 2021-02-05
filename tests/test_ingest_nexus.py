from pathlib import Path
from xicam.core.data import load_header
from xicam.plugins import manager as plugin_manager

from xicam.XPCS.ingestors import ingest_nxXPCS
from xicam.XPCS.projectors.nexus import project_nxXPCS

#TODO use githublfs to store (test)data

f = 'B009_Aerogel_1mm_025C_att1_Lq0_001_0001-10000.nxs'
p = Path('.') / f


def test_ingest_nexus(path=p):
    docs = list(ingest_nxXPCS([path]))
    #TODO check document keys even if multiple events per document

    # expected_doc_keys = ["start", "descriptor", "event", "stop"]
    # for i, doc in enumerate(docs):
    #     assert doc[0] == expected_doc_keys[i]

    expected_projection_keys = ["entry/XPCS/data/g2",
                                "entry/XPCS/data/tau",
                                "entry/XPCS/data/g2_errors",
                                "entry/data/masks/mask/mask_names",
                                'entry/XPCS/data/masks',
                                "entry/SAXS_2D/data/I",
                                "entry/SAXS_1D/data/I",
                                "entry/SAXS_1D/data/Q",
                                "entry/data/raw"]

    start_doc = docs[0][-1]
    for i in start_doc["projections"][0]["projection"].keys():
        assert i in expected_projection_keys




# def test_project_nexus():
#
#     cat = load_header([p])
#     g2_arr = project_nxXPCS(cat)
#     print(g2_arr)