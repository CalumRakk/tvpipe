from datetime import datetime, timedelta

from pydantic import BaseModel

from proyect_x.ditu.schemas.common import ChannelInfo


class CurrentSchedule(BaseModel):
    contentId: int
    title: str
    longDescription: str
    duration: int
    airingStartTime: int
    airingEndTime: int
    episodeId: int
    episodeTitle: str
    season: int
    channel_info: dict

    @property
    def content_id(self) -> int:
        return self.contentId

    @property
    def start_time(self) -> datetime:
        return datetime.fromtimestamp(self.airingStartTime / 1000)

    @property
    def end_time(self) -> datetime:
        return datetime.fromtimestamp(self.airingEndTime / 1000)

    @property
    def start_time_as_12hours(self) -> str:
        return self.start_time.strftime("%I:%M %p")

    @property
    def end_time_as_12hours(self) -> str:
        return self.end_time.strftime("%I:%M %p")


class SimpleSchedule(BaseModel):
    contentId: int
    title: str
    shortDescription: str

    airingStartTime: int
    airingEndTime: int
    duration: int

    episodeId: int
    episodeTitle: str
    episodeNumber: int
    season: int

    channel_info: dict

    @property
    def content_id(self) -> int:
        return self.contentId

    @property
    def episode_id(self) -> int:
        return self.episodeId

    @property
    def episode_number(self) -> int:
        return self.episodeNumber

    @property
    def episode_title(self) -> str:
        return self.episodeTitle.strip()

    @property
    def short_description(self) -> str:
        return self.shortDescription.strip()

    @property
    def start_time(self) -> datetime:
        return datetime.fromtimestamp(self.airingStartTime / 1000)

    @property
    def end_time(self) -> datetime:
        return datetime.fromtimestamp(self.airingEndTime / 1000)

    @property
    def start_time_as_12hours(self) -> str:
        return self.start_time.strftime("%I:%M %p")

    @property
    def end_time_as_12hours(self) -> str:
        return self.end_time.strftime("%I:%M %p")

    @property
    def channel_id(self) -> int:
        return self.channel_info["channelId"]

    @property
    def channel_name(self) -> str:
        return self.channel_info["channelName"]

    @property
    def has_started(self) -> bool:
        """True y solo True si el programa se considerará como "Iniciado".
        Se considera como "Iniciado" si el programa está en emision o falta menos de un minuto para comenzar.

        Si el programa ha finalizado, no se considera "Iniciado".
        """
        delta = datetime.now() - self.start_time
        minutes = int(delta.total_seconds() / 60)

        start = self.start_time - timedelta(minutes=13)
        has_finished_program = self.end_time <= datetime.now()
        is_on_air = (start <= datetime.now()) and (not has_finished_program)
        return is_on_air and (minutes <= 3)
