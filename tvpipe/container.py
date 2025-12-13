from tvpipe.config import AppConfig
from tvpipe.services.caracoltv import CaracolTVSchedule
from tvpipe.services.program_monitor import ProgramMonitor
from tvpipe.services.publisher import EpisodePublisher
from tvpipe.services.register import RegistryManager
from tvpipe.services.telegram import TelegramService
from tvpipe.services.watermark import WatermarkService
from tvpipe.services.youtube.client import YtDlpClient
from tvpipe.services.youtube.service import YouTubeFetcher
from tvpipe.services.youtube.strategies import CaracolDesafioParser


class ServiceContainer:
    """
    Clase encargada de ensamblar todas las dependencias del sistema.
    Centraliza la creación de objetos para limpiar el orquestador.
    """

    def __init__(self, config: AppConfig):
        self.register = RegistryManager()

        self.tg = TelegramService(
            session_name=config.telegram.session_name,
            api_id=config.telegram.api_id,
            api_hash=config.telegram.api_hash,
            workdir=config.telegram.to_telegram_working,
        )

        self.watermark = WatermarkService()

        self.schedule = CaracolTVSchedule()

        self.monitor = ProgramMonitor(
            client=self.schedule,
            program_url_keyword="desafio",  # TODO: Esto deberia ir en config
        )

        self.publisher = EpisodePublisher(
            config=config.telegram, telegram_client=self.tg, registry=self.register
        )

        # 3. Servicios de Descarga
        self.yt_client = YtDlpClient()
        self.strategy = CaracolDesafioParser()

        self.downloader = YouTubeFetcher(
            config=config.youtube,
            registry=self.register,
            episode_parser=self.strategy,
            client=self.yt_client,
        )
