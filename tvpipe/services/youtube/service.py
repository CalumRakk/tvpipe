import logging
from datetime import datetime
from typing import Optional

from tvpipe.config import DownloaderConfig
from tvpipe.interfaces import BaseDownloader, DownloadedEpisode, EpisodeParser
from tvpipe.services.register import RegistryManager
from tvpipe.services.youtube.models import VideoMetadata
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

    def fetch_and_download(
        self, manual_url: Optional[str] = None
    ) -> Optional[DownloadedEpisode]:
        meta = self._get_target_metadata(manual_url)

        if not meta:
            return None

        episode_num = self.strategy.extract_number(meta.title)

        if self.registry.was_episode_published(episode_num):
            logger.info(f"El capítulo {episode_num} ya fue publicado anteriormente.")
            return None

        return self._perform_download(meta, episode_num)

    def _get_target_metadata(
        self, manual_url: Optional[str]
    ) -> Optional[VideoMetadata]:
        """
        Determina qué video procesar. Si hay URL manual, usa esa.
        Si no, busca en el canal candidatos válidos.
        """
        if manual_url:
            logger.info("Modo Manual: Obteniendo metadatos de URL provista.")
            return self.client.get_metadata(manual_url)

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

    def _perform_download(
        self, meta: VideoMetadata, episode_num: str
    ) -> DownloadedEpisode:
        logger.info(f"Iniciando descarga para Episodio {episode_num}...")

        quality_pref = (
            str(self.config.qualities[0]) if self.config.qualities else "1080p"
        )

        stream = self.client.select_best_pair(
            meta, quality_preference=quality_pref, require_mp4=self.config.output_as_mp4
        )

        filename = self.config.generate_filename(episode_num, stream.height)
        output_path = self.config.download_folder / filename
        thumb_path = output_path.with_suffix(".jpg")

        self.client.download_stream(stream, output_path, meta.url)
        download_thumbnail(meta.thumbnail_url, thumb_path)

        return DownloadedEpisode(
            episode_number=episode_num,
            video_path=output_path,
            thumbnail_path=thumb_path,
            source="youtube",
        )
