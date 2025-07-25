import logging
import os
from datetime import time
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, List, Literal, Optional, Sequence, Union, get_args

from pydantic import Field, ValidationError, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    api_hash: str
    api_id: int
    chat_id_temporary: Union[str, int] = Field(default="me")
    project_name: str = Field(
        default="toTelegram"
    )  # TODO: Este valor está acoplado a otro proyecto. Hay que deseacoplar del otro proyecto.
    session_name: str  # Más de lo mismo, acoplado a otro proyecto. Este valor es una session pyrogram almacenada en un archivo .session
    caption: str = Field(default="Capítulo {episode} - Desafío Siglo XXI\n\n")
    chat_ids: str = Field()

    @field_validator("chat_ids", mode="after")
    @classmethod
    def validate_forward(cls, values: str):
        values = values + "," if "," in values else values
        parsed = []
        for value in values.split(","):
            if value.strip().isdigit():
                parsed.append(int(value.strip()))
            else:
                parsed.append(value.strip())
        return parsed


@lru_cache()
def get_settings(env_path: Union[Path, str]) -> AppSettings:
    """
    Carga configuración desde un archivo .env
    """
    logger = logging.getLogger(__name__)
    env_path = Path(env_path) if isinstance(env_path, str) else env_path
    try:
        if env_path.exists():
            config = AppSettings(_env_file=env_path)  # type: ignore
            logger.info(f"Configuración cargada desde {env_path}")
            return config
        raise FileNotFoundError(f"El archivo de configuración {env_path} no existe.")
    except ValidationError as e:
        print("❌ Error en configuración:", e)
        raise
