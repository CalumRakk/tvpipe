from pathlib import Path

from proyect_x.config import get_config
from proyect_x.logging_config import setup_logging
from proyect_x.services.publisher import EpisodePublisher
from proyect_x.services.register import RegistryManager
from proyect_x.yt_downloader.runner import main_loop

if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")

    config = get_config("config.env")

    register = RegistryManager()
    publisher = EpisodePublisher(telegram_config=config.telegram, registry=register)

    for episode_dled in main_loop(config.youtube):
        publisher.process_episode(episode_dled)
