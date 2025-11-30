import logging
import subprocess
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def merge_video_audio(video_path: Path, audio_path: Path, output_path: Path):
    """Fusiona video y audio usando ffmpeg."""
    if output_path.exists():
        logger.warning(f"El archivo final ya existe: {output_path}")
        return

    logger.info("Fusionando audio y video con FFmpeg...")
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True)
        logger.info(f"Fusión completada: {output_path.name}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error en FFmpeg: {e}")
        raise

    # Limpieza básica opcional (o dejarla al orquestador)
    # video_path.unlink(missing_ok=True)
    # audio_path.unlink(missing_ok=True)


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
