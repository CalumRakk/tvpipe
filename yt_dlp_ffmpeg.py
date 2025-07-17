import concurrent.futures
import enum
import logging
import typing
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import TypedDict

import requests

from config import YOUTUBE_RELEASE_TIME
from logging_config import setup_logging
from series_manager.caracoltv import CaracolTV
from series_manager.yt_dlp_tools import (
    already_downloaded_today,
    download_media_item,
    get_download_jobs,
    get_episode_number,
    get_episode_of_the_day,
    get_metadata,
    merge_with_ffmpeg,
    register_download,
    sleep_progress,
)


class RELEASE_MODE(enum.Enum):
    AUTO = "auto"
    MANUAL = "manual"


TEMPLATE_VIDEO = "{serie_name}.capitulo.{number}.yt.{quality}p{ext}"
TEMPLATE_THUMBNAIL = "{serie_name}.capitulo.{number}.yt.thumbnail.jpg"
logger = logging.getLogger(__name__)


class EpisodeDownloaded(TypedDict):
    videos: list[Path]
    thumbnail: Path
    episode_number: str


def should_skip_today(today):
    """Determina si se debe omitir la descarga del capítulo hoy."""
    if today.weekday() >= 5:
        logger.info("Hoy es fin de semana. No hay capítulo.")
        return True
    if already_downloaded_today():
        logger.info("✅ El capítulo de hoy ya fue descargado.")
        return True
    return False


def wait_until_release(today: datetime, release_time):
    """Espera hasta la hora de lanzamiento del capítulo (especificada en release_time)."""
    if today < release_time:
        difference = release_time - today
        sleep_progress(difference.total_seconds())
        return True
    return False


def prepare_folders(output_folder):
    """Prepara las carpetas necesarias para la descarga."""
    temp_folder = output_folder / "TEMP"
    temp_folder.mkdir(parents=True, exist_ok=True)
    output_folder.mkdir(exist_ok=True)
    return temp_folder


def parallel_download(download_jobs, temp_folder):
    """Descarga los archivos de forma paralela utilizando ProcessPoolExecutor."""
    downloaded_files = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(
                download_media_item, job["url"], job["format_id"], temp_folder
            ): job
            for job in download_jobs
        }
        for future in concurrent.futures.as_completed(futures):
            job = futures[future]
            result = future.result()
            if job["type"] == "audio":
                downloaded_files["audio"] = result
            else:
                downloaded_files.setdefault("videos", {})[job["quality"]] = result
    return downloaded_files


def merge_files(
    downloaded_files, output_folder: Path, serie_name, number
) -> list[Path]:
    """Merge los archivos de video y audio descargados."""
    if "audio" not in downloaded_files or "videos" not in downloaded_files:
        logger.error("No se encontraron archivos de audio o video para fusionar.")
        raise ValueError("No se encontraron archivos de audio o video para fusionar.")

    audio_path = downloaded_files["audio"]
    finales = []
    for quality, video_path in downloaded_files["videos"].items():
        ext = Path(video_path).suffix
        filename = TEMPLATE_VIDEO.format(
            serie_name=serie_name, number=number, quality=quality, ext=ext
        )
        output = output_folder / filename
        merge_with_ffmpeg(video_path, audio_path, str(output))
        logger.info(f"Archivo final: {output}")
        finales.append(output)
    return finales


def download_thumbnail(url: str, output_folder: Path, serie_name: str):
    """Descarga la miniatura del episodio si no está descargada."""
    metadata = get_metadata(url)
    number = get_episode_number(metadata["title"])
    thumbnail = metadata.get("thumbnail")
    filename = TEMPLATE_THUMBNAIL.format(serie_name=serie_name, number=number)
    output = output_folder / filename
    if not output.exists() and thumbnail:
        response = requests.get(thumbnail)
        with open(output, "wb") as f:
            f.write(response.content)
        logger.info(f"Miniatura descargada: {output}")
    return output


def get_release_time(mode) -> datetime:
    # Si se usa el modo "auto", se obtiene la hora de lanzamiento del desafío.
    # Si no, se usa una hora fija.
    # Por defecto, se establece a las 21:30 del día actual.
    release_time = datetime.combine(datetime.now().date(), YOUTUBE_RELEASE_TIME)
    if mode == RELEASE_MODE.AUTO:
        caractol = CaracolTV()
        schedule = caractol.get_schedule_desafio()
        if schedule:
            release_time = schedule["endtime"] + timedelta(minutes=5)
            return release_time
        raise ValueError("No se encontró la programación del desafío.")
    return release_time


def main_loop(
    serie_name: str,
    qualities: list[int],
    output_folder: Path,
    mode: RELEASE_MODE,
) -> typing.Generator[EpisodeDownloaded, None, None]:
    logger.info("Iniciando el bucle principal de descarga del capítulo del día.")
    release_time = get_release_time(mode)
    while True:
        logger.info(f"Hora de lanzamiento: {release_time.strftime('%I:%M %p')}")

        today = datetime.now()
        if should_skip_today(today):
            end_of_day = datetime.combine(today.date(), time(23, 59, 59))
            sleep_progress((end_of_day - today).total_seconds())
            continue

        if wait_until_release(today, release_time) and mode is RELEASE_MODE.AUTO:
            # Una vez de la primera espera se vuelve a calcular la hora de lanzamiento.
            # para casos donde la programacion pueda cambiar.
            release_time = get_release_time(mode)
            logger.info(f"Hora de lanzamiento actualizada.")
            continue

        url = get_episode_of_the_day()
        if not url:
            sleep_progress(120)
            continue

        temp_folder = prepare_folders(output_folder)

        download_jobs = get_download_jobs(url, qualities)
        downloaded_files = parallel_download(download_jobs, temp_folder)

        video_title = get_metadata(url)["title"]
        number = get_episode_number(video_title)
        serie_name_final = serie_name.replace(" ", ".").lower()

        videos = merge_files(
            downloaded_files,
            output_folder,
            serie_name_final,
            number,
        )
        register_download(number)
        thumbnail_path = download_thumbnail(url, output_folder, serie_name_final)

        logger.info("✅ Descarga del capítulo del día completada.")
        yield {"videos": videos, "thumbnail": thumbnail_path, "episode_number": number}


if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")
    serie_name = "desafio siglo xxi 2025"
    qualities = [240]
    output_folder = Path("output")
    mode = RELEASE_MODE.MANUAL

    for final_files in main_loop(serie_name, qualities, output_folder, mode):
        logger.info(f"Archivos finales: {final_files}")
        break
