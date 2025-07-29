import logging
from pathlib import Path
from time import sleep
from urllib.parse import urlparse

import requests
from unidecode import unidecode

from proyect_x.ditu.api.dash import Dash
from proyect_x.ditu.schemas.simple_schedule import SimpleSchedule

from .api.channel import DituChannel
from .api.schedule import DituSchedule

HEADERS = {
    "Host": "d1kkcfjl98zuzm.cloudfront.net",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "okhttp/4.12.0",
}
logger = logging.getLogger(__name__)


class DituStream:
    def __init__(self):
        self.schedule = DituSchedule()
        self.channel = DituChannel()
        self.dash = Dash()

    def get_schedule(self, channel) -> list[SimpleSchedule]:
        """Obtiene la programación del dia de un canal de la TV.

        Args:
            channel (int | str): ID o nombre del canal de la TV. Un string hace una busqueda por nombre que no distingue entre mayúsculas y minúsculas ni tildres, mientras un int hace una busqueda por id

        Returns:
            list[SimpleSchedule]: Programación del dia de un canal de la TV.

        """
        is_string = True if isinstance(channel, str) else False
        if is_string:
            return self.schedule.get_schedule_by_name(channel)
        else:
            return self.schedule.get_schedule_by_id(int(channel))

    def capture_schedule(self, schule: SimpleSchedule):
        title = schule.title
        title_slug = unidecode(title.strip()).lower().replace(" ", ".")
        number = schule.episode_number
        start = schule.start_time.strftime("%Y_%m_%d.%I_%M.%p")
        end = schule.end_time.strftime("%I.%M.%p")
        folder_name = f"{title_slug}.capitulo.{number}.ditu.live.1080p.{start}"
        output = Path("output/test") / folder_name

        url = self.dash.get_live_channel_manifest(schule.channel_id)
        while True:
            mpd = self.dash.fetch_mpd(url)
            representations = self.dash.parse_mpd_representations(mpd)

            video_rep = sorted(
                representations, key=lambda x: x.get("width") or 0, reverse=True
            )[0]
            audio_rep = sorted(
                representations,
                key=lambda x: x.get("audioSamplingRate") or 0,
                reverse=True,
            )[0]

            mime, _ = video_rep["mimetype"].split("/")

            init_url = video_rep["init_url"]
            init_urlpased = urlparse(init_url)
            init_file_path = output / mime / Path(init_urlpased.path).name
            if not init_file_path.exists():
                respose = requests.get(init_url, headers=HEADERS)
                respose.raise_for_status()
                init_file_path.parent.mkdir(parents=True, exist_ok=True)
                init_file_path.write_bytes(respose.content)
                logger.info(f"✅ Descargado: {init_file_path}")

            for url in video_rep["segments"]:
                urlpased = urlparse(url)
                file_path = output / mime / Path(urlpased.path).name
                if not file_path.exists():
                    try:
                        respose = requests.get(url, headers=HEADERS)
                        respose.raise_for_status()
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_path.write_bytes(respose.content)
                        logger.info(f"✅ Descargado: {file_path}")
                    except Exception as e:
                        logger.error(f"❌ Error al descargar: {file_path}: {e}")
                        sleep(7)

            init_url = audio_rep["init_url"]
            init_urlpased = urlparse(init_url)
            init_file_path = output / mime / Path(init_urlpased.path).name
            if not init_file_path.exists():
                respose = requests.get(init_url, headers=HEADERS)
                respose.raise_for_status()
                init_file_path.parent.mkdir(parents=True, exist_ok=True)
                init_file_path.write_bytes(respose.content)
                logger.info(f"✅ Descargado: {init_file_path}")

            for url in audio_rep["segments"]:
                urlpased = urlparse(url)
                file_path = output / mime / Path(urlpased.path).name
                if not file_path.exists():
                    try:
                        respose = requests.get(url, headers=HEADERS)
                        respose.raise_for_status()
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_path.write_bytes(respose.content)
                        logger.info(f"✅ Descargado: {file_path}")
                    except Exception as e:
                        logger.error(f"❌ Error al descargar: {file_path}: {e}")
                        sleep(7)
