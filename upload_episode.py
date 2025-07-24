from pathlib import Path

from proyect_x.logging_config import setup_logging
from proyect_x.upload.send_video import main as send_videos
from proyect_x.upload.settings import get_settings

if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")
    config = get_settings(env_path=Path(".env/.upload_episode.env"))

    send_videos("16", config)
