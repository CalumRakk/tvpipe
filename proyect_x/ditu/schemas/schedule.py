from datetime import datetime
from typing import TypedDict

from pydantic import BaseModel

from .container import ResultObj


class RawTVScheduleResponse(TypedDict):
    resultCode: str
    message: str
    errorDescription: str
    resultObj: ResultObj


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

    @property
    def content_id(self) -> int:
        return self.contentId

    @property
    def episode_id(self) -> int:
        return self.episodeId

    @property
    def episode_number_str(self) -> int:
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
