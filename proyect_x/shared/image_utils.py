"""
image_utils.py
----------------
Proporciona utilidades para el tratamiento de imágenes, especialmente para compresión de thumbnails.

Ideal para incluir funciones relacionadas con:
- Redimensionamiento de imágenes para limitar altura o tamaño en bytes.
- Compresión progresiva ajustando la calidad JPEG.
- Validación del tamaño final y escritura optimizada al disco.

Este módulo es útil para asegurar que las miniaturas cumplan requisitos de tamaño antes de su uso o publicación.
"""

import io
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def resize_and_compress_image(
    input_path: str | Path,
    output_path: str | Path,
    max_bytes: int,
    max_height: int = 320,
    step: int = 5,
    initial_quality: int = 95,
):
    """Redimensiona y comprime una imagen JPEG.

    Args:
        input_path (str | Path): Ruta de la imagen a redimensionar.
        output_path (str | Path): Ruta de salida.
        max_bytes (int): Tamaño máximo en bytes.
        max_height (int): Altura máxima de la imagen. Default 320.
        step (int): Paso de compresión. Default 5.
        initial_quality (int): Calidad inicial. Default 95.
    """
    img = Image.open(input_path)

    width, height = img.size
    if height > max_height:
        scale = max_height / height
        width = int(width * scale)
        height = max_height
        img = img.resize((width, height), Image.LANCZOS)  # type: ignore

    quality = initial_quality

    while True:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        size = buffer.tell()

        logger.info(f"Calidad={quality} => {size} bytes")

        if size <= max_bytes:
            with open(output_path, "wb") as f:
                f.write(buffer.getvalue())
            logger.info(f"Imagen guardada: {output_path} ({size} bytes)")
            break

        if quality - step >= 20:
            quality -= step
        else:
            logger.info(
                "No se pudo reducir más la calidad para alcanzar el tamaño deseado."
            )
            break
