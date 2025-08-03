import logging
import shutil
import subprocess
from dataclasses import asdict
from datetime import datetime, time, timedelta
from pathlib import Path
from time import sleep
from typing import Optional, Tuple, Union, cast
from urllib.parse import urlparse

import requests
from unidecode import unidecode

from proyect_x.ditu.api.dash import Dash, Period, Representation
from proyect_x.ditu.schemas.simple_schedule import CurrentSchedule, SimpleSchedule

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
        logger = logging.getLogger(__name__)
        is_string = True if isinstance(channel, str) else False
        if is_string:
            return self.schedule.get_schedule_by_name(channel)
        else:
            return self.schedule.get_schedule_by_id(int(channel))

    def _build_output_path(
        self, schedule: SimpleSchedule, base_output: Path, video_rep: Representation
    ) -> Path:
        logger = logging.getLogger(__name__)
        title_slug = unidecode(schedule.title.strip()).lower().replace(" ", ".")
        start = schedule.start_time.isoformat().replace(":", ".").replace("T", ".")
        width = video_rep.height
        folder_name = f"{title_slug}.capitulo.{schedule.episode_number}.ditu.live.{width}p.{start}.content_id={schedule.content_id}"
        logger.info(f"📂 Carpeta de salida: {folder_name}")
        return base_output / folder_name

    def _download_url_initial(self, url: str, base_output: Path) -> Path:
        logger = logging.getLogger(__name__)
        logger.info(f"🔗 Descargando URL inicial: {url}")
        path = urlparse(url).path
        init_path = base_output / Path(path).name
        if self._download_file_if_needed(url, init_path):
            logger.info(f"✅ Descargado: {init_path.parent.name}/{init_path.name}")
        else:
            logger.info(
                f"No se descargó el archivo: {init_path.parent.name}/{init_path.name}"
            )
        return init_path

    # def _download_representation_segments(
    #     self, rep: Representation, base_output: Path
    # ) -> Tuple[Path, list[Path]]:
    #     path = urlparse(rep.url_initial).path
    #     init_path = base_output.parent / Path(path).name
    #     self._download_file_if_needed(rep.url_initial, init_path)

    #     segmensts = []
    #     for segment_url in rep.segments:
    #         path = urlparse(segment_url).path
    #         segment_path = base_output / Path(path).name
    #         if self._download_file_if_needed(segment_url, segment_path):
    #             segmensts.append(segment_path)
    #     return init_path, segmensts

    def _download_segments(self, segments: list[str], base_output: Path):
        logger = logging.getLogger(__name__)
        for segment_url in segments:
            urlpath = urlparse(segment_url).path
            segment_path = base_output / Path(urlpath).name
            logger.info(f"🔗 Descargando segmento: {segment_path.name}")
            if self._download_file_if_needed(segment_url, segment_path):
                logger.info(
                    f"✅ Descargado: {segment_path.parent.name}/{segment_path.name}"
                )

    def _download_file_if_needed(self, url: str, path: Path) -> bool:
        """Devuelve True si y solo si ha descargado el archivo."""
        logger = logging.getLogger(__name__)
        if path.exists():
            logger.info(f"Archivo ya existe: {path.parent.name}/{path.name}")
            return False
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
            logger.info(f"✅ Descargado: {path.parent.name}/{path.name}")
            return True
        except Exception as e:
            logger.error(f"❌ Error al descargar: {path}: {e}")
            return False

    def get_period_content(self, url) -> Tuple[Period, list[Period]]:
        """Intenta devolver el Period que contiene el contenido (no comerciales), si no lo encuentra lo intenta 5 veces por 15 segundos."""
        logger = logging.getLogger(__name__)
        archive = []
        while True:
            mpd = self.dash.fetch_mpd(url)
            periods = self.dash.parse_periods(mpd)
            archive.extend(periods)
            if len(periods) == 1:
                logger.info("Periodo de contenido encontrado")
                return periods[0], archive
            logger.info("Periodo unico no encontrado. Actualmente en comerciales")
            sleep(2)

    def _get_videorepresentation_from_periods(
        self, periods, representation: Representation
    ):
        repres = self._get_videorepresentations_from_periods(periods, representation)
        if len(repres) >= 1:
            return repres[0]
        return None

    def _get_videorepresentations_from_periods(
        self, periods, representation: Representation
    ) -> list[Representation]:
        repres = []
        for period in periods:
            for adapt in period.AdaptationSets:
                if adapt.is_video:
                    for rep in adapt.representations:
                        if rep.media == representation.media:
                            logger.info(
                                f"✅ Representación de video encontrada: {rep.id}"
                            )
                            repres.append(rep)

        return repres

    def _get_audiorepresentation_from_periods(
        self, periods, representation: Representation
    ):
        repres = self._get_audiorepresentations_from_periods(periods, representation)
        if len(repres) >= 1:
            return repres[0]
        return None

    def _get_audiorepresentations_from_periods(
        self, periods, representation: Representation
    ) -> list[Representation]:
        repres = []
        for period in periods:
            for adapt in period.AdaptationSets:
                if not adapt.is_video:
                    for rep in adapt.representations:
                        if rep.media == representation.media:
                            logger.info(
                                f"✅ Representación de audio encontrada: {rep.id}"
                            )
                            repres.append(rep)

        return repres

    def capture_schedule(self, schedule: SimpleSchedule, output_dir: Union[str, Path]):
        logger = logging.getLogger(__name__)
        logger.info(
            f"Preparando datos iniciales para la captura del schedule: {schedule.content_id}"
        )
        url = self.dash.get_live_channel_manifest(schedule.channel_id)
        output_dir = Path(output_dir) if isinstance(output_dir, str) else output_dir
        result = {
            "video_representation_id": None,
            "audio_representation_id": None,
            "folder_video": None,
            "folder_audio": None,
            "video_init_path": Optional[Path],
            "audio_init_path": Optional[Path],
        }
        period_content, periods = self.get_period_content(url)
        best_rep_video = period_content.best_video_representation()
        best_rep_audio = period_content.best_audio_representation()
        output = self._build_output_path(schedule, output_dir, best_rep_video)

        result["video_init_path"] = self._download_url_initial(
            best_rep_video.url_initial, output
        )
        result["audio_init_path"] = self._download_url_initial(
            best_rep_audio.url_initial, output
        )
        folder_video = output / "video"
        folder_audio = output / "audio"
        result["folder_video"] = folder_video
        result["folder_audio"] = folder_audio
        result["video_representation_id"] = best_rep_video.id
        result["audio_representation_id"] = best_rep_audio.id

        logger.info(f"Datos iniciales preparados: {result}")
        logger.info("-" * 50)
        logger.info(f"Iniciando descarga de segmentos...")

        video_reps = self._get_videorepresentations_from_periods(
            periods, best_rep_video
        )
        audio_reps = self._get_audiorepresentations_from_periods(
            periods, best_rep_audio
        )
        for video_rep in video_reps:
            for audio_rep in audio_reps:
                self._download_segments(video_rep.segments, folder_video)
                self._download_segments(audio_rep.segments, folder_audio)

        while True:
            try:
                time_capture = datetime.now()
                mpd = self.dash.fetch_mpd(url)
                periods = self.dash.parse_periods(mpd)
                video_rep = self._get_videorepresentation_from_periods(
                    periods, best_rep_video
                )
                audio_rep = self._get_audiorepresentation_from_periods(
                    periods, best_rep_audio
                )
                if video_rep and audio_rep:
                    logger.info(f"📦 Representación de video y audio encontrada")
                    self._download_segments(video_rep.segments, folder_video)
                    self._download_segments(audio_rep.segments, folder_audio)
                else:
                    logger.info(
                        f"❌ No se encontraron representaciones de video o audio. "
                    )
                if self.is_program_airing_finished(time_capture, schedule):

                    break

                sleep(2)
                logger.info("=" * 50)
            except requests.exceptions.ConnectionError as e:
                logger.error(f"❌ Error de red: {e}")
                sleep(1)
            except Exception as e:
                logger.error(f"❌ Error inesperado: {e}")
                sleep(1)

        logger.info("Captura finalizada. Combinando y fusionando segmentos...")
        self.cleanup_audio_segments_without_video(result)
        return result

    def is_program_airing_finished(
        self, time_capture, schedule: SimpleSchedule
    ) -> bool:
        """
        Determina si la emisión del programa ha finalizado.

        Esta función compara el tiempo actual de captura con la hora de finalización
        del programa (`schedule.end_time`). Si la captura supera esa hora, se verifica
        si el programa en emisión es el mismo (usando `content_id`) y si su duración
        ha cambiado (nuevo `end_time`). Si después de actualizar el horario aún se ha
        superado el nuevo tiempo de finalización, se considera que el programa ha finalizado.

        Args:
            time_capture (datetime): Hora actual de captura.
            schedule (SimpleSchedule): Objeto que representa la programación original del programa.

        Returns:
            bool: True si la emisión del programa ha terminado, False en caso contrario.
        """
        if time_capture <= schedule.end_time:
            logger.info(
                f"Captura aún en curso: time_capture={time_capture}, end_time={schedule.end_time}"
            )
            return False

        logger.info(f"Obteniendo la emision actual del canal: {schedule.channel_id}")
        current = self.schedule.get_current_program_live(schedule.channel_id)
        logger.info(
            f"La emision actual del canal: {current.title} ({current.content_id})"
        )
        is_same_program = schedule.content_id == current.content_id
        if is_same_program:
            logger.info(
                f"El programa capturado con id [{schedule.channel_id}] es el mismo que el en emision: {current.title} ({current.content_id})"
            )
            return False
        logger.info(
            f"El programa capturado con id [{schedule.channel_id}] ha finalizado: {current.title} ({current.content_id})"
        )
        return True
        # logger.debug(
        #     f"[{schedule.channel_id}] Comparando programación actual: "
        #     f"captured={schedule.content_id}, current={current.content_id}, "
        #     f"old_end_time={schedule.end_time}, new_end_time={current.end_time}"
        # )

        # is_same_program = schedule.content_id == current.content_id
        # has_new_end_time = schedule.end_time != current.end_time
        # if not is_same_program:
        #     return True
        # elif has_new_end_time and is_same_program:
        #     schedule.airingEndTime = current.airingEndTime
        #     if time_capture > (current.end_time + timedelta(seconds=15)):
        #         logger.info(
        #             f"[{schedule.channel_id}] La emisión del programa ha finalizado. "
        #             f"Finalizó a las {current.end_time}, captura a las {time_capture}"
        #         )
        #         return True
        #     return False
        # return True

    def is_end_difference(
        self, schedule: SimpleSchedule, current: CurrentSchedule
    ) -> bool:
        if schedule.end_time != current.end_time:
            logger.info(f"La finalizacion del programa ha cambiado: {schedule.title}")
            return True
        return False

    def cleanup_audio_segments_without_video(self, result: dict):
        """
        Elimina archivos de video y audio cuyos índices no tienen una contraparte en el otro grupo.

        Parámetros:
            result (dict): Diccionario con claves 'video_segments' y 'audio_segments',
                        cada uno conteniendo una lista de rutas a archivos por segmento.
        """
        v_rep_id = result["video_representation_id"]
        a_rep_id = result["audio_representation_id"]
        folder_video: Path = result["folder_video"]
        folder_audio: Path = result["folder_audio"]

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

    def combine_and_merge_by_folder(self, folder: Union[Path, str]):
        folder = Path(folder) if isinstance(folder, str) else folder

        video_init = [i for i in folder.iterdir() if i.is_file() and "video" in i.name][
            0
        ]
        audio_init = [i for i in folder.iterdir() if i.is_file() and "audio" in i.name][
            0
        ]

        folder_video = folder / "video"
        folder_audio = folder / "audio"

        output_video_combined = folder / "video_combibed.mp4"
        output_audio_combined = folder / "audio_combibed.mp4"

        with open(output_video_combined, "wb") as fp:
            fp.write(video_init.read_bytes())
            segments: list[Path] = [i for i in folder_video.iterdir() if i.is_file()]
            segments.sort(key=lambda x: x.stat().st_mtime)
            for segment in segments[:-10]:
                fp.write(segment.read_bytes())

        with open(output_audio_combined, "wb") as fp:
            fp.write(audio_init.read_bytes())
            segments: list[Path] = [i for i in folder_audio.iterdir() if i.is_file()]
            segments.sort(key=lambda x: x.stat().st_mtime)
            for segment in segments[:-10]:
                fp.write(segment.read_bytes())

        output = (folder.parent / folder.name).with_suffix(video_init.suffix)
        cmd = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-i",
            str(output_video_combined),
            "-i",
            str(output_audio_combined),
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-shortest",
            str(output),
        ]
        subprocess.run(cmd, check=True)
        output_video_combined.unlink()
        output_audio_combined.unlink()

    def combine_and_merge(self, result: dict):
        video_init_path = result["video_init_path"]
        audio_init_path = result["audio_init_path"]
        folder = video_init_path.parent

        video_path = folder / ("video_combibed" + video_init_path.suffix)
        with open(video_path, "wb") as fp:
            fp.write(video_init_path.read_bytes())
            folder_video = result["folder_video"]
            segments: list[Path] = [i for i in folder_video.iterdir() if i.is_file()]
            segments.sort(key=lambda x: x.stat().st_mtime)
            for segment in segments:
                fp.write(segment.read_bytes())

        audio_path = folder / ("audio_combibed" + audio_init_path.suffix)
        with open(audio_path, "wb") as fp:
            fp.write(audio_init_path.read_bytes())
            folder_audio = result["folder_audio"]
            segments = [i for i in folder_audio.iterdir() if i.is_file()]
            segments.sort(key=lambda x: x.stat().st_mtime)
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

        shutil.rmtree(str(folder))

        logger.info(f"Archivo final: {output}")
