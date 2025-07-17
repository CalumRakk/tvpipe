import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)


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
