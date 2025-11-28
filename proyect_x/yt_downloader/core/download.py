"""
download.py
-------------
Contiene funciones para realizar descargas de medios (audio/video) y manipular los archivos resultantes.

Ideal para incluir funciones relacionadas con:
- Descarga directa de video o audio desde una URL con un `format_id` específico.
- Fusión de streams de video y audio usando `ffmpeg`.
- Limpieza de archivos temporales después de la descarga.
- Visualización del progreso de descarga en consola.

Este módulo se enfoca en la ejecución directa del proceso de descarga y postprocesamiento.
"""

import logging
import math
import os
import subprocess
from pathlib import Path
from time import sleep
from typing import Union, cast

import yt_dlp

logger = logging.getLogger(__name__)


def download_audio(config) -> str:
    url = config["URL"]
    download_folder = config["download_folder"] / "TEMP"
    output = f"{download_folder}/channel_id=%(channel_id)s&video_id=%(id)s&format_id=%(format_id)s.%(ext)s"
    ydl_opts_audio = {
        "format": "bestaudio",
        "outtmpl": output,
        "continue_dl": True,
        "cookiefile": r"C:\Users\Leo\Downloads\www.youtube.com_cookies.txt",
    }

    with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
        logger.info("Descargando audio...")
        info = cast(dict, ydl.extract_info(url, download=True))
        return info["requested_downloads"][0]["filepath"]


def merge_with_ffmpeg(
    video_path: Union[str, Path], audio_path: Union[str, Path], output: Union[str, Path]
) -> None:
    if os.path.exists(output):
        logger.info(f"El archivo {output} ya existe. Omitiendo fusión.")
        return

    logger.info("Uniendo video y audio con FFmpeg...")
    cmd = [
        "ffmpeg",
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
        "-shortest",
        str(output),
    ]
    subprocess.run(cmd, check=True)
    logger.info(f"Archivo final: {output}")


def cleanup(paths: list[str]) -> None:
    logger.info("Limpiando archivos temporales...")
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


def my_progress_hook(d):
    path = Path(d.get("filename"))
    if d["status"] == "downloading":
        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
        downloaded = d.get("downloaded_bytes", 0)
        if total_bytes:
            percent = downloaded / total_bytes * 100
            step = 10
            current_step = math.floor(percent / step) * step
            if (
                not hasattr(my_progress_hook, "last_step")
                or current_step != my_progress_hook.last_step
            ):
                my_progress_hook.last_step = current_step
                print(f"{path.name} descargando: {current_step}%")
    elif d["status"] == "finished":
        print(f"{path.name} Descarga completada.")
