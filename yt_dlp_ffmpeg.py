import os
import re
import subprocess
from datetime import datetime, time, timedelta
from pathlib import Path
from time import sleep
from typing import Optional, cast

import requests
import yt_dlp


def get_episode_of_the_day() -> Optional[str]:
    """Devuelve la url del capitulo del dia actual"""
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
                )  # Se usa para comprobar que el titulo contenga la palabra "capitulo", en caso contrario dará error y saltara al siguiente video
                info = get_metadata(url)
                timestamp = datetime.fromtimestamp(info["timestamp"])
                is_today = timestamp.date() == datetime.now().date()
                if not is_today:
                    continue
                return url
            except Exception as e:
                continue


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


MEMORY = {}


def get_metadata(url) -> dict:
    if url in MEMORY:
        return MEMORY[url]

    with yt_dlp.YoutubeDL() as ydl:
        info_dict = cast(dict, ydl.extract_info(url, download=False))
        MEMORY[url] = info_dict
    return info_dict


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
    print(
        f"✅ Mejor video {target_height}p: format_id={best['format_id']}, bitrate={best['tbr']}k, ext={best['ext']}"
    )
    return best["format_id"]


def get_best_audio_format(url) -> str:
    info = get_metadata(url)
    formats = info["formats"].copy()
    # Filtrar formatos de audio que no tengan video
    candidates = [i for i in formats if i.get("video_ext", "") == "none"]
    candidates.sort(key=lambda x: x.get("filesize") or 0)
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
        print("Descargando audio...")
        info = cast(dict, ydl.extract_info(url, download=True))
        return info["requested_downloads"][0]["filepath"]


def merge_with_ffmpeg(video_path: str, audio_path: str, output: str) -> None:
    # TODO: Usar doble comillas para encerrar las ruta, solo funciona en windows
    if os.path.exists(output):
        print(f"El archivo {output} ya existe. Omitiendo fusión.")
        return

    print("Uniendo video y audio con FFmpeg...")
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
    print(f"Archivo final: {output}")


def cleanup(paths: list[str]) -> None:
    print("Limpiando archivos temporales...")
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


def sleep_progress(seconds):
    minutes = int(timedelta(seconds=seconds).total_seconds() // 60)

    print(f"Esperando {minutes} minutos antes de continuar...")
    count = 0
    for i in range(int(seconds), 0, -1):
        sleep(1)
        count += 1
        if count % 60 == 0:
            minutes -= 1
            print(f"Esperando {minutes} minutos antes de continuar...")


if __name__ == "__main__":
    nine_pm_today = datetime.combine(datetime.now().date(), time(21, 30))
    while True:
        if datetime.now() < nine_pm_today:
            difference = nine_pm_today - datetime.now()
            seconds = difference.total_seconds()
            sleep_progress(seconds)
            continue

        url = get_episode_of_the_day()
        if url is None:
            sleep_progress(120)
            continue

        config = {
            "SERIE_NAME": "desafio siglo xxi 2025",
            "URL": url,
            "QUALITIES": [720, 360],
            "OUTPUT_FOLDER": Path("output"),
        }
        filename_template = "{serie_name_normalized}.capitulo.{number}.yt.{quality}p{ext}"  # ext debe tener el punto

        video_paths = download_video(config)
        audio_path = download_audio(config)

        video_title = get_metadata(config["URL"])["title"]
        number = get_episode_number(video_title)
        serie_name_normalized = config["SERIE_NAME"].replace(" ", ".").lower()
        for quality, video_path in video_paths:
            ext = Path(video_path).suffix
            filename = filename_template.format(
                serie_name_normalized=serie_name_normalized,
                number=number,
                quality=quality,
                ext=ext,
            )
            output = str(config["OUTPUT_FOLDER"] / filename)
            merge_with_ffmpeg(video_path, audio_path, output)

        info = get_metadata(config["URL"])
        thumbnail = info.get("thumbnail", "")
        filename = f"{serie_name_normalized}.capitulo.{number}.yt.thumbnail.jpg"
        output = config["OUTPUT_FOLDER"] / filename
        if not output.exists():
            response = requests.get(thumbnail)
            with open(output, "wb") as f:
                f.write(response.content)

        # cleanup([video_path, audio_path])
        print("✅ Proceso completado.")
        break
