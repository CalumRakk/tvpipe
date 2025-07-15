import json
import logging
import time
from datetime import datetime, time, timedelta
from pathlib import Path
from time import sleep
from typing import cast
from urllib.parse import urlparse

import requests

from logging_config import setup_logging
from series_manager.caracolstream import CaracolLiveStream
from series_manager.yt_dlp_tools import load_download_cache as load_cache_episode
from yt_dlp_ffmpeg import sleep_progress, wait_until_release


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


PATH_DOWNLOADED_STREAM = Path("meta/downloaded_stream.json")
setup_logging(f"logs/{Path(__file__).stem}.log")
logger = logging.getLogger(__name__)

# --- CONFIGURACION ---
serie_name = "desafio.siglo.xxi.2025"
number = determine_number_episode()
FOLDER_OUTPUT = Path(r"output/live_downloads/caracoltv")
release_time = datetime.combine(datetime.now().date(), time(19, 55))  # 7:55 PM
end_time = datetime.combine(datetime.now().date(), time(21, 45, 59))  # 9:45 PM

# --- DESCARGA ---
caracol = CaracolLiveStream()
FOLDER_NAME_TEMPLATE = "{serie_name}.capitulo.{number}.steam.{format_note}"
while True:
    today = datetime.now()
    end_of_day = datetime.combine(today.date(), time(23, 59, 59))

    if should_skip_today(today):
        sleep_progress((end_of_day - today).total_seconds())
        continue

    if wait_until_release(today, release_time):
        continue

    if today > end_time:
        logger.info("La transmision del capítulo de hoy ya ha finalizado.")
        register_download(number)
        sleep_progress((end_of_day - today).total_seconds())
        continue

    playlist = caracol.fetch_best_playlist(include_resolution=True)
    format_note = playlist.format_note  # type: ignore
    folder_name = FOLDER_NAME_TEMPLATE.format(
        serie_name=serie_name, number=number, format_note=format_note
    )
    folder_output = FOLDER_OUTPUT / folder_name
    folder_output.mkdir(parents=True, exist_ok=True)
    for url in [url for url in cast(str, playlist.files)]:
        parsed = urlparse(url)
        filename = Path(parsed.path).name  # type: ignore

        output = folder_output / filename
        if output.exists():
            logger.info("Skipping " + filename)
            continue

        logger.info("Downloading " + filename)
        response = requests.get(url)
        response.raise_for_status()
        output.write_bytes(response.content)
    sleep(20)
