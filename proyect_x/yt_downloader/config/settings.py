import os
from datetime import time
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, Optional, get_args

from pydantic import (
    Field,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from proyect_x.yt_downloader.schemas import QUALITY, RELEASE_MODE


class AppSettings(BaseSettings):
    """
    Configuración central del sistema, con valores por defecto y soporte para archivos .env
    """

    # Configuración general
    mode: RELEASE_MODE = Field(default=RELEASE_MODE.AUTO)
    env_name: str = Field(default="default")
    serie_name: str = Field(default="desafio siglo xxi 2025")
    download_folder: Path = Field(default=Path("output/"))
    skip_weekends: bool = Field(default=True)
    output_as_mp4: bool = Field(default=True)
    url: Optional[str] = Field(
        default=None,
        description="Especificar URL del capitulo, es usar el programa en modo manual. Ignora el filtro de fin se semana y hora de publicacion y obtencion de url.",
    )
    check_episode_publication: bool = Field(default=True)

    # Horarios para modo manual
    release_hour: time = Field(default=time(21, 30))
    # end_hour: time = Field(default=time(23, 0))

    # Lista de calidades a descargar
    qualities: str = Field(default="best, 360")

    @field_validator("qualities", mode="after")
    @classmethod
    def validate_qualities(cls, values: str):
        if "," in values:
            parsed = []
            for value in values.split(","):
                parsed.append(value.strip().lower())
            return parsed
        else:
            return [values]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @computed_field
    @property
    def serie_slug(self) -> str:
        """
        Devuelve el nombre de la serie en formato normalizado (sin espacios, solo caracteres seguros).
        """
        return self.serie_name.strip().replace(" ", ".").replace("/", "-").lower()

    # @model_validator(mode="after")
    # def validate_time_range(self) -> "AppSettings":
    #     if self.mode == "manual" and self.release_hour >= self.end_hour:
    #         raise ValueError("En modo manual, release_hour debe ser menor que end_hour")
    #     elif self.mode == "manual" and self.release_hour == self.end_hour:
    #         raise ValueError(
    #             "En modo manual, release_hour y end_hour deben ser diferentes"
    #         )
    #     elif self.mode == "auto" and self.end_hour < self.release_hour:
    #         raise ValueError(
    #             "En modo automático, end_hour debe ser mayor que release_hour"
    #         )
    #     return self


@lru_cache()
def get_settings(env_path: Path | None = None) -> AppSettings:
    """
    Carga configuración desde un archivo .env (si se proporciona) o usa valores por defecto.
    """
    if env_path:
        env_path = Path(env_path) if not env_path.is_absolute() else env_path
        if not env_path.exists():
            raise FileNotFoundError(
                f"El archivo de configuración {env_path} no existe."
            )

        try:
            return AppSettings(_env_file=env_path)  # type: ignore
        except ValidationError as e:
            print("❌ Error en configuración:", e)
            raise
    return AppSettings()
