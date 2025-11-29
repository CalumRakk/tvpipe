import logging
from datetime import datetime, time

from proyect_x.config import DownloaderConfig
from proyect_x.services.caracoltv import CaracolTV
from proyect_x.services.register import RegistryManager
from proyect_x.yt_downloader.core.common import sleep_progress
from proyect_x.yt_downloader.core.episode import (
    get_episode_number,
    get_episode_of_the_day,
    get_metadata,
)

logger = logging.getLogger(__name__)


def should_skip_weekends():
    """Determina si se debe omitir la descarga del capítulo hoy."""
    today = datetime.now()
    if today.weekday() >= 5:
        logger.info("Hoy es fin de semana. No hay capítulo.")
        return True
    return False


def was_episode_published(url: str, registry: RegistryManager) -> bool:
    """Verifica si el episodio ya fue publicado."""
    metadata = get_metadata(url)
    title = metadata["title"]
    number = get_episode_number(title)

    if registry.was_episode_published(number):
        logger.info("El capítulo de hoy ya fue descargado.")
        return True
    return False


# def should_wait_release(schedule_provider: CaracolTV):
#     """Determina si se debe esperar la hora de lanzamiento del capítulo."""
#     release_time = schedule_provider.get_release_time()
#     today = datetime.now()
#     if today < release_time:
#         return True
#     return False


# def get_release_time(schedule_provider: CaracolTV) -> datetime:
#     """Obtiene la hora de lanzamiento del capítulo."""
#     schedule = schedule_provider.get_schedule_desafio()
#     if schedule:
#         release_time = schedule["endtime"] + timedelta(minutes=5)
#         return release_time
#     else:
#         logger.warning("No se pudo obtener la hora de lanzamiento del desafío.")
#         raise ScheduleNotFound("No se pudo obtener la hora de lanzamiento del desafío.")


def wait_end_of_day():
    logger.info("Esperando fin de día...")
    today = datetime.now()
    end_of_day = datetime.combine(today.date(), time(23, 59, 59))
    sleep_progress((end_of_day - today).total_seconds())


# def wait_release(schedule_provider: CaracolTV):
#     """Espera hasta la hora de lanzamiento del capítulo segun la programacion de caracoltv."""
#     release_time = get_release_time(schedule_provider)
#     logger.info(
#         f"Hora de publicacion del capitulo en youtube: {release_time.strftime('%I:%M %p')}"
#     )
#     today = datetime.now()
#     difference = release_time - today
#     sleep_progress(difference.total_seconds())
#     return False


def get_episode_url(
    config: DownloaderConfig, registry: RegistryManager, schedule_provider: CaracolTV
) -> str:
    url = None
    while url is None:
        if not config.url and should_skip_weekends():
            wait_end_of_day()
            continue
        if not config.url and schedule_provider.should_wait_release():
            # al finalizar la espera del lanzamiento,
            # se vuelve a obtener la hora de lanzamiento para casos donde la programación pueda cambiar.
            schedule_provider.wait_release()
            continue

        url = get_episode_of_the_day() if config.url is None else config.url
        if url is None:
            sleep_progress(120)
            continue
        elif config.check_episode_publication and was_episode_published(url, registry):
            logger.info("El capítulo de hoy ya fue descargado. Esperando al siguiente.")
            wait_end_of_day()
            url = None
            continue

        if config.url:
            break
    return url
