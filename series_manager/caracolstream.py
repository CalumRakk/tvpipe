import logging
from typing import cast

import m3u8
import requests


class CaracolLiveStream:
    url = "https://mdstrm.com/live-stream-playlist/574463697b9817cf0886fc17.m3u8?access_token={access_token}"

    def __init__(self):
        pass

    def get_access_token(self):
        logger = logging.getLogger(__name__)
        API_ACCESS_TOKEN = "https://ms-live.noticiascaracol.com/vide-public-token/ctv"
        params = {
            "id": "574463697b9817cf0886fc17",
        }
        headers = {
            "accept": "*/*",
            "accept-language": "es-ES,es;q=0.8",
            "cache-control": "no-cache",
            "content-type": "application/json",
            "origin": "https://www.caracoltv.com",
            "referer": "https://www.caracoltv.com/",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        }
        logger.info("Getting access token")
        response = requests.get(
            API_ACCESS_TOKEN,
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        json_data = response.json()
        access_token = json_data["access_token"]
        logger.info("Access token: " + access_token)
        return access_token

    def fetch_master(self):
        logger = logging.getLogger(__name__)
        logger.info("Fetching master playlist")

        access_token = self.get_access_token()
        url = self.url.format(access_token=access_token)

        logger.info("URL MASTER: " + url)
        response = requests.get(url)
        response.raise_for_status()
        master = m3u8.loads(response.text)
        logger.info("Master playlist loaded")
        return master

    def fetch_best_playlist(self, include_resolution: bool = False):
        """Fetch a la mejor playlist disponible.

        include_resolution: Si True, incluye la resolución en el objeto playlist. Esto se hace de forma albirtaria al estandard m3u8.
        """
        logger = logging.getLogger(__name__)
        master = self.fetch_master()
        index = 0
        url = cast(str, master.playlists[index].uri)

        logger.info("URL PLAYLIST: " + url)

        response = requests.get(url)
        response.raise_for_status()
        playlist = m3u8.loads(response.text)
        logger.info("Playlist loaded")
        if include_resolution:
            resolution = cast(
                tuple[int, int], master.playlists[0].stream_info.resolution
            )
            resolution_format = f"{resolution[0]}x{resolution[1]}"
            format_note = f"{resolution[1]}p"
            setattr(playlist, "resolution", resolution_format)
            setattr(playlist, "format_note", format_note)
        return playlist
