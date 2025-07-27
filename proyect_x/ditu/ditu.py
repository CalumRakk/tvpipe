from datetime import datetime, time, timedelta
from typing import List, Optional

import requests

from proyect_x.ditu.schemas import ChannelInfo, RawTVScheduleResponse, SimpleSchedule


def get_day_range_timestamps_ms() -> tuple[str, str]:

    start_day = time(0, 0, 0)  # 00:00:00
    end_day = time(23, 59, 59, 999000)  # 23:59:59.999
    today = datetime.now().date()
    start_dt = datetime.combine(today, start_day)  # 00:00:00
    end_dt = datetime.combine(today, end_day) + timedelta(hours=3)  # 23:59:59.999
    start_ts_ms = int(start_dt.timestamp() * 1000)
    end_ts_ms = int(end_dt.timestamp() * 1000)
    return str(start_ts_ms), str(end_ts_ms)


HEADERS = {
    "Restful": "yes",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "okhttp/4.12.0",
}


class Ditu:

    def _fetch_raw_channels_schedule(self) -> RawTVScheduleResponse:
        start_ms, end_ms = get_day_range_timestamps_ms()
        url = "https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/TRAY/EPG"
        params = {
            "orderBy": "orderId",
            "sortOrder": "asc",
            "filter_startTime": start_ms,
            "filter_endTime": end_ms,
        }
        headers = {
            "User-Agent": "okhttp/4.12.0",
            "Accept-Encoding": "gzip, deflate, br",
        }

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_all_channel_info(self) -> list[ChannelInfo]:
        """
        Extrae información clave de todos los canales presentes en el archivo de programación.

        Retorna una lista de diccionarios con los campos:
        - channelId
        - channelName
        """
        canales = set()
        resultado = []
        raw_data = self._fetch_raw_channels_schedule()
        for canal in raw_data.get("resultObj", {}).get("containers", []):
            for emocion in canal.get("containers", []):
                channel = emocion.get("channel")
                if channel:
                    canal_id = channel.get("channelId")
                    canal_nombre = channel.get("channelName")
                    clave = (canal_id, canal_nombre)
                    if clave not in canales:
                        canales.add(clave)
                        resultado.append(
                            {"channelId": canal_id, "channelName": canal_nombre}
                        )
        return resultado

    def get_schedule_for_channel(
        self, channel_id: int
    ) -> Optional[list[SimpleSchedule]]:
        rawschedule = self._fetch_raw_channels_schedule()

        for canal in rawschedule["resultObj"]["containers"]:
            if canal["metadata"]["channelId"] == channel_id:
                contents = canal["containers"]
                schedules = []
                for data in [i["metadata"] for i in contents]:
                    airingStartTime = data["airingStartTime"]
                    end_time = data["airingEndTime"]
                    title = data["title"].strip()
                    content_id = data["contentId"]
                    long_description = data["longDescription"].strip()
                    episode_title = data["episodeTitle"].strip()
                    episode_number = data["episodeNumber"]
                    season = data["season"]
                    duration = data["duration"]
                    episode_id = data["episodeId"]

                    schedules.append(
                        SimpleSchedule(
                            contentId=content_id,
                            title=title,
                            shortDescription=long_description,
                            airingStartTime=airingStartTime,
                            airingEndTime=end_time,
                            duration=duration,
                            episodeId=episode_id,
                            episodeTitle=episode_title,
                            episodeNumber=episode_number,
                            season=season,
                        )
                    )
                return schedules

    def get_schedule_for_desafio(self) -> List[SimpleSchedule]:
        schedule = self.get_schedule_for_channel(43)  # ID del canal "Desafío Siglo XXI"
        if schedule:
            return schedule
        raise ValueError("No se encontró programación para el canal Desafío Siglo XXI")

    def get_schedule_for_caracoltv(self):
        schedule = self.get_schedule_for_channel(20)  # ID del canal Caracol TV
        if schedule:
            return schedule
        raise ValueError("No se encontró programación para el canal Caracol TV")

    # def get_live_program(self, channel_info: ChannelInfo) -> Optional[SimpleSchedule]:
    #     url = "https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/TRAY/SEARCH/PROGRAM"
    #     params = {
    #         "filter_channelIds": str(channel_info["channelId"]),
    #         "filter_airingTime": "now",
    #     }
    #     response = requests.get(url, params=params, headers=HEADERS)
    #     response.raise_for_status()
    #     data = response.json()
