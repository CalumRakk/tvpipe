import logging
from datetime import datetime, timedelta
from typing import Optional

from tvpipe.services.caracoltv_schedule import CaracolTVSchedule
from tvpipe.utils import sleep_progress


class ProgramMonitor:
    def __init__(self, client: CaracolTVSchedule, program_url_keyword: str):
        self.client = client
        self.keyword = program_url_keyword  # Ej: "desafio"
        self.logger = logging.getLogger(f"Monitor[{self.keyword}]")

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
            self.logger.warning(
                f"No se encontró info para '{self.keyword}'. Reintentando..."
            )
            sleep_progress(60 * 10)
            program_info = self.get_program_info()
            hits += 1
            if hits > 5:
                raise Exception(f"Imposible encontrar horario para {self.keyword}")

        return program_info["endtime"] + timedelta(minutes=5)

    def should_wait(self) -> bool:
        """Verifica si es necesario esperar."""
        release_time = self.get_release_time()
        return datetime.now() < release_time

    def wait_until_release(self):
        """Bloquea la ejecución hasta la hora de salida."""
        release_time = self.get_release_time()
        self.logger.info(
            f"Esperando lanzamiento ({self.keyword}): {release_time.strftime('%I:%M %p')}"
        )

        now = datetime.now()
        if now < release_time:
            diff = (release_time - now).total_seconds()
            sleep_progress(diff)
        else:
            self.logger.info("El programa ya debería haber terminado.")
