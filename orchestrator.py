from pathlib import Path

from proyect_x.logging_config import setup_logging
from proyect_x.services.publisher import EpisodePublisher
from proyect_x.services.register import RegistryManager
from proyect_x.uploader.settings import get_settings as get_upload_settings
from proyect_x.yt_downloader.config.settings import get_settings as get_yt_settings
from proyect_x.yt_downloader.runner import main_loop

if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")

    config_yt = get_yt_settings(env_path=Path(".env/.download_video.env"))
    config_upload = get_upload_settings(env_path=Path(".env/.upload_episode.env"))

    register = RegistryManager()
    publisher = EpisodePublisher(config_upload, register)

    for episode_dled in main_loop(config_yt):
        publisher.process_episode(episode_dled)
