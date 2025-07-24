import io
import json
import logging
import math
import os
import re
import subprocess
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    TypedDict,
    Union,
    cast,
    get_args,
)

import yt_dlp
from PIL import Image
from yt_dlp.utils import DownloadError

from series_manager.schemes import DownloadJob

from .exceptions import QualityNotFoundError
from .schemes import (
    KLABEL_MAP,
    YOUTUBE_AUDIO_CODECS,
    YOUTUBE_VIDEO_CODECS,
    KLabel,
    QualityAlias,
)

PATH_DOWNLOAD_CACHE = Path("meta/downloaded_episode_releases.json")
MEMORY = {}
CACHE_FILE = Path("meta/urls_cache.json")
CACHE = {}
logger = logging.getLogger(__name__)


def is_youtube_audio_codec(acodec: str) -> bool:
    if not acodec:
        return False
    prefix = acodec.split(".")[0].lower()
    return prefix in YOUTUBE_AUDIO_CODECS


def is_youtube_video_codec(vcodec: str) -> bool:
    if not vcodec:
        return False
    prefix = vcodec.split(".")[0].lower()
    return prefix in YOUTUBE_VIDEO_CODECS


def is_mp4_compatible(vcodec: str, acodec: str) -> bool:
    """Verifica si los codec de video y audio son compatibles para merge directo a .mp4."""

    # Solo puedes hacer merge directo a .mp4 si los códecs son H.264 (avc1) y AAC (mp4a).
    # Youtube manera solo tres vcodec: av01,avc1, vp09 y vp9
    vcodec = vcodec.lower()
    acodec = acodec.lower()

    return vcodec.startswith("avc1") and (acodec.startswith("mp4a") or acodec == "mp3")


def resolve_quality_alias(alias: str, formats: list[dict]) -> int | None:
    """Devuelve el formato con la calidad indicada por alias."""
    if not formats:
        return None
    elif alias not in get_args(QualityAlias):
        return None

    candicates = [i for i in formats if i.get("vbr")]
    sorted_candidates = sorted(candicates, key=lambda q: q["height"])

    match alias.lower():
        case "low":
            return sorted_candidates[0]["height"]
        case "medium":
            if len(sorted_candidates) >= 3:
                # Tomamos la mediana
                return sorted_candidates[len(sorted_candidates) // 2]["height"]
            else:
                # No hay suficiente formatos, asi que tomamos el primero
                return sorted_candidates[0]["height"]
        case "best":
            return sorted_candidates[-1]["height"]

    return None


def resolve_quality_label(label: str) -> int | None:
    """Devuelve la resolución indicada por label."""
    label = label.lower().strip()
    # Primero: intenta con la constante
    # Segundo: intenta extraer número del tipo "4320p"
    if label in get_args(KLabel):
        return KLABEL_MAP[label]

    match = re.fullmatch(r"(\d+)\s*p", label)
    if match:
        return int(match.group(1))

    return None


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


def get_format_type(fmt):
    if fmt.get("vcodec") == "none" and fmt.get("acodec") != "none":
        return "audio"
    elif fmt.get("acodec") == "none" and fmt.get("vcodec") != "none":
        return "video"
    elif fmt.get("vcodec") != "none" and fmt.get("acodec") != "none":
        return "video+audio"
    else:
        return "unknown"


def is_format_untested(fmt):
    return not all([fmt["format_id"], fmt.get("format_note"), fmt.get("protocol")])


def get_best_video_combinations(
    formats: list[dict], quality: Union[int, str], output_as_mp4: bool
) -> list[tuple[str, str]]:
    """
    Devuelve combinaciones de format_id de video y audio en orden de mejor calidad a menor,
    filtradas por calidad deseada y compatibilidad con MP4 si se indica.
    """
    # Resuelve altura especificada por quality
    if isinstance(quality, int):
        target_height = quality
    elif quality in get_args(QualityAlias):
        target_height = resolve_quality_alias(quality, formats)
    elif str(quality).isdigit():
        target_height = int(quality)
    else:
        target_height = resolve_quality_label(quality)

    # Filtrar formatos de solo video que coincidan con la altura deseada
    video_formats = [
        fmt
        for fmt in formats
        if get_format_type(fmt) == "video"
        and fmt.get("height") == target_height
        and not is_format_untested(fmt)
    ]

    if output_as_mp4:
        video_formats = [
            fmt for fmt in video_formats if "avc1" in fmt.get("vcodec", "")
        ]

    if not video_formats:
        raise QualityNotFoundError(
            f"No se encontró un formato de video con la calidad especificada: {quality}"
        )

    # Ordenar por bitrate descendente
    video_formats.sort(key=lambda x: x.get("vbr") or 0, reverse=True)

    # Generar combinaciones  (video_id, audio_id) y si se especifica `output_as_mp4` las combinaciones las selecciona compatibles
    combinations = []
    for video_fmt in video_formats:
        if output_as_mp4:
            vc = video_fmt["vcodec"]
            audio_formats = get_compatible_audio_formats_for_mp4(vc, formats)
        else:
            audio_formats = get_audio_formats_sorted(formats)
        for audio_fmt in audio_formats:
            combinations.append((video_fmt["format_id"], audio_fmt["format_id"]))
    return combinations


def get_audio_formats_sorted(formats: list[dict]) -> list[dict]:
    """Devuelve todos los formatos de audio, ordenados por abr descendente."""
    audio_formats = [fmt for fmt in formats if get_format_type(fmt) == "audio"]
    return sorted(audio_formats, key=lambda fmt: fmt.get("abr") or 0, reverse=True)


def get_compatible_audio_formats_for_mp4(
    vcodec: str, formats: list[dict]
) -> list[dict]:
    """Devuelve los formatos de audio compatibles con MP4, ordenados por abr descendente."""
    audio_formats = get_audio_formats_sorted(formats)
    return [
        fmt
        for fmt in audio_formats
        if get_format_type(fmt) == "audio"
        and is_mp4_compatible(vcodec, fmt.get("acodec", ""))
    ]


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


def merge_with_ffmpeg(
    video_path: Union[str, Path], audio_path: Union[str, Path], output: Union[str, Path]
) -> None:
    # TODO: Usar doble comillas para encerrar las ruta, solo funciona en windows
    if os.path.exists(output):
        logger.info(f"El archivo {output} ya existe. Omitiendo fusión.")
        return

    logger.info("Uniendo video y audio con FFmpeg...")
    cmd = [
        "ffmpeg",
        "-loglevel",
        "error",  # <= nivel de log de ffmpeg
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",  # copiar video sin recodificar
        "-c:a",
        "aac",  # asegura compatibilidad de audio
        "-strict",
        "experimental",
        "-shortest",  # corta al stream más corto
        str(output),
    ]
    subprocess.run(cmd, check=True)
    logger.info(f"Archivo final: {output}")


def cleanup(paths: list[str]) -> None:
    logger.info("Limpiando archivos temporales...")
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


def sleep_progress(seconds):
    if seconds <= 0:
        return
    minutes = int(timedelta(seconds=seconds).total_seconds() // 60)

    logger.info(f"Esperando {minutes} minutos antes de continuar...")
    count = 0
    for i in range(int(seconds), 0, -1):
        sleep(1)
        count += 1
        if count % 60 == 0:
            minutes -= 1
            logger.info(f"Esperando {minutes} minutos antes de continuar...")


def my_progress_hook(d):
    path = Path(d.get("filename"))
    if d["status"] == "downloading":
        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
        downloaded = d.get("downloaded_bytes", 0)
        if total_bytes:
            percent = downloaded / total_bytes * 100
            # Solo muestra cada 10 %
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


def download_media_item(job: DownloadJob, output_folder: Path) -> dict:
    """
    Descarga un único item (video o audio) usando un format_id específico.
    Esta función está diseñada para ser ejecutada en un proceso separado.
    Retorna el path del archivo descargado o lanza un error descriptivo.
    """
    output_template = f"{output_folder}/%(id)s_%(format_id)s_%(resolution)s.%(ext)s"
    url = job["url"]
    format_id = "/".join(f"{i[0]}+{i[1]}" for i in job["combinations"])
    ydl_opts = {
        "format": format_id,  # '229+140-drc|229+140|133+140-drc|133+140'
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 10,
        "fragment_retries": 10,
        "progress_hooks": [my_progress_hook],
        "progress": None,
        "noprogress": True,
        "merge_output_format": None,
        "postprocessors": [],
        "allow_unplayable_formats": True,
        # 'paths': {'home': './descargas'}, # Carpeta opcional
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = cast(dict, ydl.extract_info(url, download=True))
            filepath = info["requested_downloads"][0]["filepath"]
            logger.info(f"✔️ Descarga completada: {Path(filepath).name}")
            return info
    except DownloadError as e:
        error_msg = f"❌ Error al descargar {url} con format {format_id}: {e}"
        logger.error(error_msg)
        # Puedes elegir si relanzas o devuelves un resultado especial
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"⚠️ Excepción inesperada al descargar {url}: {str(e)}"
        logger.error(error_msg)
        logger.debug(traceback.format_exc())
        raise RuntimeError(error_msg)


def get_download_jobs(
    url: str, qualities: Sequence[Union[int, str]], output_as_mp4
) -> list[DownloadJob]:
    download_jobs = []
    formats = get_metadata(url)["formats"]
    for quality in qualities:
        combinations = get_best_video_combinations(formats, quality, output_as_mp4)
        download_jobs.append(
            {
                "quality": quality,
                "combinations": combinations,
                "url": url,
                "output_as_mp4": output_as_mp4,
            }
        )
    return download_jobs


def already_downloaded_today():
    downloads = load_download_cache()
    today = str(datetime.now().date())
    for download in downloads:
        if today in download.keys():
            return True


def register_download(number: str):
    # FIXME: si se prueba el código asegurate de eliminar el registro del dia. Sino el main_loop podria pensar que ya se ha descargado el episodio del dia.
    today = str(datetime.now().date())
    if PATH_DOWNLOAD_CACHE.exists():
        downloads = json.loads(PATH_DOWNLOAD_CACHE.read_text())
        downloads.append({today: str(number)})
        PATH_DOWNLOAD_CACHE.write_text(json.dumps(downloads))
        return
    else:
        PATH_DOWNLOAD_CACHE.parent.mkdir(parents=True, exist_ok=True)
        data = [{today: str(number)}]
        PATH_DOWNLOAD_CACHE.write_text(json.dumps(data))


def load_download_cache() -> list[dict]:
    if not PATH_DOWNLOAD_CACHE.exists():
        return []
    return json.loads(PATH_DOWNLOAD_CACHE.read_text())


def load_url_cache():
    global CACHE
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r") as f:
            CACHE = json.load(f)
    else:
        CACHE = {}


def save_url_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(CACHE, f, indent=2)


def get_metadata(url: str) -> dict:
    load_url_cache()
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
    save_url_cache()
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


def is_episode_downloaded(ep_number: str) -> bool:
    downloads = load_download_cache()
    for download in downloads:
        if ep_number in download.values():
            return True
    return False
