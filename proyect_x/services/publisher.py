import logging
from pathlib import Path
from typing import List

from proyect_x.create_thumbnail_with_watermaker import add_watermark_to_image
from proyect_x.services.register import RegistryManager
from proyect_x.uploader.send_video import TelegramUploader
from proyect_x.yt_downloader.schemas import EpisodeDownloadResult

logger = logging.getLogger(__name__)


class EpisodePublisher:
    def __init__(self, uploader: TelegramUploader, registry: RegistryManager):
        self.uploader = uploader
        self.registry = registry
        self.watermark_text = "https://t.me/DESAFIO_SIGLO_XXI"

    def process_episode(self, episode_dled: EpisodeDownloadResult) -> bool:
        """
        Orquesta la marca de agua, el registro y la subida de un episodio.
        Retorna True si el proceso fue exitoso.
        """
        episode_number = episode_dled.episode_number
        videos = episode_dled.video_paths
        thumbnail_path = episode_dled.thumbnail_path

        logger.info(f"Iniciando flujo de publicación para episodio {episode_number}")

        try:
            # 1. Registrar descarga
            self._register_downloads(episode_number, videos)

            # 2. Procesar Miniatura
            watermarked_thumb = "thumbnail_watermarked.jpg"
            add_watermark_to_image(
                str(thumbnail_path), self.watermark_text, watermarked_thumb
            )

            # 3. Subir Video(s) usando la instancia del uploader
            self.uploader.send_media_group(videos, watermarked_thumb, episode_number)

            # 4. Registrar Publicación
            self.registry.register_episode_publication(episode_number)
            logger.info(
                f"Publicación del episodio {episode_number} completada exitosamente."
            )
            return True

        except Exception as e:
            logger.error(
                f"Error procesando la publicación del episodio {episode_number}: {e}",
                exc_info=True,
            )
            raise e

    def _register_downloads(self, episode_number: str, videos: List[Path]):
        for video_path in videos:
            self.registry.register_episode_downloaded(episode_number, video_path)
