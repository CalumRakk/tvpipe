"""
jobs.py
---------
Este módulo se encarga de preparar y ejecutar trabajos de descarga (`DownloadJob`) usando combinaciones
precalculadas de formatos de video y audio. También gestiona la descarga de medios individuales en procesos separados.

Ideal para incluir funciones relacionadas con:
- Generación de trabajos de descarga para múltiples calidades.
- Descarga individual de combinaciones (video+audio).
- Procesamiento en paralelo o asincrónico de descargas.
- Extracción o análisis de los resultados de descarga (paths, formatos, calidad).
"""

import logging
from pathlib import Path
from typing import Sequence, Union, cast

import yt_dlp
from yt_dlp.utils import DownloadError

from proyect_x.yt_downloader.schemas import DownloadJob

from .download import my_progress_hook
from .formats import get_best_video_combinations
from .metadata import get_metadata

logger = logging.getLogger(__name__)


def get_download_jobs(
    url: str, qualities: Sequence[Union[int, str]], output_as_mp4: bool
) -> list[DownloadJob]:
    download_jobs = []
    formats = get_metadata(url)["formats"]
    for quality in qualities:
        combinations = get_best_video_combinations(formats, quality, output_as_mp4)
        download_jobs.append(
            {
                "quality": quality,
                "combinations": combinations,
                "url": url,
                "output_as_mp4": output_as_mp4,
            }
        )
    return download_jobs


def download_media_item(job: DownloadJob, download_folder: Path) -> dict:
    """
    Descarga un único item (video o audio) usando un format_id específico.
    Esta función está diseñada para ser ejecutada en un proceso separado.
    Retorna el path del archivo descargado o lanza un error descriptivo.
    """
    output_template = f"{download_folder}/%(id)s_%(format_id)s_%(resolution)s.%(ext)s"
    url = job["url"]
    format_id = "/".join(f"{i[0]}+{i[1]}" for i in job["combinations"])

    ydl_opts = {
        "format": format_id,
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 10,
        "fragment_retries": 10,
        "progress_hooks": [my_progress_hook],
        "progress": None,
        "noprogress": True,
        "merge_output_format": None,
        "postprocessors": [],
        "allow_unplayable_formats": True,
        # "cookiefile": r"C:\Users\Leo\Downloads\www.youtube.com_cookies.txt",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = cast(dict, ydl.extract_info(url, download=True))
            filepath = info["requested_downloads"][0]["filepath"]
            logger.info(f"✔️ Descarga completada: {Path(filepath).name}")
            return info
    except DownloadError as e:
        error_msg = f"❌ Error al descargar {url} con format {format_id}: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"⚠️ Excepción inesperada al descargar {url}: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
