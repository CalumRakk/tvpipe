import json
import logging
import time
from datetime import datetime, time, timedelta
from pathlib import Path

from config import STREAM_CAPTURE_END_TIME, STREAM_CAPTURE_START_TIME
from logging_config import setup_logging
from series_manager.caracoltv import CaracolTV
from series_manager.ditu import main as ditu_main_yield
from series_manager.yt_dlp_tools import load_download_cache as load_cache_episode
from yt_dlp_ffmpeg import RELEASE_MODE, sleep_progress, wait_until_release

PATH_DOWNLOADED_STREAM = Path("meta/downloaded_stream.json")
FOLDER_OUTPUT = Path(r"output/live_downloads/ditu")


def should_skip_today(today):
    """Determina si se debe omitir la descarga del capítulo hoy."""
    if today.weekday() >= 5:
        logger.info("Hoy es fin de semana. No hay capítulo.")
        return True

    stream_cache = load_registered_stream()
    today_str = today.strftime("%Y-%m-%d")
    if today_str in stream_cache:
        logger.info("✅ El Stream de hoy ya fue descargado.")
        return True
    return False


def determine_number_episode():
    """Determina el número del episodio actual basado en el cache de descargas."""
    # TODO: Funcion acoplata al cache de descargas. Deberia buscar otro metodo para obtener el numero del capitulo.
    today = datetime.now().date() - timedelta(days=1)
    download_cache = load_cache_episode()
    today_str = today.strftime("%Y-%m-%d")
    last_episode = download_cache[today_str]
    episode_number = last_episode.replace("capitulo", "").strip()
    return int(episode_number) + 1


def register_download(number):
    """Registra la descarga del steam"""
    today = datetime.now().date()
    if PATH_DOWNLOADED_STREAM.exists():
        data = json.loads(PATH_DOWNLOADED_STREAM.read_text())
        data[str(today)] = f"capitulo {number}"
    else:
        PATH_DOWNLOADED_STREAM.parent.mkdir(parents=True, exist_ok=True)
        data = {str(today): f"capitulo {number}"}
    PATH_DOWNLOADED_STREAM.write_text(json.dumps(data, indent=4))


def load_registered_stream():
    """Carga el cache de descargas de stream."""
    if PATH_DOWNLOADED_STREAM.exists():
        return json.loads(PATH_DOWNLOADED_STREAM.read_text())
    return {}


def get_stream_capture_times(mode) -> tuple[datetime, datetime]:
    """Obtiene la hora de inicio y fin de la captura del stream.

    returns:
        datetime: Hora de inicio de la captura del stream.
        datetime: Hora de fin de la captura del stream.
    """
    start_time = datetime.combine(datetime.now().date(), STREAM_CAPTURE_START_TIME)
    end_time = datetime.combine(datetime.now().date(), STREAM_CAPTURE_END_TIME)
    if mode == RELEASE_MODE.AUTO:
        caractol = CaracolTV()
        schedule = caractol.get_schedule_desafio()
        if schedule:
            start_time = schedule["starttime"] - timedelta(minutes=5)
            end_time = schedule["endtime"] + timedelta(minutes=5)
            return start_time, end_time
        raise ValueError("No se encontró la programación del desafío.")
    return start_time, end_time


if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")
    logger = logging.getLogger(__name__)
    logger.info("Iniciando captura del stream de Caracol TV")

    # --- CONFIGURACION ---
    serie_name = "desafio.siglo.xxi.2025"
    mode = RELEASE_MODE.AUTO

    start_time, end_time = get_stream_capture_times(mode)
    while True:
        logger.info(f"Capturando empieza a las: {start_time.strftime('%I:%M %p')}")

        today = datetime.now()
        if should_skip_today(today):
            end_of_day = datetime.combine(today.date(), time(23, 59, 59))
            sleep_progress((end_of_day - today).total_seconds())
            continue

        if wait_until_release(today, start_time) and mode is RELEASE_MODE.AUTO:
            start_time, end_time = get_stream_capture_times(mode)
            logger.info(f"Hora de lanzamiento actualizada.")
            continue

        number = determine_number_episode()
        folder_name = f"{serie_name}.capitulo.{number}.ditu.1080p"  #
        folder_output = FOLDER_OUTPUT / folder_name
        folder_output.mkdir(parents=True, exist_ok=True)
        for _ in ditu_main_yield(folder_output):
            logger.info(f"Capturando termina a las: {end_time.strftime('%I:%M %p')}")
            if (
                end_time < datetime.now()
                and get_stream_capture_times(mode)[1] < datetime.now()
            ):
                register_download(number)
                logger.info(f"✅ Capítulo {number} capturado.")
                break

    # FIXME: Recuerda almacenar los master obtenidos que almacena supervisor ya que tiene un limite de tamaño.
