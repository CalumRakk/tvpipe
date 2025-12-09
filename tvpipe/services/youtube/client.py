import logging
import shutil
from pathlib import Path
from typing import Any, cast

import yt_dlp

from .models import Stream, StreamPair, VideoMetadata

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
            url=url,
        )

    def download_stream(self, stream: StreamPair, output_path: Path, url: str) -> Path:
        """
        Descarga un stream específico usando la URL original del video.
        """
        if not url.startswith("https://www.youtube.com/watch?"):
            raise ValueError(f"URL inválida: {url}")

        temp_video = output_path.with_suffix(".temp")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists():
            logger.info(f"Archivo ya existe, saltando descarga: {output_path.name}")
            return output_path

        if not temp_video.exists():
            opts = self.base_opts.copy()
            opts.update(
                {
                    "format": f"{stream.video.format_id}+{stream.audio.format_id}",
                    "outtmpl": str(temp_video),
                }
            )

            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

        temp_video.rename(output_path)
        return output_path

    def select_best_pair(
        self,
        meta: VideoMetadata,
        quality_preference: str = "1080p",
        require_mp4: bool = True,
    ) -> StreamPair:
        target_height = self._parse_height(quality_preference)

        # Seleccionar Video
        best_video = self._select_video_track(meta.streams, target_height, require_mp4)
        logger.info(
            f"Video seleccionado: {best_video.height}p ({best_video.format_id})"
        )

        # Seleccionar Audio (basado en el video elegido)
        best_audio = self._select_smart_audio_track(
            meta.streams, best_video.height or 0, require_mp4
        )
        logger.info(
            f"Audio seleccionado: {best_audio.acodec} | Bitrate: {best_audio.abr}k ({best_audio.format_id})"
        )

        return StreamPair(video=best_video, audio=best_audio)

    def _parse_height(self, quality_str: str) -> int:
        """Convierte '1080p' o 'best' a un entero numérico."""
        # TODO: Mejorar el parse para que acepte terminos humanos como "hd","sd" o calidades k como "2k", "4k"
        if "p" in quality_str:
            return int(quality_str.replace("p", ""))
        return 1080

    def _select_video_track(
        self, streams: list[Stream], target_height: int, require_mp4: bool
    ) -> Stream:
        """
        Filtra y selecciona el stream de video más cercano a la altura deseada.
        Prioriza H.264 si require_mp4 es True.
        """
        candidates = [s for s in streams if s.is_video]

        if require_mp4:
            # Filtro solo H.264 garantiza merge sin recodificación
            candidates = [s for s in candidates if s.is_h264]
            if not candidates:
                raise ValueError(
                    "No se encontraron streams de video H.264 compatibles."
                )

        best_video = min(
            candidates,
            key=lambda s: (abs((s.height or 0) - target_height), -s.size_bytes),  # type: ignore
        )
        return best_video

    def _select_smart_audio_track(
        self, streams: list[Stream], video_height: int, require_mp4: bool
    ) -> Stream:
        """
        Selecciona el audio más adecuado proporcionalmente a la calidad del video.
        """
        candidates = [s for s in streams if s.is_audio_only]

        if require_mp4:
            # Preferencia fuerte por AAC para evitar recodificación
            candidates = [s for s in candidates if s.is_aac]
            if not candidates:
                logger.warning(
                    "No hay audio AAC disponible. Se usará fallback (posible recodificación)."
                )
                raise ValueError("No se encontraron streams de audio AAC compatibles.")

        # Definir Bitrate Objetivo (kbps) según resolución de video
        target_abr = self._get_target_audio_bitrate(video_height)

        # Elegir el ganador basado en Score
        return sorted(
            candidates,
            key=lambda s: self._calculate_audio_score(s, target_abr),
            reverse=True,
        )[0]

    def _get_target_audio_bitrate(self, height: int) -> float:
        """Define qué calidad de audio 'merece' el video según su tamaño."""
        if height <= 480:
            return 96.0  # Calidad baja/media
        elif height < 1080:
            return 128.0  # Calidad estándar
        return 9999.0  # Calidad máxima (HD/4K)

    def _calculate_audio_score(self, stream: Stream, target_abr: float) -> float:
        """
        Calcula una puntuación para el stream de audio.
        Retorna un valor más alto cuanto mejor sea el candidato.
        """
        abr = stream.abr or 0
        if target_abr == 9999.0:
            return abr

        diff = abr - target_abr

        # Penalización fuerte: Si es menor al target (-10kbps de margen), lo castigamos.
        # Preferimos pasarnos (desperdiciar un poco) a que se escuche mal.
        if diff < -10:
            return diff * 2

        # Si es mayor o igual, priorizamos el que esté más cerca
        return -abs(diff)

    def get_latest_channel_entries(
        self, channel_url: str, limit: int = 5
    ) -> list[dict]:
        """Obtiene las últimas N entradas de un canal."""
        logger.info(f"Escaneando canal: {channel_url}")

        opts = self.base_opts.copy()
        opts.update({"extract_flat": True, "playlistend": limit})

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = cast(dict, ydl.extract_info(channel_url, download=False))
            return info.get("entries", []) if info else []
