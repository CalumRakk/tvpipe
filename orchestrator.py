import logging
import time
from datetime import datetime
from pathlib import Path

from tvpipe.config import get_config
from tvpipe.logging_config import setup_logging
from tvpipe.services.caracoltv import CaracolTVSchedule
from tvpipe.services.program_monitor import ProgramMonitor
from tvpipe.services.publisher import EpisodePublisher
from tvpipe.services.register import RegistryManager
from tvpipe.services.telegram import TelegramService
from tvpipe.services.watermark import WatermarkService
from tvpipe.services.youtube.service import YouTubeFetcher
from tvpipe.services.youtube.strategies import CaracolDesafioParser
from tvpipe.utils import sleep_progress

logger = logging.getLogger("Orchestrator")


def should_skip_weekends() -> bool:
    """Helper para lógica de fines de semana."""
    return datetime.now().weekday() >= 5


def wait_end_of_day():
    """Duerme hasta las 23:59:59."""
    now = datetime.now()
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
    diff = (end_of_day - now).total_seconds()
    if diff > 0:
        logger.info("Esperando hasta el fin del día...")
        sleep_progress(diff)


def run_orchestrator():

    setup_logging(f"logs/{Path(__file__).stem}.log")
    config = get_config("config.env")

    register = RegistryManager()

    # Servicios
    tg_service = TelegramService(
        session_name=config.telegram.session_name,
        api_id=config.telegram.api_id,
        api_hash=config.telegram.api_hash,
        workdir=config.telegram.to_telegram_working,
    )

    schedule_client = CaracolTVSchedule()
    monitor = ProgramMonitor(schedule_client, "desafio")
    watermark_service = WatermarkService()

    publisher = EpisodePublisher(
        telegram_config=config.telegram,
        registry=register,
        telegram_service=tg_service,
        watermark_service=watermark_service,
    )
    desafio_strategy = CaracolDesafioParser()
    downloader = YouTubeFetcher(config.youtube, register, desafio_strategy)

    logger.info(">>> SISTEMA INICIADO: Orquestador en control <<<")

    while True:
        try:
            # Si `config.youtube.url` está definido, se trata de un modo manual.
            if config.youtube.url:
                logger.info("Modo Manual detectado. Saltando chequeos de horario.")
                episode = downloader.find_and_download(manual_url=config.youtube.url)
                if not episode:
                    logger.error("Falló la descarga manual.")

                publisher.process_episode(episode)
                logger.info("Proceso manual terminado. Saliendo.")
                break

            # Comprobación de fin de semana
            if config.youtube.skip_weekends and should_skip_weekends():
                logger.info("Es fin de semana. No hay emisión.")
                wait_end_of_day()
                continue

            # Comprobacion de Horario
            if monitor.should_wait():
                monitor.wait_until_release()
                continue

            episode = downloader.find_and_download()
            if not episode:
                logger.info("Video no disponible aún. Reintentando en 2 minutos...")
                sleep_progress(120)
                continue

            # Publicación
            success = publisher.process_episode(episode)

            if success:
                logger.info(
                    f"Ciclo completado exitosamente para {episode.episode_number}."
                )
                wait_end_of_day()
            else:
                logger.error("Hubo un error en la publicación.")
                time.sleep(60)

        except KeyboardInterrupt:
            logger.info("Deteniendo orquestador por solicitud del usuario.")
            break
        except Exception as e:
            logger.error(f"Error crítico en el bucle principal: {e}", exc_info=True)
            sleep_progress(60)


if __name__ == "__main__":
    run_orchestrator()
