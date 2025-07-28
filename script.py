from proyect_x.ditu.ditu import DituStream

ditu = DituStream()


response = ditu.get_schedule("desafio")
print(response)


# dash = Dash()
# url = dash.get_live_channel_manifest(43)
# mpd = dash.fetch_mpd(url)
# qualities = dash._extract_qualities(mpd)
# print(qualities)
