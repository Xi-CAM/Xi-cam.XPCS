from pathlib import Path
from xicam.core.data import load_header

from xicam.XPCS.ingestors import ingest_nxXPCS
from xicam.XPCS.projectors.nexus import project_nxXPCS

f = 'B009_Aerogel_1mm_025C_att1_Lq0_001_0001-10000.nxs'
p = Path('/home/ihumphrey/Downloads') / f


def test_ingest_nexus(path=p):
    docs = list(ingest_nxXPCS([path]))

    print(docs)


def test_project_nexus():
    cat = load_header([p])
    g2_arr = project_nxXPCS(cat)
    print(g2_arr)