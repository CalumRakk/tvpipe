from datetime import datetime, time, timedelta
from typing import List, Optional, cast

import requests
from unidecode import unidecode

from proyect_x.ditu.schemas.common import ChannelInfo, ProgramMetadata
from proyect_x.ditu.schemas.entitlement_response import EntitlementChannelResponse
from proyect_x.ditu.schemas.filder_response import FilterResponse
from proyect_x.ditu.schemas.raw_schedule_response import (
    ChannelItem,
    ProgramItem,
    RawTVScheduleResponse,
)
from proyect_x.ditu.schemas.simple_schedule import CurrentSchedule, SimpleSchedule

HEADERS = {
    "Restful": "yes",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "okhttp/4.12.0",
}


class DituSchedule:
    def get_current_program_live(self, channel_id: int) -> CurrentSchedule:
        """Obtiene informacion del programa actualmente en emision de un canal."""
        url = "https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/TRAY/SEARCH/PROGRAM"
        params = {
            "filter_channelIds": str(channel_id),
            "filter_airingTime": "now",
        }
        response = requests.get(url, params=params, headers=HEADERS)
        response.raise_for_status()
        filter = response.json()
        item = filter["resultObj"]["containers"][0]
        data = item["metadata"]
        channel_info = item["channel"]
        return CurrentSchedule(
            contentId=data["contentId"],
            title=data["title"],
            longDescription=data["longDescription"],
            duration=data["duration"],
            airingStartTime=data["airingStartTime"],
            airingEndTime=data["airingEndTime"],
            episodeId=data["episodeId"],
            episodeTitle=data["episodeTitle"],
            season=data["season"],
            channel_info=channel_info,
        )

    def _get_entitlements_for_live_channel(
        self, channel_id: int
    ) -> EntitlementChannelResponse:
        """Obtiene la información de derechos de reproducción ("entitlement") y los assets disponibles (por ejemplo, LIVE_HD) para una transmisión en vivo del canal especificado. Sirve para determinar si el canal puede reproducirse y qué assets están disponibles, incluyendo su assetId, que puede usarse en otro endpoint (como el de VIDEOURL).

        Nota: No se usa de momento.
        """
        url = "https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/CONTENT/USERDATA/LIVE/20"
        params = {
            "filter_channelIds": str(channel_id),
            "filter_entitlementType": "live",
        }
        response = requests.get(url, params=params, headers=HEADERS)
        response.raise_for_status()
        return response.json()

    def _get_day_range_timestamps_ms(self) -> tuple[str, str]:
        """Obtiene los timestamps de inicio y fin de un día."""
        start_day = time(0, 0, 0)  # 00:00:00
        end_day = time(23, 59, 59, 999000)  # 23:59:59.999
        today = datetime.now().date()
        start_dt = datetime.combine(today, start_day)  # 00:00:00
        end_dt = datetime.combine(today, end_day) + timedelta(hours=3)  # 23:59:59.999
        start_ts_ms = int(start_dt.timestamp() * 1000)
        end_ts_ms = int(end_dt.timestamp() * 1000)
        return str(start_ts_ms), str(end_ts_ms)

    def _fetch_raw_channels_schedule(self) -> RawTVScheduleResponse:
        """Obtiene la programación de todos los canales de la TV."""
        start_ms, end_ms = self._get_day_range_timestamps_ms()
        url = "https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/TRAY/EPG"
        params = {
            "orderBy": "orderId",
            "sortOrder": "asc",
            "filter_startTime": start_ms,
            "filter_endTime": end_ms,
        }

        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json()

    def _extract_simpleprogram(self, program_item: ProgramItem) -> SimpleSchedule:

        data = program_item["metadata"]
        channel_info = program_item["channel"]
        airingStartTime = data["airingStartTime"]
        end_time = data["airingEndTime"]
        title = data["title"]
        content_id = data["contentId"]
        long_description = data["longDescription"]
        episode_title = data["episodeTitle"]
        episode_number = data["episodeNumber"]
        season = data["season"]
        duration = data["duration"]
        episode_id = data["episodeId"]
        return SimpleSchedule(
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
            channel_info=channel_info,
        )

    def _extract_channel_info(self, channel_item: ChannelItem) -> ChannelInfo:
        for program_item in channel_item["containers"]:
            return program_item["channel"]
        raise ValueError("No se encontró ProgramItem para el canal")

    def get_schedule_by_id(self, channel_id: int) -> list[SimpleSchedule]:
        """Obtiene la programación de un canal de la TV."""
        json_data = self._fetch_raw_channels_schedule()
        schedules = []
        for channel_item in json_data["resultObj"]["containers"]:
            channel_info = self._extract_channel_info(channel_item)
            if channel_info["channelId"] == channel_id:
                for program_item in channel_item["containers"]:
                    simple = self._extract_simpleprogram(program_item)
                    schedules.append(simple)
        return schedules

    def get_schedule_for_desafio(self) -> List[SimpleSchedule]:
        schedule = self.get_schedule_by_id(43)  # ID del canal "Desafío Siglo XXI"
        if schedule:
            return schedule
        raise ValueError("No se encontró programación para el canal Desafío Siglo XXI")

    def get_schedule_for_caracoltv(self):
        schedule = self.get_schedule_by_id(20)  # ID del canal Caracol TV
        if schedule:
            return schedule
        raise ValueError("No se encontró programación para el canal Caracol TV")

    def get_schedule_by_name(self, channel_name: str) -> list[SimpleSchedule]:
        json_data = self._fetch_raw_channels_schedule()
        schedules = []
        for channel_item in json_data["resultObj"]["containers"]:
            channel_info = self._extract_channel_info(channel_item)
            channel_name_target = unidecode(channel_info["channelName"].lower())
            if unidecode(channel_name.lower()) in channel_name_target:
                for program_item in channel_item["containers"]:
                    simple = self._extract_simpleprogram(program_item)
                    schedules.append(simple)
        return schedules
