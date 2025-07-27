import logging
from datetime import datetime, time, timedelta
from pathlib import Path

from unidecode import unidecode

from proyect_x.ditu.ditu import Ditu
from proyect_x.ditu.ditu_stream import ditu_main_yield
from proyect_x.ditu.schemas import SimpleSchedule
from proyect_x.logging_config import setup_logging
from proyect_x.yt_downloader.core.common import sleep_progress


def get_target(
    targets: list[str],
    schedules: list[SimpleSchedule],
):
    candicates = []
    for schedule in schedules:
        for target in targets:
            if unidecode(target).lower() in unidecode(schedule.title).lower():
                candicates.append(schedule)
    return candicates


def should_wait_for_publication(start_time: datetime):
    """Espera hasta la hora de lanzamiento del capítulo (especificada en release_time)."""
    today = datetime.now()
    if today < start_time:
        return True
    return False


def wait_release(start_time: datetime):
    """Espera hasta la hora de lanzamiento del capítulo (especificada en release_time)."""
    today = datetime.now()
    difference = start_time - today
    logger.info(
        f"Hora de publicacion del capitulo en youtube: {start_time.strftime('%I:%M %p')}"
    )
    sleep_progress(difference.total_seconds())
    return False


ditu = Ditu()
schudules = ditu.get_schedule_for_desafio()
filter = get_target(["Desafio"], schudules)
setup_logging(f"logs/{Path(__file__).stem}.log")
logger = logging.getLogger(__name__)
for schule in filter:
    start_time = schule.start_time
    end_time = schule.end_time

    if should_wait_for_publication(start_time):
        wait_release(start_time)
        print(
            f"Esperando hasta la hora de lanzamiento: {start_time.strftime('%I:%M %p')}"
        )
    elif datetime.now() >= end_time:
        logger.info("El capítulo ya ha sido capturado.")
        continue

    title = schule.title
    title_slug = unidecode(title).lower().replace(" ", ".")
    number = schule.episode_number
    start = schule.start_time.strftime("%Y_%m_%d.%I_%M.%p")
    end = schule.end_time.strftime("%I.%M.%p")
    folder_name = f"{title_slug}.capitulo.{number}.ditu.live.1080p.{start}"
    output = Path("output/test") / folder_name
    output.parent.mkdir(parents=True, exist_ok=True)
    for _ in ditu_main_yield(output):
        logger.info(f"Capturando termina a las: {end_time.strftime('%I:%M %p')}")

        if datetime.now() >= end_time:
            break
