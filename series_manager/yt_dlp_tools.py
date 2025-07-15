import io
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
from typing import Optional, cast

import yt_dlp
from PIL import Image

PATH_DOWNLOAD_CACHE = Path("meta/downloaded.log")
MEMORY = {}
CACHE_FILE = Path("meta/metadata_cache.json")
CACHE = {}
logger = logging.getLogger(__name__)


def get_episode_of_the_day() -> Optional[str]:
    """Devuelve la url del capitulo del dia actual"""
    logger.info("Consiguiendo el episodio del día...")
    url = "https://www.youtube.com/@desafiocaracol/videos"
    ydl_opts = {
        "extract_flat": True,
        "playlistend": 5,
        "quiet": True,  # No imprime mensajes informativos
        "no_warnings": True,  # No muestra advertencias
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = cast(dict, ydl.extract_info(url, download=False))
        for entry in info["entries"]:
            try:
                title = entry["title"]
                url = entry["url"]
                number = get_episode_number(
                    title
                )  # Se usa para comprobar que el titulo contenga la palabra "capitulo", en caso contrario dará error a la siguiente url
                info = get_metadata(url)
                timestamp = datetime.fromtimestamp(info["timestamp"])
                is_today = timestamp.date() == datetime.now().date()
                is_live = info["was_live"]
                if is_today or is_live is False:
                    logger.info(f"✔️ Encontrado el episodio del dia: {title}")
                    return url
            except Exception as e:
                continue
        logger.info(f"❌ No se encontró el episodio del dia: {title}")


def get_episode_number(string) -> str:
    """
    Extrae el número de episodio de una cadena de texto.

    Esta función busca un patrón específico en la cadena de texto para identificar
    el número de episodio, que se espera esté precedido por la palabra "capítulo"
    Args:
        string (str): La cadena de texto de la que se extraerá el número de episodio.

    Raises:
        Exception: Si no se encuentra el número de episodio.

    Returns:
        str: El número de episodio extraído.
    """
    pattern = r"[Cc]ap[ií]tulo\s*([0-9]+)"
    match = re.search(pattern, string)
    if match:
        return match.group(1).zfill(2)
    raise Exception("No se encontró el número de episodio.")


def get_best_video_format(url, target_height: int) -> str:

    info = get_metadata(url)
    formats = info["formats"]

    # Obtener formatos de video con la altura deseada y sin audio (se espera concatenar audio después)
    candidates = [
        i
        for i in formats
        if i.get("height") == target_height and i.get("audio_ext", "") == "none"
    ]
    if not candidates:
        raise Exception(
            f"No se encontraron formatos de video con altura {target_height}p y sin audio."
        )

    candidates.sort(key=lambda x: x.get("filesize") or 0, reverse=True)
    best = candidates[0]
    logger.info(
        f"✅ Mejor video {target_height}p: format_id={best['format_id']}, bitrate={best['tbr']}k, ext={best['ext']}"
    )
    return best["format_id"]


def get_best_audio_format(url) -> str:
    info = get_metadata(url)
    formats = info["formats"].copy()
    # Filtrar formatos de audio que no tengan video
    candidates = [i for i in formats if i.get("resolution", "") == "audio only"]
    candidates.sort(key=lambda x: x.get("filesize") or 0, reverse=True)
    best = candidates[0]
    return best["format_id"]


def download_video(config: dict) -> list[tuple[int, str]]:
    url = config["URL"]
    qualities: list[int] = config["QUALITIES"]

    paths = []
    for quality in qualities:
        best_video_id = get_best_video_format(url, quality)
        output_folder = config["OUTPUT_FOLDER"] / "TEMP"
        output = f"{output_folder}/channel_id=%(channel_id)s&video_id=%(id)s&format_id=%(format_id)s&resolution=%(resolution)s.%(ext)s"

        ydl_opts_video = {
            "format": best_video_id,
            "outtmpl": output,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            info = cast(dict, ydl.extract_info(url, download=True))
            path: str = info["requested_downloads"][0]["filepath"]
            paths.append((quality, path))

    return paths


def download_audio(config) -> str:
    url = config["URL"]
    output_folder = config["OUTPUT_FOLDER"] / "TEMP"
    output = f"{output_folder}/channel_id=%(channel_id)s&video_id=%(id)s&format_id=%(format_id)s.%(ext)s"
    ydl_opts_audio = {"format": "bestaudio", "outtmpl": output, "continue_dl": True}

    with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
        logger.info("Descargando audio...")
        info = cast(dict, ydl.extract_info(url, download=True))
        return info["requested_downloads"][0]["filepath"]


def merge_with_ffmpeg(video_path: str, audio_path: str, output: str) -> None:
    # TODO: Usar doble comillas para encerrar las ruta, solo funciona en windows
    if os.path.exists(output):
        logger.info(f"El archivo {output} ya existe. Omitiendo fusión.")
        return

    logger.info("Uniendo video y audio con FFmpeg...")
    cmd = [
        "ffmpeg",
        "-i",
        video_path,
        "-i",
        audio_path,
        "-c:v",
        "copy",  # copiar video sin recodificar
        "-c:a",
        "aac",  # asegura compatibilidad de audio
        "-strict",
        "experimental",
        "-shortest",  # corta al stream más corto
        output,
    ]
    subprocess.run(cmd, check=True)
    logger.info(f"Archivo final: {output}")


def cleanup(paths: list[str]) -> None:
    logger.info("Limpiando archivos temporales...")
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


def sleep_progress(seconds):
    minutes = int(timedelta(seconds=seconds).total_seconds() // 60)

    logger.info(f"Esperando {minutes} minutos antes de continuar...")
    count = 0
    for i in range(int(seconds), 0, -1):
        sleep(1)
        count += 1
        if count % 60 == 0:
            minutes -= 1
            logger.info(f"Esperando {minutes} minutos antes de continuar...")


def download_media_item(url: str, format_id: str, output_folder: Path) -> str:
    """
    Descarga un único item (video o audio) usando un format_id específico.
    Esta función está diseñada para ser ejecutada en un proceso separado.
    """
    output_template = f"{output_folder}/%(id)s_{format_id}_%(resolution)s.%(ext)s"

    ydl_opts = {
        "format": format_id,
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 10,  # Reintentos en caso de fallo de red
        "fragment_retries": 10,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = cast(dict, ydl.extract_info(url, download=True))
        filepath = info["requested_downloads"][0]["filepath"]
        logger.info(f"✔️ Descarga completada: {Path(filepath).name}")
        return filepath


def get_download_jobs(config):
    download_jobs = []
    url = config["URL"]
    for quality in config["QUALITIES"]:
        format_id = get_best_video_format(url, quality)
        download_jobs.append(
            {"type": "video", "quality": quality, "format_id": format_id}
        )

    format_id = get_best_audio_format(url)
    download_jobs.append({"type": "audio", "quality": "best", "format_id": format_id})
    return download_jobs


def already_downloaded_today():
    today = datetime.now().strftime("%Y-%m-%d")
    if not PATH_DOWNLOAD_CACHE.exists():
        return False
    with open(PATH_DOWNLOAD_CACHE, "r") as f:
        for line in f:
            if today in line:
                return True
    return False


def register_download(number):
    today = datetime.now().strftime("%Y-%m-%d")
    with open(PATH_DOWNLOAD_CACHE, "a") as f:
        f.write(f"{today}: episodio {number}\n")


def load_cache():
    global CACHE
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r") as f:
            CACHE = json.load(f)
    else:
        CACHE = {}


def save_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(CACHE, f, indent=2)


def get_metadata(url: str) -> dict:
    load_cache()
    now = datetime.now()

    entry = CACHE.get(url)
    if entry:
        timestamp = datetime.fromisoformat(entry["timestamp"])
        if now - timestamp < timedelta(hours=24):
            return entry["info"]

    ydl_opts = {"quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = cast(dict, ydl.extract_info(url, download=False))

    # Actualizar cache
    CACHE[url] = {"timestamp": now.isoformat(), "info": info_dict}
    save_cache()
    return info_dict


def resize_and_compress_image(
    input_path, output_path, max_bytes, max_height=320, step=5, initial_quality=95
):
    """Redimensiona y compresiona una imagen JPEG.

    Args:
        input_path (str): Ruta de la imagen a redimensionar.
        output_path (str): Ruta de la imagen redimensionada y compresionada.
        max_bytes (int): Tamaño máximo en bytes de la imagen redimensionada y compresionada.
        max_height (int, optional): Altura máxima de la imagen redimensionada. Por defecto es 320.
        step (int, optional): Paso de calidad para la compresión. Por defecto es 5.
        initial_quality (int, optional): Calidad inicial para la compresión. Por defecto es 95.

    Example:
        resize_and_compress_image(
            input_path="thumbnail_watermarked.jpg",
            output_path="salida.jpg",
            max_bytes=50 * 1024,  # 50 KB
            max_height=320,
        )

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

        print(f"Calidad={quality} => {size} bytes")

        if size <= max_bytes:
            with open(output_path, "wb") as f:
                f.write(buffer.getvalue())
            print(f"Imagen guardada: {output_path} ({size} bytes)")
            break

        if quality - step >= 20:
            quality -= step
        else:
            print("No se pudo reducir más la calidad para alcanzar el tamaño deseado.")
            break
