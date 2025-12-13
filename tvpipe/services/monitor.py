import logging
from datetime import datetime, timedelta
from typing import Optional

from tvpipe.config import DownloaderConfig
from tvpipe.schemas import VideoMetadata
from tvpipe.services.caracoltv import CaracolTVSchedule
from tvpipe.services.youtube.service import YouTubeFetcher
from tvpipe.utils import should_skip_weekends, sleep_progress, wait_end_of_day

logger = logging.getLogger(__name__)


class ProgramMonitor:
    def __init__(
        self,
        client: CaracolTVSchedule,
        program_url_keyword: str,
        config: DownloaderConfig,
        fetcher: YouTubeFetcher,
    ):
        self.client = client
        self.keyword = program_url_keyword  # Ej: "desafio"
        self.config = config
        self.fetcher = fetcher

    def get_program_info(self) -> Optional[dict]:
        """Busca el programa en la parrilla de hoy."""
        schedule = self.client.get_today_schedule()
        for item in schedule:
            if self.keyword in item.get("url", ""):
                return item
        return None

    def get_release_time(self) -> datetime:
        """Obtiene la hora de fin + buffer."""
        program_info = self.get_program_info()
        hits = 0

        while program_info is None:
            logger.warning(
                f"No se encontró info para '{self.keyword}'. Reintentando..."
            )
            sleep_progress(60 * 10)
            program_info = self.get_program_info()
            hits += 1
            if hits > 5:
                raise Exception(f"Imposible encontrar horario para {self.keyword}")

        return program_info["endtime"] + timedelta(minutes=5)

    def _should_wait_for_schedule(self) -> bool:
        """Verifica si es necesario esperar."""
        release_time = self.get_release_time()
        return datetime.now() < release_time

    def _wait_until_broadcast_end(self):
        """Bloquea la ejecución hasta la hora de salida."""
        release_time = self.get_release_time()
        logger.info(
            f"Esperando lanzamiento ({self.keyword}): {release_time.strftime('%I:%M %p')}"
        )

        now = datetime.now()
        if now < release_time:
            diff = (release_time - now).total_seconds()
            sleep_progress(diff)
        else:
            logger.info("El programa ya debería haber terminado.")

    def wait_for_next_episode(self) -> VideoMetadata:
        """
        Bloquea el proceso hasta que encuentra un episodio válido para descargar.
        Gestiona modo manual, fines de semana, horarios y polling.
        """

        if self.config.url:
            logger.info("Modo Manual: Obteniendo metadatos...")
            meta = self.fetcher.fetch_episode()
            if not meta:
                raise Exception("URL manual inválida o video no disponible")
            return meta

        logger.info("Modo Automático: Iniciando vigilancia de episodio...")
        while True:
            meta = self._attempt_one_check()
            if meta:
                return meta

    def _attempt_one_check(self) -> Optional[VideoMetadata]:
        """
        Ejecuta UN ciclo de validación.
        Maneja esperas (sleeps) si es necesario, pero retorna inmediatamente
        después de verificar el estado actual.
        """

        # Verificar Fin de Semana
        if self.config.skip_weekends and should_skip_weekends():
            logger.info("Fin de semana detectado. Esperando hasta el lunes...")
            wait_end_of_day()
            return None

        # Verificar Horario TV
        if self._should_wait_for_schedule():
            # Esta función internamente llama a sleep_progress
            self._wait_until_broadcast_end()
            return None

        # Verificar YouTube
        episode_meta = self.fetcher.fetch_episode()
        if episode_meta:
            return episode_meta

        # Si es la hora correcta pero no está en YT
        logger.info("El video aún no está en YouTube. Reintentando en 2 min...")
        sleep_progress(120)
        return None
