import copy
import logging
import time
from datetime import datetime
from multiprocessing import Process
from pathlib import Path
from typing import List, Set

from proyect_x.ditu.ditu import DituStream
from proyect_x.ditu.schemas.simple_schedule import SimpleSchedule
from proyect_x.logging_config import setup_logging

# Configuracion
CHANNEL_NAME = "Club"
OUTPUT_DIR = "output/test"
CHECK_INTERVAL = 10  # segundos
REFRESH_INTERVAL = 10 * 60  # segundos (10 minutos)
TRIGGER_WINDOW = 5 * 60  # segundos (5 minutos antes del inicio)
MAX_PROCESSES = 2


class ProcessManager:
    def __init__(self, max_workers: int = 2):
        self.max_workers = max_workers
        self.active: List[Process] = []

    def cleanup(self):
        self.active = [p for p in self.active if p.is_alive()]

    def can_start(self):
        self.cleanup()
        return len(self.active) < self.max_workers

    def start(self, func, *args):
        if self.can_start():
            p = Process(target=func, args=args)
            p.start()
            self.active.append(p)
            return True
        return False


def fetch_updated_schedules(ditu: DituStream, channel_id: int) -> List[SimpleSchedule]:
    logger = logging.getLogger(__name__)
    logger.info("🔄 Actualizando programación del canal...")
    return ditu.get_schedule(channel_id)


def update_schedule_list(
    current: List[SimpleSchedule], new: List[SimpleSchedule]
) -> List[SimpleSchedule]:
    updated_map = {s.content_id: s for s in new}
    current_map = {s.content_id: s for s in current}

    for cid, schedule in updated_map.items():
        current_map[cid] = schedule

    return list(current_map.values())


def capture_process(schedule: SimpleSchedule):
    ditu = DituStream()
    logger = logging.getLogger(__name__)
    logger.info(f"📡 Iniciando captura: {schedule.title}")
    result = ditu.capture_schedule(schedule, OUTPUT_DIR)
    ditu.combine_and_merge(result)
    logger.info(f"✅ Captura finalizada: {schedule.title}")


def filter_schedule_finished(schedules: List[SimpleSchedule]) -> List[SimpleSchedule]:
    return [s for s in schedules if s.end_time > datetime.now()]


def run_supervisor():
    setup_logging(f"logs/{Path(__file__).stem}.log")
    logger = logging.getLogger(__name__)

    ditu = DituStream()
    channel_info = ditu.channel.get_info(CHANNEL_NAME)
    channel_id = channel_info["channelId"]

    schedules = fetch_updated_schedules(ditu, channel_id)
    captured_ids: Set[int] = set()
    manager = ProcessManager(MAX_PROCESSES)

    logger.info("🎬 Iniciando supervisor de capturas inteligentes...")

    while True:
        # if time.time() - last_refresh >= REFRESH_INTERVAL:
        #     new_schedules = fetch_updated_schedules(ditu, channel_id)
        #     schedules = update_schedule_list(schedules, new_schedules)
        #     last_refresh = time.time()

        manager.cleanup()

        if manager.can_start():
            for schedule in filter_schedule_finished(schedules):
                if schedule.content_id in captured_ids:
                    continue

                if schedule.has_started:
                    logger.info(f"🚀 Lanzando proceso de captura: {schedule.title}")
                    schedule_copy = copy.deepcopy(schedule)
                    manager.start(capture_process, schedule_copy)
                    captured_ids.add(schedule.content_id)
                    break
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_supervisor()
