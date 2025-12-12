import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from tvpipe.config import DownloaderConfig
from tvpipe.interfaces import BaseDownloader, EpisodeParser
from tvpipe.schemas import DownloadedEpisode, VideoMetadata
from tvpipe.services.register import RegistryManager
from tvpipe.utils import download_thumbnail

from .client import YtDlpClient

logger = logging.getLogger(__name__)


class YouTubeFetcher(BaseDownloader):
    def __init__(
        self,
        config: DownloaderConfig,
        registry: RegistryManager,
        episode_parser: EpisodeParser,
        client: YtDlpClient,
    ):
        self.config = config
        self.registry = registry
        self.client = client
        self.strategy = episode_parser

    def fetch_episode(self) -> Optional[VideoMetadata]:
        """
        Obtiene los metadatos del candidato ideal (ya sea por URL manual o búsqueda automática).
        NO descarga nada, solo retorna la info si encuentra algo válido.
        """
        if self.config.url:
            logger.info("Modo Manual: Obteniendo metadatos de URL provista.")
            return self.client.get_metadata(self.config.url)
        return self._find_automatic_candidate()

    def _find_automatic_candidate(self) -> Optional[VideoMetadata]:
        """
        Itera sobre las últimas entradas del canal y retorna los metadatos
        del primer video que cumpla con la estrategia y sea de hoy.
        """
        entries = self.client.get_latest_channel_entries(self.config.channel_url)

        for entry in entries:
            title = entry.get("title", "")
            url = entry.get("url", "")

            if not self.strategy.matches_criteria(title):
                continue

            try:
                # Validación extra (Fecha y Live status)
                meta = self.client.get_metadata(url)

                video_date = datetime.fromtimestamp(meta.timestamp).date()
                is_today = video_date == datetime.now().date()

                if is_today and not meta.was_live:
                    logger.info(f"¡Candidato encontrado!: {title}")
                    return meta

            except Exception as e:
                logger.warning(f"Error verificando candidato {url}: {e}")
                continue

        return None

    def download_episode(self, meta: VideoMetadata) -> DownloadedEpisode:
        """
        Orquesta la descarga de múltiples versiones del video según `config.qualities`.

        Lógica de Resolución y Deduplicación:
            1. Itera sobre las calidades deseadas (ej: ["1080p", "720p", "480p"]).
            2. `select_best_pair` busca el stream más cercano a la calidad solicitada.
            3. Si el video original tiene resoluciones limitadas (ej: solo llega a 480p):
               - Al pedir "1080p", el selector retornará el stream de 480p (el mejor disponible).
               - Al pedir "720p", retornará nuevamente el mismo stream de 480p.
               - El set `processed_resolutions` detectará que 480p ya se procesó y evitará
                 descargar el archivo dos veces.

        Returns:
            DownloadedEpisode: Objeto con la lista de rutas de los videos descargados
            (uno por cada resolución única encontrada) y la miniatura.
        """

        logger.info(f"Iniciando la descarga del Episodio {meta.title}...")

        downloaded_paths = []
        processed_resolutions = set()

        episode_num = self.strategy.extract_number(meta.title)
        for quality_pref in self.config.qualities:
            quality_pref_str = str(quality_pref)
            try:
                stream = self.client.select_best_pair(
                    meta,
                    quality_preference=quality_pref_str,
                    require_mp4=self.config.output_as_mp4,
                )
            except ValueError as e:
                logger.warning(f"Saltando calidad '{quality_pref_str}': {e}")
                continue

            if stream.height in processed_resolutions:
                logger.info(
                    f"Omitiendo '{quality_pref_str}' porque la resolución {stream.height}p ya fue procesada."
                )
                continue

            filename = self.config.generate_video_filename(episode_num, stream.height)
            output_path = self.config.download_folder / filename

            try:
                logger.info(
                    f"Descargando versión {stream.height}p (pref: {quality_pref_str})..."
                )
                self.client.download_stream(stream, output_path, meta.url)

                downloaded_paths.append(output_path)
                processed_resolutions.add(stream.height)

            except Exception as e:
                logger.error(f"Error descargando stream {stream.height}p: {e}")

        if not downloaded_paths:
            raise Exception(
                f"No se pudo descargar ninguna calidad válida para el episodio {episode_num}."
            )

        return DownloadedEpisode(
            episode_number=episode_num,
            video_paths=downloaded_paths,
            source="youtube",
        )

    def download_thumbnail(self, meta: VideoMetadata) -> Path:
        episode_num = self.strategy.extract_number(meta.title)
        thumb_filename = self.config.generate_thumb_filename(episode_num)
        thumb_path = self.config.download_folder / thumb_filename

        return download_thumbnail(meta.thumbnail_url, thumb_path)
