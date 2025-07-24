import concurrent.futures
import enum
import logging
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Generator, Optional, Sequence, Tuple, Union, cast

import requests

from proyect_x.caracoltv import CaracolTV
from proyect_x.download_register import DownloadRegistry, EpisodeDownloaded

from .core.download import merge_with_ffmpeg, sleep_progress
from .core.episode import (
    already_downloaded_today,
    get_episode_number,
    get_episode_of_the_day,
)
from .core.formats import get_format_type
from .core.jobs import download_media_item, get_download_jobs
from .core.metadata import get_metadata
from .schemas import DownloadJob, DownloadJobResult, MainLoopResult, YtDlpResponse


class RELEASE_MODE(enum.Enum):
    AUTO = "auto"
    MANUAL = "manual"


TEMPLATE_VIDEO = "{serie_name}.capitulo.{number}.yt.{quality_height}p{ext}"
TEMPLATE_THUMBNAIL = "{serie_name}.capitulo.{number}.yt.thumbnail.jpg"
logger = logging.getLogger(__name__)


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


def parallel_download(
    download_jobs: list[DownloadJob], temp_folder
) -> list[DownloadJobResult]:
    """Descarga una lita de jobs de descarga en paralelo y devuelve una lista de resultados."""

    downloaded_files = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(download_media_item, job, temp_folder): job
            for job in download_jobs
        }
        for future in concurrent.futures.as_completed(futures):
            job = cast(DownloadJob, futures[future])
            result = cast(YtDlpResponse, future.result())
            download_result = {"download_job": job, "ytdlp_response": result}
            downloaded_files.append(download_result)
    return downloaded_files


def download_thumbnail(url: str, output_folder: Path, serie_name: str) -> Path:
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
    release_time = None
    if mode == RELEASE_MODE.AUTO:
        caractol = CaracolTV()
        schedule = caractol.get_schedule_desafio()
        if schedule:
            release_time = schedule["endtime"] + timedelta(minutes=5)
            return release_time
        raise ValueError("No se encontró la programación del desafío.")
    else:
        release_time = datetime.combine(datetime.now().date(), YOUTUBE_RELEASE_TIME)  # type: ignore
        pass  # FIXME: Corregir
    return release_time


def extract_files_from_download_result(
    download_result: DownloadJobResult,
) -> Tuple[Optional[Path], Optional[Path], Optional[int]]:
    video = None
    audio = None
    quality_height = None
    for formatsimple in download_result["ytdlp_response"]["requested_downloads"][0][
        "requested_formats"
    ]:
        if get_format_type(formatsimple) == "video":
            video = Path(formatsimple["filepath"]).resolve()
            quality_height = formatsimple["height"]

        elif get_format_type(formatsimple) == "audio":
            audio = Path(formatsimple["filepath"]).resolve()
    return (video, audio, quality_height)


def main_loop(
    serie_name: str,
    qualities: Sequence[Union[int, str]],
    output_folder: Path,
    mode: RELEASE_MODE,
    output_as_mp4: bool = True,
) -> Generator[MainLoopResult, None, None]:
    """Bucle principal de descarga del capítulo del día.

    Args:
        serie_name (str): Nombre de la serie.
        qualities (list[int]): Listado de resoluciones a descargar.
        output_folder (Path): Carpeta de salida.
        mode (RELEASE_MODE): Modo de lanzamiento.
        output_as_mp4 (bool): Si se debe descargar el capítulo como MP4.

    Nota: output_as_mp4 influye en la calidad de los formatos de video. Cuando es True, se seleccionará solo mejor calidad especifica que sea compatible para mergear video con audio para MP4.
    """

    logger.info("Iniciando el bucle principal de descarga del capítulo del día.")
    release_time = get_release_time(mode)
    while True:
        logger.info(f"Hora de lanzamiento: {release_time.strftime('%I:%M %p')}")

        # today = datetime.now()
        # if should_skip_today(today):
        #     end_of_day = datetime.combine(today.date(), time(23, 59, 59))
        #     sleep_progress((end_of_day - today).total_seconds())
        #     continue

        # if wait_until_release(today, release_time) and mode is RELEASE_MODE.AUTO:
        #     # Una vez de la primera espera se vuelve a calcular la hora de lanzamiento.
        #     # para casos donde la programacion pueda cambiar.
        #     release_time = get_release_time(mode)
        #     logger.info(f"Hora de lanzamiento actualizada.")
        #     continue

        url = get_episode_of_the_day()
        if not url:
            sleep_progress(120)
            continue
        video_title = get_metadata(url)["title"]
        number = get_episode_number(video_title)
        serie_name_final = serie_name.replace(" ", ".").lower()

        temp_folder = prepare_folders(output_folder)

        download_jobs = get_download_jobs(url, qualities, output_as_mp4=output_as_mp4)
        downloaded_results = parallel_download(download_jobs, temp_folder)

        finales = []
        for download_result in downloaded_results:
            quality_label = download_result["download_job"]["quality"]
            video_path, audio_path, quality_height = extract_files_from_download_result(
                download_result
            )
            if video_path is None or audio_path is None:
                continue

            filename = TEMPLATE_VIDEO.format(
                serie_name=serie_name_final,
                number=number,
                quality_height=quality_height,
                ext=video_path.suffix,
            )
            output = output_folder / filename
            if not output.exists():
                merge_with_ffmpeg(video_path, audio_path, str(output))
                register = DownloadRegistry()
                register.register_download(
                    episode=number,
                    source="youtube",
                    method="download",
                    quality=quality_label,
                    path=output,
                )
            finales.append(output)

        thumbnail_path = download_thumbnail(url, output_folder, serie_name_final)

        yield {
            "videos": finales,
            "thumbnail": thumbnail_path,
            "episode_number": number,
        }

        logger.info("✅ Descarga del capítulo del día completada.")


if __name__ == "__main__":
    serie_name = "desafio siglo xxi 2025"
    qualities = ["720", "360"]
    output_folder = Path("output")
    mode = RELEASE_MODE.AUTO

    for final_files in main_loop(serie_name, qualities, output_folder, mode):
        logger.info(f"Archivos finales: {final_files}")
        break
