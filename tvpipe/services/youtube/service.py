import logging
import re
from typing import Optional

from tvpipe.config import DownloaderConfig
from tvpipe.interfaces import BaseDownloader, DownloadedEpisode
from tvpipe.services.register import RegistryManager
from tvpipe.utils import download_thumbnail

from .client import YtDlpClient

logger = logging.getLogger(__name__)


def get_episode_number_from_title(title: str) -> str:
    match = re.search(r"ap[íi]tulo\s+(\d+)", title, re.IGNORECASE)
    if match:
        return match.group(1)
    raise Exception("No se encontró el número de episodio.")


def is_valid_episode_title(title: str) -> bool:
    try:
        episode_num = get_episode_number_from_title(title)
        return bool(episode_num) and "avance" in title
    except Exception:
        return False


class YouTubeDownloader(BaseDownloader):
    CHANNEL_URL = "https://www.youtube.com/@desafiocaracol/videos"

    def __init__(self, config: DownloaderConfig, registry: RegistryManager):
        self.config = config
        self.registry = registry
        self.client = YtDlpClient()

    def find_and_download(
        self, manual_url: Optional[str] = None
    ) -> Optional[DownloadedEpisode]:
        """
        Intenta encontrar y descargar un episodio.
        Retorna DownloadedEpisode si tuvo éxito, o None si no encontró nada o ya existe.
        """
        url = manual_url
        if not url:
            url = self.client.find_video_by_criteria(
                channel_url=self.CHANNEL_URL, title_validator=is_valid_episode_title
            )

        if not url:
            return None

        meta = self.client.get_metadata(url)
        try:
            episode_num = get_episode_number_from_title(meta.title)
        except Exception:
            logger.warning(f"Video encontrado pero título inválido: {meta.title}")
            return None

        if self.registry.was_episode_published(episode_num):
            logger.info(f"El capítulo {episode_num} ya fue publicado anteriormente.")
            return None

        logger.info(f"Iniciando descarga para Episodio {episode_num}...")

        quality_pref = (
            str(self.config.qualities[0]) if self.config.qualities else "1080p"
        )

        stream = self.client.select_best_pair(
            meta, quality_preference=quality_pref, require_mp4=self.config.output_as_mp4
        )

        filename = self.config.generate_filename(episode_num, stream.height)
        output_path = self.config.download_folder / filename

        self.client.download_stream(stream, output_path, url)

        thumb_path = output_path.with_suffix(".jpg")
        download_thumbnail(meta.thumbnail_url, thumb_path)

        return DownloadedEpisode(
            episode_number=episode_num,
            video_path=output_path,
            thumbnail_path=thumb_path,
            source="youtube",
        )
