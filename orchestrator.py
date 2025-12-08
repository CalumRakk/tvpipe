from pathlib import Path

from tvpipe.config import get_config
from tvpipe.logging_config import setup_logging
from tvpipe.services.caracoltv_schedule import CaracolTVSchedule
from tvpipe.services.program_monitor import ProgramMonitor
from tvpipe.services.publisher import EpisodePublisher
from tvpipe.services.register import RegistryManager
from tvpipe.services.telegram.client import TelegramService
from tvpipe.services.watermark import WatermarkService
from tvpipe.yt_downloader.runner import main_loop

if __name__ == "__main__":
    setup_logging(f"logs/{Path(__file__).stem}.log")

    config = get_config("config.env")

    register = RegistryManager()

    tg_service = TelegramService(
        session_name=config.telegram.session_name,
        api_id=config.telegram.api_id,
        api_hash=config.telegram.api_hash,
        workdir=config.telegram.to_telegram_working,
    )
    client = CaracolTVSchedule()
    monitor = ProgramMonitor(client, "desafio")
    watermark_service = WatermarkService()

    publisher = EpisodePublisher(
        telegram_config=config.telegram,
        registry=register,
        telegram_service=tg_service,
        watermark_service=watermark_service,
    )

    for episode_dled in main_loop(config.youtube, register, monitor):
        publisher.process_episode(episode_dled)
