from proyect_x.ditu.ditu import Ditu

ditu = Ditu()


response = ditu._get_dash_manifest_for_live_channel(43)
print(response)
