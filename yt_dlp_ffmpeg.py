import os
import re
import subprocess
from pathlib import Path
from typing import Optional, cast

import yt_dlp


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
        return match.group(1)
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


def build_name_stem(serie_name, url, quality) -> str:
    info = get_metadata(url)
    number = get_episode_number(info["title"]).zfill(2)
    serie_name_normalized = serie_name.replace(" ", ".").lower()
    return f"{serie_name_normalized}.capitulo.{number}.yt.{quality}p"


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


if __name__ == "__main__":

    config = {
        "SERIE_NAME": "desafio siglo xxi 2025",
        "URL": "https://www.youtube.com/watch?v=Z-rketUJeRg",
        "QUALITIES": [720, 480],
        "OUTPUT_FOLDER": Path("output"),
    }

    video_paths = download_video(config)
    audio_path = download_audio(config)

    for quality, video_path in video_paths:
        serie_name = config["SERIE_NAME"]
        url = config["URL"]
        stem = build_name_stem(serie_name, url, quality)
        output = str(config["OUTPUT_FOLDER"] / f"{stem}.mp4")
        merge_with_ffmpeg(video_path, audio_path, output)

    # cleanup([video_path, audio_path])
    print("✅ Proceso completado.")
