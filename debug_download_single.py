from pathlib import Path

from tvpipe.config import get_config
from tvpipe.logging_config import setup_logging
from tvpipe.services.register import RegistryManager
from tvpipe.services.youtube.client import YtDlpClient
from tvpipe.services.youtube.service import YouTubeFetcher
from tvpipe.services.youtube.strategies import CaracolDesafioParser

# --- CONFIGURACIÓN DE LA PRUEBA ---
TEST_URL = "https://www.youtube.com/watch?v=pfELv3BsuVQ"


def debug_single_download():
    setup_logging(f"logs/{Path(__file__).stem}.log")

    config = get_config("config.env")
    config.youtube.url = TEST_URL

    downloader = YouTubeFetcher(
        config.youtube, RegistryManager(), CaracolDesafioParser(), YtDlpClient()
    )
    episode = downloader.fetch_episode()
    if episode:
        downloader.download_episode(episode)


if __name__ == "__main__":
    debug_single_download()
