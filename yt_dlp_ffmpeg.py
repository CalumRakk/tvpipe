import os
import re
import subprocess
from pathlib import Path

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


def download_video_and_audio(URL):
    ydl_opts_video = {
        "format": f"bestvideo[height={TARGET_HEIGHT}]",
        "outtmpl": VIDEO_FILE,
    }
    ydl_opts_audio = {"format": "bestaudio", "outtmpl": AUDIO_FILE}

    with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
        print(f"Descargando video {TARGET_HEIGHT}p...")
        ydl.download([VIDEO_URL])

    with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
        print("Descargando audio...")
        ydl.download([VIDEO_URL])


def get_metadata(url) -> dict:
    if url in MEMORY:
        return MEMORY[url]

    with yt_dlp.YoutubeDL() as ydl:
        info_dict = ydl.extract_info(url, download=False)
        MEMORY[url] = info_dict
    return info_dict


def get_best_video_format(url, target_height: int) -> str:

    info = get_metadata(url)
    formats = info["formats"]

    # Filtrar: video-only, height == target_height, con bitrate
    candidates = [
        f
        for f in formats
        if f.get("height") == target_height
        and f.get("vcodec") != "none"
        and f.get("acodec") == "none"
    ]

    if not candidates:
        raise Exception(f"No se encontró video con resolución {target_height}p")

    # Ordenar por bitrate descendente
    best = max(candidates, key=lambda f: f.get("tbr") or 0)
    print(
        f"✅ Mejor video {target_height}p: format_id={best['format_id']}, bitrate={best['tbr']}k, ext={best['ext']}"
    )
    return best["format_id"]


def download_video(config: dict):
    url = config["URL"]
    quality = config["QUALITY"]
    serie_name = config["SERIE_NAME"]
    output_folder = Path(config["OUTPUT_FOLDER"])

    info = get_metadata(url)
    best_video_id = get_best_video_format(url, quality)
    number = get_episode_number(info["title"]).zfill(2)
    serie_name_normalized = serie_name.replace(" ", ".").lower()
    name = f"{serie_name_normalized}.capitulo.{number}.yt.{quality}p"

    output = output_folder / "TEMP" / f"{name}.%(ext)s"

    ydl_opts_video = {
        "format": best_video_id,
        "outtmpl": str(output),
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
        ydl.download([url])
    return output


def merge_with_ffmpeg():
    print("Uniendo video y audio con FFmpeg...")
    cmd = [
        "ffmpeg",
        "-i",
        VIDEO_FILE,
        "-i",
        AUDIO_FILE,
        "-c:v",
        "copy",  # copiar video sin recodificar
        "-c:a",
        "aac",  # asegura compatibilidad de audio
        "-strict",
        "experimental",
        "-shortest",  # corta al stream más corto
        OUTPUT_FILE,
    ]
    subprocess.run(cmd, check=True)
    print(f"Archivo final: {OUTPUT_FILE}")


def cleanup():
    print("Limpiando archivos temporales...")
    for f in [VIDEO_FILE, AUDIO_FILE]:
        if os.path.exists(f):
            os.remove(f)


if __name__ == "__main__":
    SERIE_NAME = "desafio siglo xxi 2025"
    URL = "https://www.youtube.com/watch?v=Ho4LmkE2fBA"
    QUALITY = 720
    OUTPUT_FOLDER = "output"

    config = {
        "SERIE_NAME": SERIE_NAME,
        "URL": URL,
        "QUALITY": QUALITY,
        "OUTPUT_FOLDER": OUTPUT_FOLDER,
    }

    video_path = download_video(config)
    # audio_path = download_audio(config)
    # merge_with_ffmpeg(video_path, audio_path)

    # cleanup([video_path, audio_path])
    print("✅ Proceso completado.")
