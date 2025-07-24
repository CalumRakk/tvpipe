import os
from datetime import time
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, List, Literal, Sequence, Union, get_args

from pydantic import Field, ValidationError, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    api_hash: str
    api_id: int
    chat_id: Union[str, int] = Field(default="")
    project_name: str = Field(
        default="toTelegram"
    )  # TODO: Este valor está acoplado a otro proyecto. Hay que deseacoplar del otro proyecto.
    session_name: str  # Más de lo mismo, acoplado a otro proyecto. Este valor es una session pyrogram almacenada en un archivo .session

    caption: str = Field(default="Capítulo {episode} - Desafío Siglo XXI\n\n")
    thumbnail_path: str = Field(default="thumbnail_watermarked.jpg")
    forward: Sequence[Union[str, int]] = Field(default_factory=list)

    video_paths: str

    @field_validator("video_paths", mode="after")
    @classmethod
    def validate_qualities(cls, values: str):
        if "," in values:
            parsed = []
            for value in values.split(","):
                path = Path(value.strip()).resolve()
                if not path.exists():
                    raise FileNotFoundError(f"El archivo {path} no existe.")
                parsed.append(path)
            return parsed
        else:
            return [Path(values).resolve()]


@lru_cache()
def get_settings(env_path: Union[Path, str]) -> AppSettings:
    """
    Carga configuración desde un archivo .env (si se proporciona) o usa valores por defecto.
    """
    env_path = Path(env_path) if isinstance(env_path, str) else env_path
    if not env_path.exists():
        raise FileNotFoundError(f"El archivo de configuración {env_path} no existe.")

    try:
        return AppSettings(_env_file=env_path)  # type: ignore
    except ValidationError as e:
        print("❌ Error en configuración:", e)
        raise
