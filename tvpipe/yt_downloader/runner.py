import logging
import re
import time
from datetime import datetime
from typing import Generator

from tvpipe.config import DownloaderConfig
from tvpipe.services.program_monitor import ProgramMonitor
from tvpipe.services.register import RegistryManager
from tvpipe.utils import sleep_progress

from .client import YtDlpClient
from .models import DownloadedEpisode
from .processing import download_thumbnail

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


def is_valid_episode_title(title: str) -> bool:
    """
    Define explícitamente qué constituye un episodio válido.
    Usa la extracción del número de episodio como validación.
    """
    try:
        episode_num = get_episode_number_from_title(title)
        return bool(episode_num) and "avance" in title
    except Exception:
        return False


def main_loop(
    config: DownloaderConfig, registry: RegistryManager, monitor: ProgramMonitor
) -> Generator[DownloadedEpisode, None, None]:

    client = YtDlpClient()
    CHANNEL_URL = "https://www.youtube.com/@desafiocaracol/videos"
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
                url = client.find_video_by_criteria(
                    channel_url=CHANNEL_URL, title_validator=is_valid_episode_title
                )
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
            stream = client.select_best_pair(
                meta, quality_preference=quality_pref, require_mp4=config.output_as_mp4
            )
            filename = config.generate_filename(episode_num, stream.height)
            output_path = config.download_folder / filename

            client.download_stream(stream, output_path, url)

            thumb_path = output_path.with_suffix(".jpg")
            download_thumbnail(meta.thumbnail_url, thumb_path)

            # Yield Resultado
            yield DownloadedEpisode(
                episode_number=episode_num,
                video_path=output_path,
                thumbnail_path=thumb_path,
            )

            logger.info(f"Ciclo terminado para episodio {episode_num}")

    except Exception as e:
        logger.error(f"Error en el ciclo de descarga: {e}", exc_info=True)
        time.sleep(30)
