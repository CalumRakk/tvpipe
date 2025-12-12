import logging
from typing import List

from tvpipe.config import TelegramConfig
from tvpipe.services.telegram.client import TelegramService
from tvpipe.services.telegram.schemas import UploadedVideo

logger = logging.getLogger(__name__)


class EpisodePublisher:
    def __init__(self, config: TelegramConfig, client: TelegramService):
        self.config = config
        self.client = client

    def build_caption(self, episode_number: str, videos: List[UploadedVideo]) -> str:
        caption = self.config.caption.format(episode=str(episode_number))
        for vid in videos:
            size_mb = int(vid.size_bytes / (1024 * 1024))
            format_name = "HD" if vid.width > 720 else "SD"
            caption += f"{format_name}: {size_mb} MB\n"
        return caption

    def publish(self, episode_number: str, videos: List[UploadedVideo]) -> bool:
        caption = self.build_caption(episode_number, videos)
        logger.info(f"Publicando álbum episodio {episode_number}...")
        try:
            target_chats = self.client.send_album(
                files=videos,
                caption=caption,
                dest_chat_ids=self.config.chat_ids,
            )
            return bool(target_chats)
        finally:
            self.client.stop()
