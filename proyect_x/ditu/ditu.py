import logging
import shutil
import subprocess
from datetime import datetime, timedelta
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
            logger.info(f"✅ Descargado: {path.name}")
            return True
        except Exception as e:
            logger.error(f"❌ Error al descargar: {path}: {e}")

    def capture_schedule(self, schedule: SimpleSchedule, output_dir: Union[str, Path]):
        url = self.dash.get_live_channel_manifest(schedule.channel_id)
        output_dir = Path(output_dir) if isinstance(output_dir, str) else output_dir
        result = {
            "video_init": None,
            "video_segments": [],
            "video_represenation_id": None,
            "audio_init": None,
            "audio_segments": [],
            "audio_represenation_id": None,
        }
        representation_id = None
        while True:
            if datetime.now() > schedule.end_time + timedelta(seconds=5):
                logger.info(f"Programa terminado: {schedule.title}")
                break
            mpd = self.dash.fetch_mpd(url)
            reps = self.dash.parse_mpd_representations(mpd)
            if reps[0]["count_periods"] == 1 and (
                representation_id == reps[0]["representation_id"]
                or representation_id is None
            ):
                if representation_id is None:
                    representation_id = reps[0]["representation_id"]

                video_rep = self._select_best_representation(reps, key="height")
                output = self._build_output_path(schedule, output_dir, video_rep)
                audio_rep = self._select_best_representation(reps, key="sampling_rate")

                period_id = video_rep["period_id"]
                v_segment_name = Path(urlparse(video_rep["segments"][0]).path).name
                a_segment_name = Path(urlparse(audio_rep["segments"][0]).path).name
                logger.info(
                    f"📥 Descargando MPD... {period_id} {v_segment_name} {a_segment_name}"
                )

                video_init, video_segments = self._download_representation_segments(
                    video_rep, output / "video"
                )
                audio_init, audio_segments = self._download_representation_segments(
                    audio_rep, output / "audio"
                )
                # -- Actualizar el diccionario con los datos de la captura --
                result["video_init"] = video_init
                result["video_segments"].extend(video_segments)
                result["audio_init"] = audio_init
                result["audio_segments"].extend(audio_segments)
                result["video_represenation_id"] = video_rep["representation_id"]
                result["audio_represenation_id"] = audio_rep["representation_id"]

            sleep(1)  # TODO: reemplazar por el valor recomendado del manifest

        self.cleanup_audio_segments_without_video(result)

        return result

    def cleanup_audio_segments_without_video(self, result: dict):
        """
        Elimina archivos de video y audio cuyos índices no tienen una contraparte en el otro grupo.

        Parámetros:
            result (dict): Diccionario con claves 'video_segments' y 'audio_segments',
                        cada uno conteniendo una lista de rutas a archivos por segmento.
        """
        v_rep_id = result["video_represenation_id"]
        a_rep_id = result["audio_represenation_id"]
        folder_video: Path = result["video_segments"][0].parent
        folder_audio: Path = result["audio_segments"][0].parent

        video_match = f"index_video_{v_rep_id}"
        video_index_map = {
            path: path.name.split(video_match)[-1]
            for path in folder_video.iterdir()
            if video_match in path.name
        }

        audio_match = f"index_audio_{a_rep_id}"
        audio_index_map = {
            path: path.name.split(audio_match)[-1]
            for path in folder_audio.iterdir()
            if audio_match in path.name
        }

        video_indices = set(video_index_map.values())
        audio_indices = set(audio_index_map.values())

        unmatched_audio = [
            path for path, idx in audio_index_map.items() if idx not in video_indices
        ]
        unmatched_video = [
            path for path, idx in video_index_map.items() if idx not in audio_indices
        ]

        for path in unmatched_audio + unmatched_video:
            logger.info(f"Eliminando segmento sin pareja: {path}")
            path.unlink()

    def combine_and_merge(self, result: dict):
        folder = result["video_init"].parent
        video_path = folder / ("video_combibed" + result["video_init"].suffix)
        with open(video_path, "wb") as fp:
            fp.write(result["video_init"].read_bytes())
            segment_folder = result["video_segments"][0].parent
            segments = [i for i in segment_folder.iterdir() if i.is_file()]
            segments.sort(key=lambda x: int(x.stem.split("_")[-1]))
            for segment in segments:
                fp.write(segment.read_bytes())

        audio_path = folder / ("audio_combibed" + result["audio_init"].suffix)
        with open(audio_path, "wb") as fp:
            fp.write(result["audio_init"].read_bytes())
            segment_folder = result["audio_segments"][0].parent
            segments = [i for i in segment_folder.iterdir() if i.is_file()]
            segments.sort(key=lambda x: int(x.stem.split("_")[-1]))
            for segment in segments:
                fp.write(segment.read_bytes())

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

        # shutil.rmtree(str(folder))

        logger.info(f"Archivo final: {output}")
