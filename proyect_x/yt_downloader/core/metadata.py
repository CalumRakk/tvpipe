"""
metadata.py
--------------
Manejo de caché y obtención de metadatos desde URLs usando `yt_dlp`.

Ideal para incluir funciones relacionadas con:
- Extracción de información de un video sin necesidad de descargarlo.
- Implementación de caché local para evitar solicitudes repetidas.
- Control de expiración del caché con base en tiempo (ej. 24 horas).
- Carga/guardado de información JSON desde disco.

Este módulo debe ser usado antes de cualquier descarga para planificarla correctamente.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, cast

import yt_dlp

logger = logging.getLogger(__name__)

CACHE_FILE = Path("meta/urls_cache.json")
CACHE: Dict[str, Dict[str, Any]] = {}


def load_url_cache():
    global CACHE
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r") as f:
            CACHE = json.load(f)
    else:
        CACHE = {}


def save_url_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(CACHE, f, indent=2)


def get_metadata(url: str) -> dict:
    load_url_cache()
    now = datetime.now()

    entry = CACHE.get(url)
    if entry:
        timestamp = datetime.fromisoformat(entry["timestamp"])
        if now - timestamp < timedelta(hours=24):
            return entry["info"]

    ydl_opts = {"quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = cast(dict, ydl.extract_info(url, download=False))

    CACHE[url] = {"timestamp": now.isoformat(), "info": info_dict}
    save_url_cache()
    return info_dict
