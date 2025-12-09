import hashlib
import logging
import re
from pathlib import Path
from time import sleep
from typing import Optional, Union

import filetype
import requests

logger = logging.getLogger(__name__)


def normalize_windows_name(name: str) -> str:
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
    name = re.sub(invalid_chars, "_", name)
    name = name.rstrip(" .")
    if len(name) < 0:
        raise ValueError("Invalid name")
    return name


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


def create_md5sum_by_hashlib(path: Union[str, Path]) -> str:
    path = Path(path) if isinstance(path, str) else path
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(50 * 1024 * 1024), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_mimetype(path: Path):
    path = Path(path) if isinstance(path, str) else path
    logger.debug(f"Obteniendo el mimetype para {path=}")
    for _ in range(3):
        kind = filetype.guess(str(path))
        logger.debug(f"El mimetype para {path=} es {kind=}")
        if kind is None:
            sleep(1)
            continue
        return kind.mime


def download_thumbnail(url: Optional[str], output_path: Path) -> Path:
    if not url:
        logger.warning("No hay URL de miniatura disponible.")
        return output_path

    if output_path.exists():
        return output_path

    try:
        logger.info("Descargando miniatura...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
    except Exception as e:
        logger.error(f"Error descargando miniatura: {e}")

    return output_path
