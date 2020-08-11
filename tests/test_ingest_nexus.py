from xicam.XPCS.ingestors import ingest_nxXPCS


def test_ingest_nexus(path='C:\\Users\\LBL\\PycharmProjects\\merged-repo\\Xi-cam.XPCS\\tests\\B009_Aerogel_1mm_025C_att1_Lq0_001_0001-10000.nxs'):
    docs = list(ingest_nxXPCS([path]))

    print(docs)
