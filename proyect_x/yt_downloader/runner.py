import logging
import re
import time
from datetime import datetime
from typing import Generator, Optional, cast

import yt_dlp

from proyect_x.config import DownloaderConfig
from proyect_x.services.program_monitor import ProgramMonitor
from proyect_x.services.register import RegistryManager
from proyect_x.utils import sleep_progress

from .client import YtDlpClient
from .models import DownloadedEpisode
from .processing import download_thumbnail, merge_video_audio

# from .services.scheduling import get_episode_url

logger = logging.getLogger(__name__)


def get_episode_number_from_title(title: str) -> str:
    """Extrae el número de episodio del titulo"""
    match = re.search(r"ap[íi]tulo\s+(\d+)", title, re.IGNORECASE)
    if match:
        return match.group(1)
    raise Exception("No se encontró el número de episodio.")


def should_skip_weekends():
    """Determina si se debe omitir la descarga del capítulo hoy."""
    today = datetime.now()
    if today.weekday() >= 5:
        logger.info("Hoy es fin de semana. No hay capítulo.")
        return True
    return False


def time_remaining_in_day():
    now = datetime.now()
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59, 999999)
    return end_of_day - now


def wait_end_of_day():
    logger.info("Esperando fin de dia...")
    time_remaining = time_remaining_in_day()
    sleep_progress(time_remaining.total_seconds())
    logger.info("Dia terminado.")


def get_episode_of_the_day(client: YtDlpClient) -> Optional[str]:

    logger.info("Consiguiendo el episodio del día...")
    url = "https://www.youtube.com/@desafiocaracol/videos"
    ydl_opts: yt_dlp._Params = {
        "extract_flat": True,
        "playlistend": 5,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = cast(dict, ydl.extract_info(url, download=False))
        for entry in info["entries"]:
            try:
                title = entry["title"]
                url = entry["url"]
                # Truco para identificar el video que es el "capitulo"
                number = get_episode_number_from_title(title)
                if number is None:
                    continue

                # Verificamos que el capítulo haya sido publicado el día actual.
                info = client.get_metadata(url)
                timestamp = datetime.fromtimestamp(info.timestamp)

                is_today = timestamp.date() == datetime.now().date()
                if (
                    is_today
                    and info.was_live is False
                    and not "avance" in title.lower()
                ):
                    logger.info(f"Encontrado el episodio del dia: {title}")
                    return url
            except Exception:
                continue
        logger.info(f"No se encontró el episodio del dia.")


def main_loop(
    config: DownloaderConfig, registry: RegistryManager, monitor: ProgramMonitor
) -> Generator[DownloadedEpisode, None, None]:

    client = YtDlpClient()

    temp_dir = config.download_folder / "TEMP"
    temp_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Iniciando bucle principal de descargas (Refactorizado)")

    try:
        while True:
            url = config.url
            if url is None:
                if should_skip_weekends():
                    logger.info("Es fin de semana. Esperando a que finalice el dia.")
                    wait_end_of_day()
                    continue
                elif monitor.should_wait():
                    # al finalizar la espera del lanzamiento,
                    # se vuelve a obtener la hora de lanzamiento para casos donde la programación pueda cambiar.
                    monitor.wait_until_release()
                    continue
                url = get_episode_of_the_day(client)
                if url is None:
                    sleep_progress(120)
                    continue

            meta = client.get_metadata(url)
            episode_num = get_episode_number_from_title(meta.title)
            if registry.was_episode_published(episode_num):
                logger.info(
                    "El capítulo de hoy ya fue descargado. Esperando al siguiente."
                )
                wait_end_of_day()
                continue

            quality_pref = str(config.qualities[0]) if config.qualities else "1080p"
            video_stream, audio_stream = client.select_best_pair(
                meta, quality_preference=quality_pref, require_mp4=config.output_as_mp4
            )

            vid_path = (
                temp_dir
                / f"{config.serie_slug}_{episode_num}_{video_stream.format_id}.{video_stream.ext}"
            )
            aud_path = (
                temp_dir
                / f"{config.serie_slug}_{episode_num}_{audio_stream.format_id}.{audio_stream.ext}"
            )

            client.download_stream(video_stream, vid_path, url)
            client.download_stream(audio_stream, aud_path, url)

            # Procesamiento
            final_filename = f"{config.serie_slug}.capitulo.{episode_num}.mp4"
            final_path = config.download_folder / final_filename

            merge_video_audio(vid_path, aud_path, final_path)

            # Miniatura
            thumb_path = (
                config.download_folder
                / f"{config.serie_slug}.capitulo.{episode_num}.jpg"
            )
            download_thumbnail(meta.thumbnail_url, thumb_path)

            # Yield Resultado
            yield DownloadedEpisode(
                episode_number=episode_num,
                video_path=final_path,
                thumbnail_path=thumb_path,
            )

            logger.info(f"Ciclo terminado para episodio {episode_num}")

    except Exception as e:
        logger.error(f"Error en el ciclo de descarga: {e}", exc_info=True)
        time.sleep(30)
