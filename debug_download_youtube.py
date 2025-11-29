import logging
from pathlib import Path

from proyect_x.config import get_config
from proyect_x.logging_config import setup_logging
from proyect_x.yt_downloader.runner import main_loop

if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")

    config = get_config(env_path=Path("config.env"))

    for final_files in main_loop(config.youtube):
        logger = logging.getLogger(__name__)
        logger.info(f"Archivos finales: {final_files}")
        break
