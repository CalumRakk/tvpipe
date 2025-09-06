import logging
from datetime import datetime, time, timedelta
from typing import Optional, cast

from proyect_x.caracoltv import CaracolTV
from proyect_x.shared.download_register import RegistryManager
from proyect_x.yt_downloader.core.common import sleep_progress
from proyect_x.yt_downloader.core.episode import (
    get_episode_number,
    get_episode_of_the_day,
    get_metadata,
)
from proyect_x.yt_downloader.exceptions import ScheduleNotFound
from proyect_x.yt_downloader.schemas import RELEASE_MODE

logger = logging.getLogger(__name__)
register = RegistryManager()


def should_skip_weekends():
    """Determina si se debe omitir la descarga del capítulo hoy."""
    today = datetime.now()
    if today.weekday() >= 5:
        logger.info("Hoy es fin de semana. No hay capítulo.")
        return True
    return False


def was_episode_published(url: str) -> bool:
    """Verifica si el episodio ya fue publicado."""
    metadata = get_metadata(url)
    title = metadata["title"]
    number = get_episode_number(title)

    if register.was_episode_published(number):
        logger.info("✅ El capítulo de hoy ya fue descargado.")
        return True
    return False


def wait_until_release(config):
    # TODO: Corregir nombre de la función.
    """Espera hasta la hora de lanzamiento del capítulo (especificada en release_time)."""
    release_time = get_release_time(config)
    today = datetime.now()
    if today < release_time:
        return True
    return False


def get_release_time(config) -> datetime:
    # Si se usa el modo "auto", se obtiene la hora de lanzamiento del desafío.
    # Si no, se usa una hora fija.
    # Por defecto, se establece a las 21:30 del día actual.
    release_time = None
    if config.mode == RELEASE_MODE.AUTO:
        caractol = CaracolTV()
        schedule = caractol.get_schedule_desafio()
        if schedule:
            release_time = schedule["endtime"] + timedelta(minutes=5)
            return release_time
        else:
            logger.warning("No se pudo obtener la hora de lanzamiento del desafío.")
            raise ScheduleNotFound(
                "No se pudo obtener la hora de lanzamiento del desafío."
            )
    else:
        release_time = datetime.combine(datetime.now().date(), config.release_hour)
    return release_time


def wait_end_of_day():
    logger.info("Esperando fin de día...")
    today = datetime.now()
    end_of_day = datetime.combine(today.date(), time(23, 59, 59))
    sleep_progress((end_of_day - today).total_seconds())


def wait_release(mode):
    """Espera hasta la hora de lanzamiento del capítulo (especificada en release_time)."""
    release_time = get_release_time(mode)
    logger.info(
        f"Hora de publicacion del capitulo en youtube: {release_time.strftime('%I:%M %p')}"
    )
    today = datetime.now()
    difference = release_time - today
    sleep_progress(difference.total_seconds())
    return False


def get_episode_url(config) -> str:
    url = None
    while url is None:
        try:
            if not config.url and should_skip_weekends():
                wait_end_of_day()
                continue
            if (
                not config.url
                and wait_until_release(config)
                and config.mode is RELEASE_MODE.AUTO
            ):
                # TODO creo que se puede eliminar la opcion RELEASE_MODE. Esta opcion podria funcionar con solo especificar la hora de lanzamiento sino se especifica es porque se usa el modo auto
                # Si mode está en auto, al finalizar la espera del lanzamiento,
                # se vuelve a obtener la hora de lanzamiento para casos donde la programación pueda cambiar.
                wait_release(config)
                continue

            url = get_episode_of_the_day() if config.url is None else config.url
            if url is None:
                sleep_progress(120)
                continue
            elif config.check_episode_publication and was_episode_published(url):
                logger.info(
                    "El capítulo de hoy ya fue descargado. Esperando al siguiente."
                )
                wait_end_of_day()
                url = None
                continue

            if config.url:
                break

        except ScheduleNotFound as e:
            logger.error(f"Error al obtener la programación: {e}")
            wait_10_minutes = datetime.now() + timedelta(minutes=10)
            logger.info(f"Esperando hasta {wait_10_minutes.strftime('%I:%M %p')}")
            sleep_progress((wait_10_minutes - datetime.now()).total_seconds())
            continue
    return url
