import logging
from pathlib import Path
from typing import List

from tvpipe.config import TelegramConfig
from tvpipe.services.register import RegistryManager
from tvpipe.services.telegram.client import TelegramService
from tvpipe.services.telegram.schemas import UploadedVideo

logger = logging.getLogger(__name__)


class EpisodePublisher:
    def __init__(
        self,
        config: TelegramConfig,
        telegram_client: TelegramService,
        registry: RegistryManager,
    ):
        self.config = config
        self.client = telegram_client
        self.registry = registry

    def prepare_video(self, video_path: Path, thumbnail_path: Path) -> UploadedVideo:
        """
        Sube un video o lo recupera del caché si ya existe y es válido.
        """

        if self.registry.was_video_uploaded(video_path):
            data = self.registry.get_video_uploaded(video_path)
            chat_id = data["chat_id"]
            message_id = data["message_id"]

            if self.client.exists_video_in_chat(chat_id, message_id):
                logger.info(f"Video reutilizado desde caché: {video_path.name}")
                return self.client.fetch_video_uploaded(chat_id, message_id)
            else:
                logger.warning(
                    f"Entrada de caché inválida para {video_path.name}. Limpiando registro."
                )
                self.registry.remove_video_entry(video_path)

        logger.info(f"Subiendo archivo nuevo: {video_path.name}")
        uploaded_video = self.client.upload_video(
            video_path=video_path,
            thumbnail_path=thumbnail_path,
            target_chat_id=self.config.chat_id_temporary,
            caption=video_path.name,
        )

        self.registry.register_video_uploaded(
            uploaded_video.message_id, uploaded_video.chat_id, video_path
        )

        return uploaded_video

    def publish(self, episode_number: str, videos: List[UploadedVideo]) -> bool:
        """
        Publica el álbum final con el caption formateado.
        """
        caption = self._build_caption(episode_number, videos)
        logger.info(f"Publicando álbum episodio {episode_number}...")

        target_chats = self.client.send_album(
            files=videos,
            caption=caption,
            dest_chat_ids=self.config.chat_ids,
        )

        success = bool(target_chats)
        if success:
            self.registry.register_episode_publication(episode_number)

        return success

    def _build_caption(self, episode_number: str, videos: List[UploadedVideo]) -> str:
        caption = self.config.caption.format(episode=str(episode_number))
        videos_sorted = sorted(videos, key=lambda v: v.size_bytes)

        for vid in videos_sorted:
            size_mb = int(vid.size_bytes / (1024 * 1024))
            format_name = "HD" if vid.width > 720 else "SD"
            caption += f"{format_name}: {size_mb} MB\n"
        return caption
