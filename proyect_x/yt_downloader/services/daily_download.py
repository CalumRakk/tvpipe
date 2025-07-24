import concurrent.futures
import logging
from pathlib import Path
from typing import cast

import requests

from proyect_x.shared.download_register import EventType, register_event
from proyect_x.yt_downloader.core.download import merge_with_ffmpeg
from proyect_x.yt_downloader.core.episode import get_episode_number
from proyect_x.yt_downloader.core.formats import extract_files_from_download_result
from proyect_x.yt_downloader.core.metadata import get_metadata
from proyect_x.yt_downloader.schemas import (
    DownloadJob,
    DownloadJobResult,
    YtDlpResponse,
)

from ..core.jobs import download_media_item, get_download_jobs

logger = logging.getLogger(__name__)


def prepare_folders(download_folder):
    """Prepara las carpetas necesarias para la descarga."""
    temp_folder = download_folder / "TEMP"
    temp_folder.mkdir(parents=True, exist_ok=True)
    download_folder.mkdir(exist_ok=True)
    return temp_folder


def prepare_formats(episode: str, config) -> list[DownloadJob]:

    qualities = config.qualities
    output_as_mp4 = config.output_as_mp4
    return get_download_jobs(episode, qualities, output_as_mp4)


def parallel_downloads(
    download_jobs: list[DownloadJob], config
) -> list[DownloadJobResult]:
    """Descarga una lita de jobs de descarga en paralelo y devuelve una lista de resultados."""

    download_folder = config.download_folder
    temp_folder = prepare_folders(download_folder)

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


def download_thumbnail(url: str, config) -> Path:
    """Descarga la miniatura del episodio si no está descargada."""
    metadata = get_metadata(url)
    number = get_episode_number(metadata["title"])
    thumbnail = metadata.get("thumbnail")

    filename = f"{config.serie_slug}.capitulo.{number}.yt.thumbnail.jpg"
    output = config.download_folder / filename
    if not output.exists() and thumbnail:
        response = requests.get(thumbnail)
        with open(output, "wb") as f:
            f.write(response.content)
        logger.info(f"Miniatura descargada: {output}")
    return output


def postprocess_and_register(
    url: str, downloads: list[DownloadJobResult], config
) -> dict:
    finales = []

    serie_name_final = config.serie_slug
    download_folder = config.download_folder
    video_title = get_metadata(url)["title"]
    number = get_episode_number(video_title)
    for download_result in downloads:
        # Datos de download_result
        video_path, audio_path, quality_height = extract_files_from_download_result(
            download_result
        )
        if video_path is None or audio_path is None:
            raise Exception("No se pudo encontrar el video o el audio")

        # build filename y output
        filename = f"{serie_name_final}.capitulo.{number}.yt.{quality_height}p{video_path.suffix}"
        output = download_folder / filename

        if not output.exists():
            merge_with_ffmpeg(video_path, audio_path, str(output))
            register_event(
                episode=number,
                event="download",
                file_path=output,
                source="yt_downloader",
            )

        finales.append(output)

    thumbnail_path = download_thumbnail(url, config)
    return {
        "videos": finales,
        "thumbnail": thumbnail_path,
        "episode_number": number,
    }
