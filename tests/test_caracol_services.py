import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

sys.path.append(os.getcwd())
from tvpipe.services.caracoltv.schedule import CaracolTVSchedule
from tvpipe.services.monitor import ProgramMonitor

MOCK_HTML_CONTENT = """
<html>
<body>
    <div class="ScheduleWeek-days">
        <div data-day="Lunes">
            <!-- Programa 1: Normal (Desafío) -->
            <div class="ScheduleDay-Content-item flex flex-col"
                 data-starttime="1700000000000"
                 data-endtime="1700003600000">
                 <a class="ScheduleDay-media-link"
                    title="Desafío XX"
                    href="https://www.caracoltv.com/desafio"></a>
            </div>

            <!-- Programa 2: El último del día con el bug de timestamp (ej: dice terminar a las 12:00 PM/mediodía) -->
            <!-- Supongamos que start es tarde en la noche -->
            <div class="ScheduleDay-Content-item flex flex-col"
                 data-starttime="1700010000000"
                 data-endtime="1700050000000"> <!-- Timestamp falso para simular el error -->
                 <a class="ScheduleDay-media-link"
                    title="Ultimo Noticiero"
                    href="/noticias"></a>
            </div>
        </div>
    </div>
</body>
</html>
"""


class TestCaracolSchedule(unittest.TestCase):

    def setUp(self):
        self.client = CaracolTVSchedule()

    @patch("tvpipe.services.caracoltv.schedule.requests.get")
    @patch("tvpipe.services.caracoltv.schedule.get_day_name")
    # Para evitar fallo en `get_today_schedule` al iterar sobre otro día
    @patch("tvpipe.services.caracoltv.schedule.DAYS", ("Lunes",))
    def test_parsing_logic(self, mock_day_name, mock_get):
        """Prueba que el HTML se parsea correctamente y se extraen los programas."""

        mock_day_name.return_value = "Lunes"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = MOCK_HTML_CONTENT
        mock_get.return_value = mock_response

        schedule = self.client.get_today_schedule()

        self.assertTrue(len(schedule) >= 1, "Debería encontrar programas")

        # Verificar que encontró el Desafío
        desafio = next((p for p in schedule if "Desafío" in p["title"]), {})
        self.assertIsNotNone(desafio)
        self.assertEqual(desafio["url"], "https://www.caracoltv.com/desafio")
        self.assertIsInstance(desafio["starttime"], datetime)
        self.assertIsInstance(desafio["endtime"], datetime)


class TestProgramMonitor(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock(spec=CaracolTVSchedule)
        self.monitor = ProgramMonitor(
            self.mock_client,
            program_url_keyword="desafio",
            config=MagicMock(),
            fetcher=MagicMock(),
        )

    def test_program_not_found(self):
        """Si el programa no está en la parrilla, debe devolver None."""
        self.mock_client.get_today_schedule.return_value = [
            {"url": "/noticias", "title": "Noticias"},
            {"url": "/novela", "title": "Novela"},
        ]

        info = self.monitor.get_program_info()
        self.assertIsNone(info)

    def test_program_found(self):
        """Si el programa está, debe devolver el diccionario correcto."""
        expected_item = {"url": "https://www.caracoltv.com/desafio", "title": "Desafío"}
        self.mock_client.get_today_schedule.return_value = [
            {"url": "/noticias", "title": "Noticias"},
            expected_item,
        ]

        info = self.monitor.get_program_info()
        self.assertEqual(info, expected_item)

    def test_get_release_time_calculation(self):
        """Prueba que se suma el buffer de 5 minutos al tiempo de fin."""

        end_time = datetime(2025, 1, 1, 21, 0, 0)

        self.mock_client.get_today_schedule.return_value = [
            {"url": "/desafio", "endtime": end_time}
        ]

        release_time = self.monitor.get_release_time()

        expected_time = end_time + timedelta(minutes=5)
        self.assertEqual(release_time, expected_time)

    @patch("tvpipe.services.monitor.datetime")
    def test_should_wait_true(self, mock_datetime):
        """Debe esperar si AHORA es ANTES del release_time."""

        # Escenario:
        # Programa termina: 21:00
        # Release time: 21:05
        # Ahora es: 20:00 -> DEBE ESPERAR (True)

        program_end = datetime(2025, 1, 1, 21, 0, 0)
        now_fake = datetime(2025, 1, 1, 20, 0, 0)

        # Configurar Mocks
        self.mock_client.get_today_schedule.return_value = [
            {"url": "/desafio", "endtime": program_end}
        ]
        mock_datetime.now.return_value = now_fake

        should_wait = self.monitor._should_wait_for_schedule()

        self.assertTrue(should_wait, "Debería indicar que hay que esperar")

    @patch("tvpipe.services.monitor.datetime")
    def test_should_wait_false(self, mock_datetime):
        """NO debe esperar si AHORA es DESPUÉS del release_time."""

        # Escenario:
        # Release time: 21:05
        # Ahora es: 21:10 -> NO DEBE ESPERAR (False)

        program_end = datetime(2025, 1, 1, 21, 0, 0)
        now_fake = datetime(2025, 1, 1, 21, 10, 0)

        self.mock_client.get_today_schedule.return_value = [
            {"url": "/desafio", "endtime": program_end}
        ]
        mock_datetime.now.return_value = now_fake

        should_wait = self.monitor._should_wait_for_schedule()
        self.assertFalse(should_wait, "No debería esperar, ya salió el capítulo")


if __name__ == "__main__":
    unittest.main()
