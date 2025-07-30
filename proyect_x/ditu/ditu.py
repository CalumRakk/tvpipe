import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Tuple, Union, cast
from urllib.parse import urlparse

import requests
from unidecode import unidecode

from proyect_x.ditu.api.dash import Dash, Representation
from proyect_x.ditu.schemas.simple_schedule import SimpleSchedule

from .api.channel import DituChannel
from .api.schedule import DituSchedule

HEADERS = {
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

    def _build_output_path(
        self, schedule: SimpleSchedule, base_output: Path, video_rep: Representation
    ) -> Path:
        title_slug = unidecode(schedule.title.strip()).lower().replace(" ", ".")
        start = schedule.start_time.strftime("%Y_%m_%d.%I_%M.%p")
        width = video_rep["height"]
        folder_name = f"{title_slug}.capitulo.{schedule.episode_number}.ditu.live.{width}p.{start}"
        return base_output / folder_name

    def _select_best_representation(self, reps: list, key: str) -> Representation:
        return sorted(reps, key=lambda x: x.get(key) or 0, reverse=True)[0]

    def _download_representation_segments(
        self, rep: Representation, base_output: Path
    ) -> Tuple[Path, list[Path]]:
        path = urlparse(rep["init_url"]).path
        init_path = base_output.parent / Path(path).name
        self._download_file_if_needed(rep["init_url"], init_path)

        segmensts = []
        for segment_url in rep["segments"]:
            path = urlparse(segment_url).path
            segment_path = base_output / Path(path).name
            if self._download_file_if_needed(segment_url, segment_path):
                segmensts.append(segment_path)
        return init_path, segmensts

    def _download_file_if_needed(self, url: str, path: Path):
        if path.exists():
            return
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
            logger.info(f"✅ Descargado: {path}")
            return True
        except Exception as e:
            logger.error(f"❌ Error al descargar: {path}: {e}")

    def capture_schedule(self, schedule: SimpleSchedule, output_dir: Union[str, Path]):
        url = self.dash.get_live_channel_manifest(schedule.channel_id)
        output_dir = Path(output_dir) if isinstance(output_dir, str) else output_dir
        result = {
            "video_init": None,
            "video_segments": [],
            "audio_init": None,
            "audio_segments": [],
        }

        while True:
            if datetime.now() > schedule.end_time:
                logger.info(f"Programa terminado: {schedule.title}")
                break
            mpd = self.dash.fetch_mpd(url)
            reps = self.dash.parse_mpd_representations(mpd)

            video_rep = self._select_best_representation(reps, key="height")

            output = self._build_output_path(schedule, output_dir, video_rep)

            audio_rep = self._select_best_representation(reps, key="sampling_rate")

            (
                video_init,
                video_segments,
            ) = self._download_representation_segments(
                video_rep, audio_rep, output / "video"
            )
            result["video_init"] = video_init
            result["video_segments"].extend(video_segments)
            audio_init, audio_segments = self._download_representation_segments(
                audio_rep, output / "audio"
            )
            result["audio_init"] = audio_init
            result["audio_segments"].extend(audio_segments)

            sleep(5)  # TODO: reemplazar por el valor recomendado del manifest

        return result

    def combine_and_merge(self, result: dict):
        folder = result["video_init"].parent
        video_path = folder / ("video_combibed" + result["video_init"].suffix)
        with open(video_path, "wb") as fp:
            fp.write(result["video_init"].read_bytes())
            for segment in result["video_segments"]:
                fp.write(segment.read_bytes())

        audio_path = folder / ("audio_combibed" + result["audio_init"].suffix)
        with open(audio_path, "wb") as fp:
            fp.write(result["audio_init"].read_bytes())
            for segment in result["audio_segments"]:
                fp.write(segment.read())

        output = folder.parent / (folder.name + video_path.suffix)
        cmd = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-shortest",
            str(output),
        ]
        subprocess.run(cmd, check=True)

        shutil.rmtree(str(folder))

        logger.info(f"Archivo final: {output}")
