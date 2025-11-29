from datetime import time
from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Union

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramConfig(BaseSettings):
    """
    Configuración exclusiva para el servicio de Telegram.
    Prefijo en .env: TELEGRAM_ (ej: TELEGRAM_API_ID)
    """

    api_id: int
    api_hash: str
    session_name: str

    # Soporta una lista de IDs (ints) o alias (strs).
    # En el .env se pone: TELEGRAM_CHAT_IDS="-100123, -100456, me"
    chat_ids: Union[List[Union[int, str]], str]

    chat_id_temporary: Union[int, str] = "me"
    caption: str = "Capítulo {episode} - Desafío Siglo XXI\n\n"

    model_config = SettingsConfigDict(
        env_file="config.env",
        env_file_encoding="utf-8",
        env_prefix="TELEGRAM_",
        extra="ignore",  # Ignora variables que no sean TELEGRAM_
    )

    @field_validator("chat_ids", mode="before")
    @classmethod
    def parse_chat_ids(cls, v):
        if isinstance(v, str):
            # Convierte string separado por comas en lista
            cleaned = []
            for item in v.split(","):
                item = item.strip()
                if not item:
                    continue
                # Intentar convertir a int si es numérico
                if item.lstrip("-").isdigit():
                    cleaned.append(int(item))
                else:
                    cleaned.append(item)
            return cleaned
        return v


class DownloaderConfig(BaseSettings):
    """
    Configuración para la descarga y el scraper.
    Prefijo en .env: YT_ (ej: YT_SERIE_NAME)
    """

    serie_name: str = "desafio siglo xxi 2025"
    download_folder: Path = Path("output/")

    # Lista de calidades: YT_QUALITIES="best, 360"
    qualities: Union[List[Union[int, str]], str] = ["best", "360"]

    output_as_mp4: bool = True
    skip_weekends: bool = True
    check_episode_publication: bool = True

    # Configuración de modo y horarios
    url: Union[str, None] = None  # Si se define, es modo manual
    release_hour: time = time(21, 30)

    model_config = SettingsConfigDict(
        env_file="config.env",
        env_file_encoding="utf-8",
        env_prefix="YT_",
        extra="ignore",  # Ignora variables que no sean YT_
    )

    @computed_field
    @property
    def serie_slug(self) -> str:
        """Slug normalizado para nombres de archivo."""
        return self.serie_name.strip().replace(" ", ".").replace("/", "-").lower()

    @field_validator("qualities", mode="before")
    @classmethod
    def parse_qualities(cls, v):
        if isinstance(v, str):
            return [x.strip().lower() for x in v.split(",")]
        return v


class ProjectConfig(BaseSettings):
    """Configuración general del proyecto."""

    project_name: str = "toTelegram"
    env_state: Literal["dev", "prod"] = "dev"

    model_config = SettingsConfigDict(
        env_file="config.env", env_prefix="PROJECT_", extra="ignore"
    )


class AppConfig:
    """
    Clase orquestadora que agrupa las configuraciones.
    No es un modelo de Pydantic, es un contenedor simple.
    """

    def __init__(self, env_path: Path):
        self.project = ProjectConfig(_env_file=env_path)  # type: ignore
        self.telegram = TelegramConfig(_env_file=env_path)  # type: ignore
        self.youtube = DownloaderConfig(_env_file=env_path)  # type: ignore


@lru_cache()
def get_config(env_path: Union[str, Path] = "config.env") -> AppConfig:
    """
    Singleton para obtener la configuración cargada.
    Permite especificar una ruta de archivo .env personalizada.
    """
    path = Path(env_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Error Crítico: No se encontró el archivo de configuración en: {path.absolute()}"
        )

    return AppConfig(env_path=path)
