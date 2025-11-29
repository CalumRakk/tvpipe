import logging
import time
from typing import Generator, Optional

from proyect_x.caracoltv import CaracolTV
from proyect_x.config import DownloaderConfig
from proyect_x.services.register import RegistryManager
from proyect_x.yt_downloader.schemas import EpisodeDownloadResult
from proyect_x.yt_downloader.services.daily_download import (
    parallel_downloads,
    postprocess_downloads,
    prepare_formats,
)
from proyect_x.yt_downloader.services.scheduling import get_episode_url

logger = logging.getLogger(__name__)


class EpisodePipeline:
    def __init__(
        self,
        config: DownloaderConfig,
        registry: RegistryManager,
        schedule_provider: CaracolTV,
    ):
        self.config = config
        self.registry = registry
        self.schedule_provider = schedule_provider

    def _step_get_url(self) -> Optional[str]:
        """Paso 1: Obtener la URL del episodio."""
        try:
            logger.info("Buscando URL del episodio...")
            return get_episode_url(self.config, self.registry, self.schedule_provider)
        except Exception as e:
            logger.error(f"Fallo en paso [GET URL]: {e}")
            raise

    def _step_download(self, episode_url: str):
        """Paso 2: Preparar formatos y descargar."""
        try:
            logger.info(f"Iniciando descarga para: {episode_url}")
            formats = prepare_formats(episode_url, self.config)
            return parallel_downloads(formats, self.config)
        except Exception as e:
            logger.error(f"Fallo en paso [DOWNLOAD]: {e}")
            # TODO: Limpiar las descarga si falla.
            raise

    def _step_postprocess(self, episode_url: str, downloads) -> EpisodeDownloadResult:
        """Paso 3: Unir audio/video y generar thumbnail."""
        try:
            logger.info("Procesando archivos descargados...")
            return postprocess_downloads(episode_url, downloads, self.config)
        except Exception as e:
            logger.error(f"Fallo en paso [POST-PROCESS]: {e}")
            raise

    def run_once(self) -> Optional[EpisodeDownloadResult]:
        """Ejecuta una iteración completa."""
        episode_url = self._step_get_url()
        if not episode_url:
            return None
        downloads = self._step_download(episode_url)
        result = self._step_postprocess(episode_url, downloads)
        return result

    def start(self) -> Generator[EpisodeDownloadResult, None, None]:
        logger.info("Iniciando Pipeline de Descarga.")

        while True:
            try:
                result = self.run_once()
                if result:
                    yield result
                    logger.info(
                        "Ciclo completado con éxito. Esperando siguiente ciclo..."
                    )
                else:
                    time.sleep(60)
            except Exception as e:
                logger.critical(f"Error crítico en el ciclo: {e}")
                time.sleep(10)
                continue


def main_loop(
    config: DownloaderConfig, registry: RegistryManager, schedule_provider: CaracolTV
) -> Generator[EpisodeDownloadResult, None, None]:
    pipeline = EpisodePipeline(config, registry, schedule_provider)
    yield from pipeline.start()
