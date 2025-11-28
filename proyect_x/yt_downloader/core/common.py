import logging
from time import sleep
from typing import Any, Dict

from proyect_x.yt_downloader.config import Settings as Config

logger = logging.getLogger(__name__)


def sleep_progress(seconds: float):
    total = int(seconds)
    if total <= 0:
        return

    logger.info(
        f"Esperando {total // 60} minutos y {total % 60} segundos antes de continuar..."
    )

    for i in range(total, 0, -1):
        sleep(1)
        if i % 60 == 0:
            mins_left = i // 60
            logger.info(f"Faltan {mins_left} minutos...")
        elif i <= 10:  # Mostrar segundos finales
            logger.info(f"{i} segundos restantes...")


def get_ytdl_base_opts(config: "Config", extra_opts: Dict[str, Any]) -> Dict[str, Any]:
    """Genera la configuración base para yt-dlp inyectando cookies si existen."""
    opts = {
        "quiet": True,
        "nocheckcertificate": True,
    }

    if config.youtube_cookies_path and config.youtube_cookies_path.exists():
        opts["cookiefile"] = str(config.youtube_cookies_path)
    else:
        logger.warning("No se ha configurado archivo de cookies o no existe.")

    if extra_opts:
        opts.update(extra_opts)

    return opts
