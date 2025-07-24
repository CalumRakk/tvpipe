import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)
import subprocess


def is_combination_valid(container: str, vcodec: str, acodec: str) -> bool:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",  # muestra solo errores
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=128x128:rate=1",  # fuente de video
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000",  # fuente de audio
        "-t",
        "1",  # duración: 1 segundo
        "-c:v",
        vcodec,
        "-c:a",
        acodec,
        "-f",
        container,
        "-y",  # sobrescribe archivo de salida si existe
        "dummy_output." + container,
    ]

    try:
        subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


# Ejemplos de uso
if __name__ == "__main__":
    combos = [
        ("mp4", "libx264", "aac"),
        ("webm", "libvpx", "libvorbis"),
        ("webm", "libx264", "aac"),  # inválido
        ("mkv", "libx264", "aac"),
    ]

    for container, vcodec, acodec in combos:
        result = is_combination_valid(container, vcodec, acodec)
        print(
            f"{container} | vcodec: {vcodec:10s} | acodec: {acodec:10s} -> {'✅ Válido' if result else '❌ Inválido'}"
        )


def load_stream_delay():

    path = Path("meta/stream_delay.json")
    if not path.exists():
        return timedelta(0)
    try:
        data = json.loads(path.read_text())
        if data["date"] == datetime.now().strftime("%Y-%m-%d"):
            return timedelta(minutes=int(data.get("delay_minutes", 0)))
    except Exception as e:
        logger.warning(f"No se pudo leer el retraso: {e}")
    return timedelta(0)


def get_video_metadata(video_path: str) -> dict:
    """Devuelve un diccionario con los siguientes campos:
    {
        "width": width,
        "height": height,
        "duration": duration,
        "thumb": str(temp_folder),
        "size_mb": size_mb
    }
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("Error al abrir el video")
        exit()

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = int(total_frames / fps)
    size = Path(video_path).stat().st_size
    size_mb = int(size / (1024 * 1024))

    cap.release()
    return {
        "width": width,
        "height": height,
        "duration": duration,
        "size_mb": size_mb,
        "size": size,
        "path": video_path,
        "format_name": "HD" if width > 720 else "SD",
    }
