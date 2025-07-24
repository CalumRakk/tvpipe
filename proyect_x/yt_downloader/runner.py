import logging
from pathlib import Path
from typing import Generator

from proyect_x.yt_downloader.services.daily_download import prepare_formats
from proyect_x.yt_downloader.services.scheduling import get_episode_url

from .config.settings import AppSettings, get_settings
from .schemas import RELEASE_MODE, MainLoopResult
from .services.daily_download import (
    parallel_downloads,
    postprocess_and_register,
    prepare_formats,
)

logger = logging.getLogger(__name__)


# Generator[MainLoopResult, None, None]
def main_loop(
    config: AppSettings,
) -> Generator[dict, None, None]:
    logger.info("Iniciando el bucle principal de descarga del capítulo del día.")
    while True:
        episode = get_episode_url(config.mode)
        formats = prepare_formats(episode, config)
        downloads = parallel_downloads(formats, config)
        yield postprocess_and_register(episode, downloads, config)
        logger.info("✅ Descarga del capítulo del día completada.")


if __name__ == "__main__":
    config = get_settings()
    for final_files in main_loop(config):
        logger.info(f"Archivos finales: {final_files}")
        break
