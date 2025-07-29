import logging
from pathlib import Path
from time import sleep
from typing import Union, cast
from urllib.parse import urlparse

import requests
from unidecode import unidecode

from proyect_x.ditu.api.dash import Dash, Representation
from proyect_x.ditu.schemas.simple_schedule import SimpleSchedule

from .api.channel import DituChannel
from .api.schedule import DituSchedule

HEADERS = {
    "Host": "d1kkcfjl98zuzm.cloudfront.net",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "okhttp/4.12.0",
}
logger = logging.getLogger(__name__)


def _build_output_path(self, schedule: SimpleSchedule) -> Path:
    title_slug = unidecode(schedule.title.strip()).lower().replace(" ", ".")
    start = schedule.start_time.strftime("%Y_%m_%d.%I_%M.%p")
    folder_name = (
        f"{title_slug}.capitulo.{schedule.episode_number}.ditu.live.1080p.{start}"
    )
    return Path("output/test") / folder_name


def _select_best_representation(self, reps: list, key: str) -> dict:
    return sorted(reps, key=lambda x: x.get(key) or 0, reverse=True)[0]


def _download_representation_segments(self, rep: dict, base_output: Path):
    mime, _ = rep["mimetype"].split("/")
    init_path = self._build_segment_path(rep["init_url"], base_output, mime)
    self._download_file_if_needed(rep["init_url"], init_path)

    for segment_url in rep["segments"]:
        segment_path = self._build_segment_path(segment_url, base_output, mime)
        self._download_file_if_needed(segment_url, segment_path, retry_on_fail=True)


def _build_segment_path(self, url: str, base_output: Path, mime: str) -> Path:
    path = urlparse(url).path
    return base_output / mime / Path(path).name


def _download_file_if_needed(self, url: str, path: Path, retry_on_fail: bool = False):
    if path.exists():
        return
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
        logger.info(f"✅ Descargado: {path}")
    except Exception as e:
        logger.error(f"❌ Error al descargar: {path}: {e}")
        if retry_on_fail:
            sleep(7)


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

    def _build_output_path(
        self, schedule: SimpleSchedule, base_output: Path, video_rep: Representation
    ) -> Path:
        title_slug = unidecode(schedule.title.strip()).lower().replace(" ", ".")
        start = schedule.start_time.strftime("%Y_%m_%d.%I_%M.%p")
        width = video_rep["width"]
        folder_name = f"{title_slug}.capitulo.{schedule.episode_number}.ditu.live.{width}p.{start}"
        return base_output / folder_name

    def _select_best_representation(self, reps: list, key: str) -> Representation:
        return sorted(reps, key=lambda x: x.get(key) or 0, reverse=True)[0]

    def _download_representation_segments(self, rep: Representation, base_output: Path):
        path = urlparse(rep["init_url"]).path
        init_path = base_output / Path(path).name
        self._download_file_if_needed(rep["init_url"], init_path)

        for segment_url in rep["segments"]:
            path = urlparse(segment_url).path
            segment_path = base_output / Path(path).name
            self._download_file_if_needed(segment_url, segment_path)

    def _download_file_if_needed(self, url: str, path: Path):
        if path.exists():
            return
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
            logger.info(f"✅ Descargado: {path}")
        except Exception as e:
            logger.error(f"❌ Error al descargar: {path}: {e}")

    def capture_schedule(
        self, schedule: SimpleSchedule, output_dir: Union[str, Path]
    ) -> Path:
        url = self.dash.get_live_channel_manifest(schedule.channel_id)
        output_dir = Path(output_dir) if isinstance(output_dir, str) else output_dir

        while True:
            mpd = self.dash.fetch_mpd(url)
            reps = self.dash.parse_mpd_representations(mpd)

            video_rep = self._select_best_representation(reps, key="width")

            output = self._build_output_path(schedule, output_dir, video_rep)

            audio_rep = self._select_best_representation(reps, key="sampling_rate")

            self._download_representation_segments(video_rep, output / "video")
            self._download_representation_segments(audio_rep, output / "audio")

            sleep(5)  # TODO: reemplazar por el valor recomendado del manifest
        return output
