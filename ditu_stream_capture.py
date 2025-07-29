import logging
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import List

from unidecode import unidecode

from proyect_x.ditu.ditu import DituStream
from proyect_x.ditu.schemas.simple_schedule import SimpleSchedule
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


if __name__ == "__main__":

    setup_logging(f"logs/{Path(__file__).stem}.log")
    logger = logging.getLogger(__name__)

    ditu = DituStream()
    channel_info = ditu.channel.get_info("caracol")
    schedules = ditu.get_schedule(channel_info["channelId"])
    programs: List[SimpleSchedule] = [
        schedule
        for schedule in schedules
        if "Desafío Siglo XXI" in schedule.title
        or "Pre-Desafío" in schedule.title
        or "Post Desafío" in schedule.title
        or "Tour" in schedule.title
    ]

    for schule in programs:
        start_time = schule.start_time
        end_time = schule.end_time

        # if should_wait_for_publication(start_time):
        #     wait_release(start_time)
        #     print(
        #         f"Esperando hasta la hora de lanzamiento: {start_time.strftime('%I:%M %p')}"
        #     )
        # elif datetime.now() >= end_time:
        #     logger.info("El capítulo ya ha sido capturado.")
        #     continue

        logger.info(f"Publicando el capitulo: {schule.title}")
        output = ditu.capture_schedule(schule, "output/test")
