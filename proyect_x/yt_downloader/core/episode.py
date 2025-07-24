"""
episode.py
------------
Contiene la lógica relacionada con la gestión de episodios diarios (e.g., de una serie en YouTube).

Ideal para incluir funciones relacionadas con:
- Detección del episodio del día a partir de una URL base (e.g., canal de YouTube).
- Extracción del número de episodio desde los títulos.
- Verificación de si un episodio ya ha sido descargado previamente.
- Registro de episodios descargados en archivos de cache locales.
- Lógica de omisión de fines de semana o días sin capítulos.

Este módulo ayuda a automatizar la lógica de lanzamientos periódicos.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, cast

from .metadata import get_metadata

logger = logging.getLogger(__name__)

DAILY_EPISODE_LOG_PATH = Path("meta/downloaded_episode_releases.json")


def get_episode_of_the_day() -> Optional[str]:
    logger.info("Consiguiendo el episodio del día...")
    url = "https://www.youtube.com/@desafiocaracol/videos"
    ydl_opts = {
        "extract_flat": True,
        "playlistend": 5,
        "quiet": True,
        "no_warnings": True,
    }
    import yt_dlp  # import aquí para evitar dependencia circular si usas `yt_dlp` en múltiples módulos

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = cast(dict, ydl.extract_info(url, download=False))
        for entry in info["entries"]:
            try:
                title = entry["title"]
                url = entry["url"]
                number = get_episode_number(title)
                info = get_metadata(url)
                timestamp = datetime.fromtimestamp(info["timestamp"])
                is_today = timestamp.date() == datetime.now().date()
                is_live = info.get("was_live")
                if is_today or is_live is False:
                    logger.info(f"✔️ Encontrado el episodio del dia: {title}")
                    return url
            except Exception:
                continue
        logger.info(f"❌ No se encontró el episodio del dia: {title}")


def get_episode_number(string: str) -> str:
    pattern = r"[Cc]ap[ií]tulo\s*([0-9]+)"
    match = re.search(pattern, string)
    if match:
        return match.group(1).zfill(2)
    raise Exception("No se encontró el número de episodio.")


def already_downloaded_today() -> bool:
    downloads = load_download_cache()
    today = str(datetime.now().date())
    return any(today in d for d in downloads)


def register_download(number: str):
    today = str(datetime.now().date())
    if DAILY_EPISODE_LOG_PATH.exists():
        downloads = json.loads(DAILY_EPISODE_LOG_PATH.read_text())
        downloads.append({today: str(number)})
        DAILY_EPISODE_LOG_PATH.write_text(json.dumps(downloads))
    else:
        DAILY_EPISODE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = [{today: str(number)}]
        DAILY_EPISODE_LOG_PATH.write_text(json.dumps(data))


def load_download_cache() -> list[dict]:
    if not DAILY_EPISODE_LOG_PATH.exists():
        return []
    return json.loads(DAILY_EPISODE_LOG_PATH.read_text())


def is_episode_downloaded(ep_number: str) -> bool:
    downloads = load_download_cache()
    return any(ep_number in d.values() for d in downloads)
