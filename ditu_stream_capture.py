import copy
import logging
from datetime import datetime, timedelta
from multiprocessing import Process
from pathlib import Path
from time import sleep
from typing import List, Set, Tuple, Union

from proyect_x.ditu.ditu import DituStream
from proyect_x.ditu.schemas.common import ChannelInfo
from proyect_x.ditu.schemas.simple_schedule import SimpleSchedule
from proyect_x.logging_config import setup_logging
from proyect_x.utils import normalize_windows_name, sleep_progress

# Configuracion
CHANNEL_NAME = "Desafio"
OUTPUT_DIR = "output/test"
CHECK_INTERVAL = 5  # segundos
REFRESH_INTERVAL = 20 * 60  # segundos (10 minutos)
TRIGGER_WINDOW = 5 * 60  # segundos (5 minutos antes del inicio)
MAX_PROCESSES = 2
CAPTURE_TIME_RANGES = ["01:28 pm - 01:31 pm", "1:46 pm - 1:50 pm"]


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


def capture_process(
    channel: ChannelInfo, range: Tuple[datetime, datetime], output_dir: Union[str, Path]
):
    time_start, time_end = range
    today_as_string = datetime.now().date()
    time_start_as_string = time_start.strftime("%I:%M%p").replace(":", "_")
    time_end_as_string = time_end.strftime("%I:%M%p").replace(":", "_")

    filename = f"{Path(__file__).stem}.{today_as_string}.{time_start_as_string}-{time_end_as_string}.log"
    filename_normal = normalize_windows_name(filename)
    setup_logging(f"logs/{filename_normal}")
    ditu = DituStream()
    output_dir = Path(output_dir) if isinstance(output_dir, str) else output_dir

    result = ditu.capture_schedule_range(channel, range, output_dir)
    ditu.combine_and_merge(result)


def filter_schedule_finished(schedules: List[SimpleSchedule]) -> List[SimpleSchedule]:
    return [s for s in schedules if s.end_time > datetime.now()]


def parse_time_ranges(time_ranges: list[str]) -> list[Tuple[datetime, datetime]]:
    results = []
    today = datetime.now().date()
    for range_string in time_ranges:
        range_string_normalized = range_string.replace(" ", "")
        start, end = range_string_normalized.split("-")
        start_obj = datetime.strptime(f"{today}-{start}", f"%Y-%m-%d-%I:%M%p")
        end_obj = datetime.strptime(f"{today}-{end}", f"%Y-%m-%d-%I:%M%p")
        results.append((start_obj, end_obj))
    return results


def is_valid_time_range(time_range: Tuple[datetime, datetime]) -> bool:
    start, end = time_range
    return start < end


def get_waiting_times(ranges: list[Tuple[datetime, datetime]]):
    waiting_times_map = []
    for start, end in ranges[:]:
        delta = start - datetime.now()
        # minutes= delta.total_seconds() / 60
        seconds = max(int(delta.total_seconds()), 0)
        waiting_times_map.append((seconds, start, end))
    waiting_times_map.sort(key=lambda x: x[0])
    return waiting_times_map


def warn_if_start_time_is_less_than_now(start_time: datetime):
    """Imprime Log de advertencia si la hora de inicio es menor a la hora actual."""
    logger = logging.getLogger(__name__)
    has_been_started = max(int((start_time - datetime.now()).total_seconds()), 0) > 60
    if has_been_started:
        logger.info(
            f"Se especifico la captura de inicio menor al tiempo actual: Captura: {start_time}, tiempo actual: {datetime.now()}"
        )


def run_supervisor():
    setup_logging(f"logs/{Path(__file__).stem}.log")
    logger = logging.getLogger(__name__)

    ditu = DituStream()
    manager = ProcessManager(MAX_PROCESSES)
    logger.info("🎬 Iniciando supervisor de capturas inteligentes...")

    ranges = parse_time_ranges(CAPTURE_TIME_RANGES).copy()
    if not all([is_valid_time_range(r) for r in ranges]):
        raise Exception("Invalid time ranges")

    start_done = set()
    channel = ditu.channel.get_info(CHANNEL_NAME)
    waiting_times = get_waiting_times(ranges)
    while len(waiting_times) > 0:
        if manager.can_start():
            for time_wait, start, end in waiting_times[:]:
                if end >= datetime.now():
                    sleep_progress(time_wait)
                    warn_if_start_time_is_less_than_now(start)
                    capture_process(channel, (start, end), OUTPUT_DIR)
                    start_done.add(start)
                else:
                    logger.info(
                        f"La captura especicada ya finalizo: Inicio: {start.isoformat()} | Finalizacion:{end.isoformat()}"
                    )
                    waiting_times.remove((time_wait, start, end))
        if len(waiting_times) > 0:
            logger.info(f"🕐 Esperando {CHECK_INTERVAL} segundos...")
            sleep_progress(CHECK_INTERVAL)
            manager.cleanup()
    logger.info("🎉 Finalizando supervisor de capturas inteligentes...")


if __name__ == "__main__":
    run_supervisor()
