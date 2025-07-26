"""
formats.py
------------
Contiene funciones relacionadas con el manejo, validación y resolución de formatos y calidades de video/audio.

Ideal para incluir funciones relacionadas con:
- Resolución de alias de calidad (e.g., "best", "medium", "low").
- Mapeo de etiquetas de resolución ("4k", "1080p", etc.) a alturas numéricas.
- Filtrado y ordenamiento de formatos de acuerdo a compatibilidad (ej. MP4).
- Determinación del tipo de formato (audio, video, mixto).
- Comprobación de compatibilidad de codecs entre audio y video.

Este módulo es clave para construir combinaciones óptimas de descarga.
"""

import re
from pathlib import Path
from typing import Optional, Tuple, Union, get_args

from proyect_x.yt_downloader.schemas import (
    KLABEL_MAP,
    YOUTUBE_AUDIO_CODECS,
    YOUTUBE_VIDEO_CODECS,
    DownloadJobResult,
    KLabel,
    QualityAlias,
)

from ..exceptions import QualityNotFoundError


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
    vcodec = vcodec.lower()
    acodec = acodec.lower()
    return vcodec.startswith("avc1") and (acodec.startswith("mp4a") or acodec == "mp3")


def resolve_quality_alias(alias: str, formats: list[dict]) -> int | None:
    if not formats or alias not in get_args(QualityAlias):
        return None

    candicates = [i for i in formats if i.get("vbr")]
    sorted_candidates = sorted(candicates, key=lambda q: q["height"])

    match alias.lower():
        case "low":
            return sorted_candidates[0]["height"]
        case "medium":
            return (
                sorted_candidates[len(sorted_candidates) // 2]["height"]
                if len(sorted_candidates) >= 3
                else sorted_candidates[0]["height"]
            )
        case "best":
            return sorted_candidates[-1]["height"]

    return None


def resolve_quality_label(label: str) -> int | None:
    label = label.lower().strip()
    if label in get_args(KLabel):
        return KLABEL_MAP[label]

    match = re.fullmatch(r"(\d+)\s*p", label)
    if match:
        return int(match.group(1))

    return None


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
    return not all([fmt.get("format_id"), fmt.get("format_note"), fmt.get("protocol")])


def get_audio_formats_sorted(formats: list[dict]) -> list[dict]:
    audio_formats = [fmt for fmt in formats if get_format_type(fmt) == "audio"]
    return sorted(audio_formats, key=lambda fmt: fmt.get("abr") or 0, reverse=True)


def get_compatible_audio_formats_for_mp4(
    vcodec: str, formats: list[dict]
) -> list[dict]:
    audio_formats = get_audio_formats_sorted(formats)
    return [
        fmt
        for fmt in audio_formats
        if get_format_type(fmt) == "audio"
        and is_mp4_compatible(vcodec, fmt.get("acodec", ""))
    ]


def get_best_video_combinations(
    formats: list[dict], quality: Union[int, str], output_as_mp4: bool
) -> list[tuple[str, str]]:
    if isinstance(quality, int):
        target_height = quality
    elif quality in get_args(QualityAlias):
        target_height = resolve_quality_alias(quality, formats)
    elif str(quality).isdigit():
        target_height = int(quality)
    else:
        target_height = resolve_quality_label(quality)

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

    video_formats.sort(key=lambda x: x.get("vbr") or 0, reverse=True)

    combinations = []
    for video_fmt in video_formats:
        audio_formats = (
            get_compatible_audio_formats_for_mp4(video_fmt["vcodec"], formats)
            if output_as_mp4
            else get_audio_formats_sorted(formats)
        )
        for audio_fmt in audio_formats:
            combinations.append((video_fmt["format_id"], audio_fmt["format_id"]))
    return combinations


def extract_files_from_download_result(
    download_result: DownloadJobResult,
) -> Tuple[Optional[Path], Optional[Path], Optional[int]]:
    video = None
    audio = None
    quality_height = None
    for formatsimple in download_result["ytdlp_response"]["requested_downloads"][0][
        "requested_formats"
    ]:
        if get_format_type(formatsimple) == "video":
            video = Path(formatsimple["filepath"]).resolve()
            quality_height = formatsimple["height"]

        elif get_format_type(formatsimple) == "audio":
            audio = Path(formatsimple["filepath"]).resolve()
    return (video, audio, quality_height)
