import logging
from pathlib import Path

import cv2


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
    logger = logging.getLogger(__name__)
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        logger.error("Error al abrir el video")
        exit()

    logger.info("Obteniendo metadatos del video...")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = int(total_frames / fps)
    size = Path(video_path).stat().st_size
    size_mb = int(size / (1024 * 1024))

    cap.release()

    data = {
        "width": width,
        "height": height,
        "duration": duration,
        "size_mb": size_mb,
        "size": size,
        "path": video_path,
        "format_name": "HD" if width > 720 else "SD",
    }
    logger.info(f"Metadatos obtenidos: {data}")
    return data
