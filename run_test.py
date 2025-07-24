import logging
from pathlib import Path

from logging_config import setup_logging
from proyect_x.yt_downloader.main import RELEASE_MODE, main_loop

if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")
    logger = logging.getLogger(__name__)
    serie_name = "desafio siglo xxi 2025"
    qualities = ["720", "360"]
    output_folder = Path("output")
    mode = RELEASE_MODE.AUTO

    for final_files in main_loop(serie_name, qualities, output_folder, mode):
        logger.info(f"Archivos finales: {final_files}")
        break
