import logging
from time import sleep
from typing import Any, Dict

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


def get_ytdl_base_opts(extra_opts: Dict[str, Any]) -> Dict[str, Any]:
    """Genera la configuración base para yt-dlp inyectando cookies si existen."""
    opts = {
        "quiet": True,
        "nocheckcertificate": True,
    }

    if extra_opts:
        opts.update(extra_opts)

    return opts
