import datetime
import locale
from datetime import datetime, timedelta
from typing import Optional

import requests
from lxml import etree
from unidecode import unidecode

DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
URL_SCHEDULE = "https://www.caracoltv.com/programacion"


def get_day():
    hoy = datetime.today().weekday()  # 0=lunes, 6=domingo
    return DAYS[hoy].capitalize()


class CaracolTV:
    """
    Clase para manejar la descarga de series de Caracol TV.
    """

    def _maker_request(self, url):
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-language": "es-ES,es;q=0.5",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "sec-gpc": "1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        }

        response = requests.get(url, headers=headers)
        return response

    def _get_root(self, url):
        response = self._maker_request(url)
        if response.status_code == 200:
            root = etree.HTML(response.text)  # type: ignore
            return root
        else:
            raise Exception(
                f"Error al obtener el contenido de {url}: {response.status_code}"
            )

    def _get_data_element(self, item):
        data_element = item.find(".//a[@class='ScheduleDay-media-link']")
        if data_element is None:
            return item.find(".//span[@class='ScheduleDay-media-link']")
        return data_element

    def _extract_schedule_day(self, root, day):
        schedule_today = root.find(
            f".//div[@class='ScheduleWeek-days']/div[@data-day='{day}']"
        )
        scheduls = []
        items = schedule_today.xpath(
            ".//div[@class='ScheduleDay-Content-item flex flex-col']"
        )
        for index, item in enumerate(items):
            data_element = self._get_data_element(item)
            if data_element is None:
                continue
            starttime_milliseconds = int(item.get("data-starttime"))
            endtime_milliseconds = int(item.get("data-endtime"))

            starttime = datetime.fromtimestamp(starttime_milliseconds / 1000)
            endtime = datetime.fromtimestamp(endtime_milliseconds / 1000)
            if index == len(items) - 1:
                # Corrección al timestamp del último ítem:
                # En todos los casos observados, el sitio devuelve un valor incorrecto de finalización para el último programa del día.
                # En lugar de un horario nocturno (como 23:30 o 00:00), devuelve exactamente las 12:00 PM (mediodía),
                # lo que causa que el programa parezca terminar antes que los anteriores.
                # Como solución, se asume que debería finalizar 12 horas después, y se ajusta sumando ese tiempo.
                if endtime.hour == 12 and endtime.minute == 0:
                    endtime = endtime + timedelta(hours=12)
                elif endtime.hour == 0 and endtime.minute == 0:
                    endtime = endtime + timedelta(hours=24)
                else:
                    # Algunos programas cruzan medianoche pero el sitio no ajusta el día.
                    # Sumamos 1 día para corregir.
                    # ejemplo : inicia deesde las 11PM hasta la 1PM, pero el timestamp sigue en el mismo día.
                    endtime = endtime + timedelta(days=1)

            title = data_element.get("title")
            url = data_element.get("href") or ""
            is_live = starttime <= datetime.now() <= endtime
            was_live = datetime.now() > endtime
            assert starttime < endtime, f"El inicio de {title} es posterior al fin."
            scheduls.append(
                {
                    "title": title,
                    "starttime": starttime,
                    "endtime": endtime,
                    "starttime12hour": starttime.strftime("%Y-%m-%d %I:%M %p"),
                    "endtime12hour": endtime.strftime("%Y-%m-%d %I:%M %p"),
                    "url": url,
                    "is_live": is_live,
                    "was_live": was_live,
                    "day": day,
                }
            )
            # TODO: El valor de `day` esta en español, pero se usa key de dict en ingles.
        return scheduls

    def get_schedule(self):
        """Obtiene laprogramación para el día actual."""
        day = get_day()
        return self.get_schedule_by_day(day)

    def get_schedule_desafio(
        self,
    ) -> Optional[dict]:
        """Obtiene la programación del dia actual del desafío o None si no hay programa.."""
        schedule = self.get_schedule()
        for item in schedule:
            # Se usa la URL del desafío para identificar el programa
            if "https://www.caracoltv.com/desafio" in item.get("url", ""):
                return item

    def get_schedule_by_day(self, day) -> dict:
        """Obtiene la programación para un día específico.
        Args:
            day (str): Nombre del día en español (ej. "Lunes", "Martes", etc.). Soporta excluir acentos.
        """
        root = self._get_root(URL_SCHEDULE)
        day_target = unidecode(day).lower()
        schedule_all = {}
        for DAY in DAYS:
            schedule = self._extract_schedule_day(root, DAY)
            key = unidecode(DAY).lower()
            schedule_all[key] = schedule
        if day_target in schedule_all:
            return schedule_all[day_target]
        raise ValueError(
            f"El día '{day}' no es válido. Debe ser uno de: {', '.join(DAYS)}"
        )


if __name__ == "__main__":
    caracol = CaracolTV()
    schedule = caracol.get_schedule_desafio()
    print(schedule)
