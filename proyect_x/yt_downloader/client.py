import logging
from pathlib import Path
from typing import Any, Tuple, cast

import yt_dlp

from .models import Stream, VideoMetadata

logger = logging.getLogger(__name__)


class YtDlpClient:
    def __init__(self, check_certificate: bool = False):
        # Any para ignorar el tipado de yt_dlp
        self.base_opts: Any = {
            "quiet": True,
            "nocheckcertificate": not check_certificate,
        }

    def get_metadata(self, url: str) -> VideoMetadata:
        """Obtiene metadatos y los sanea en modelos Pydantic."""
        logger.info(f"Obteniendo metadatos de: {url}")

        with yt_dlp.YoutubeDL(self.base_opts) as ydl:
            info = cast(dict, ydl.extract_info(url, download=False))

        if info is None:
            raise ValueError("No se encontraron metadatos para la URL")

        # Convertimos la lista de diccionarios en objetos Stream validados
        streams = [
            Stream(**fmt)
            for fmt in info.get("formats", [])
            if fmt.get("format_id")  # Filtrar basura sin ID
        ]

        return VideoMetadata(
            id=info["id"],
            title=info["title"],
            thumbnail_url=info.get("thumbnail"),
            duration=info.get("duration"),
            streams=streams,
        )

    def select_best_pair(
        self,
        meta: VideoMetadata,
        quality_preference: str = "1080p",
        require_mp4: bool = True,
    ) -> Tuple[Stream, Stream]:
        """
        Selecciona el mejor par Video + Audio basado en la calidad deseada.
        Reemplaza toda la lógica compleja de `formats.py`.
        """
        # 1. Parsear calidad objetivo (ej: "1080p" -> 1080)
        target_h = (
            int(quality_preference.replace("p", ""))
            if "p" in quality_preference
            else 1080
        )

        # 2. Filtrar videos candidatos
        candidates = [s for s in meta.streams if s.is_video]

        if require_mp4:
            candidates = [s for s in candidates if s.is_h264]

        if not candidates:
            raise ValueError(
                f"No se encontraron streams de video compatibles (MP4={require_mp4})"
            )

        # 3. Ordenar: Primero por cercanía a la altura, luego por bitrate/tamaño
        #    La key ordena por diferencia absoluta de altura (menor es mejor) y luego tamaño (mayor es mejor)
        best_video = sorted(
            candidates, key=lambda s: (abs(s.height - target_h), -s.size_bytes)  # type: ignore
        )[0]

        logger.info(
            f"Video seleccionado: {best_video.height}p ({best_video.format_id})"
        )

        # 4. Seleccionar mejor audio compatible
        audio_candidates = [s for s in meta.streams if s.is_audio_only]
        if require_mp4:
            audio_candidates = [s for s in audio_candidates if s.is_aac]

        if not audio_candidates:
            # Fallback: si no hay audio aac específico, intentar cualquiera
            audio_candidates = [s for s in meta.streams if s.is_audio_only]

        best_audio = sorted(audio_candidates, key=lambda s: s.size_bytes, reverse=True)[  # type: ignore
            0
        ]
        logger.info(f"Audio seleccionado: {best_audio.acodec} ({best_audio.format_id})")

        return best_video, best_audio

    def download_stream(self, stream: Stream, output_path: Path) -> Path:
        """Descarga un stream específico a la ruta indicada."""
        if output_path.exists():
            logger.info(f"Archivo ya existe, saltando descarga: {output_path.name}")
            return output_path

        opts = self.base_opts.copy()
        opts.update(
            {
                "format": stream.format_id,
                "outtmpl": str(output_path),
            }
        )

        logger.info(f"Descargando {stream.format_id} -> {output_path.name}...")
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([stream.url])  # type: ignore

        return output_path
