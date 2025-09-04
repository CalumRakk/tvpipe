from datetime import datetime, time
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    project_name: str

    youtube_release_time: time = time(hour=21, minute=30)
    start_stream_capture: time = time(hour=19, minute=55)
    end_stream_capture: time = time(hour=21, minute=45)

    @field_validator("end_stream_capture")
    def validate_times(cls, end_time, values):
        start_time = values.get("start_stream_capture")
        if start_time and end_time <= start_time:
            raise ValueError("La hora de fin debe ser posterior a la hora de inicio")
        return end_time

    class Config:
        env_file = ".env"


config = Settings()
