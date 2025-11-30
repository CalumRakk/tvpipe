from pathlib import Path

from proyect_x.config import get_config
from proyect_x.logging_config import setup_logging
from proyect_x.yt_downloader.client import YtDlpClient

if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")

    config = get_config(env_path=Path("config.env"))

    client = YtDlpClient()

    meta = client.get_metadata("https://www.youtube.com/watch?v=pfELv3BsuVQ")
    pairs = client.select_best_pair(meta)
    print(meta)
