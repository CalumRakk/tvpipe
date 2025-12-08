import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Tuple, cast

import yt_dlp

from .models import Stream, VideoMetadata

logger = logging.getLogger(__name__)


class YtDlpClient:
    def __init__(self, check_certificate: bool = False):
        node_path = shutil.which("node") or "node"

        self.base_opts: Any = {
            "quiet": True,
            "nocheckcertificate": not check_certificate,
            "js_runtimes": {"node": {"args": [node_path]}},
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
            timestamp=info["timestamp"],
            was_live=info["is_live"],
        )

    def select_best_pair(
        self,
        meta: VideoMetadata,
        quality_preference: str = "1080p",
        require_mp4: bool = True,
    ) -> Tuple[Stream, Stream]:
        """
        Selecciona el mejor par Video + Audio basado en la calidad deseada.
        """
        target_h = (
            int(quality_preference.replace("p", ""))
            if "p" in quality_preference
            else 1080
        )

        # Filtrar videos candidatos
        candidates = [s for s in meta.streams if s.is_video]

        if require_mp4:
            candidates = [s for s in candidates if s.is_h264]

            if not candidates:
                raise ValueError(
                    f"No se encontraron streams de video compatibles (MP4={require_mp4})"
                )

        # Ordenar: Primero por cercanía a la altura, luego por bitrate/tamaño
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

    def download_stream(self, stream: Stream, output_path: Path, url: str) -> Path:
        """
        Descarga un stream específico usando la URL original del video.
        """
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
            ydl.download([url])

        return output_path

    def find_video_by_criteria(
        self, channel_url: str, title_validator: Callable[[str], bool]
    ) -> Optional[str]:
        """
        Busca en el canal un video que cumpla con el validador de título
        y que haya sido publicado HOY.
        """
        logger.info(f"Escaneando canal: {channel_url}")

        search_opts = self.base_opts.copy()
        search_opts.update(
            {
                "extract_flat": True,
                "playlistend": 5,
            }
        )

        with yt_dlp.YoutubeDL(search_opts) as ydl:
            # download=False y extract_flat=True hacen que esto sea muy rápido
            info = cast(dict, ydl.extract_info(channel_url, download=False))

            if not info or "entries" not in info:
                return None

            for entry in info["entries"]:
                title = entry.get("title", "")
                url = entry.get("url", "")

                if not title_validator(title):
                    continue

                # Validación de seguridad (Fecha y Live)
                try:
                    meta = self.get_metadata(url)

                    video_date = datetime.fromtimestamp(meta.timestamp).date()
                    is_today = video_date == datetime.now().date()

                    if is_today and not meta.was_live:
                        logger.info(f"¡Match confirmado!: {title}")
                        return url

                except Exception as e:
                    logger.warning(f"Error verificando metadatos de {url}: {e}")
                    continue

            return None
