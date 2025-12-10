from abc import ABC, abstractmethod
from typing import Optional

from tvpipe.schemas import VideoMetadata


class BaseDownloader(ABC):
    """
    Contrato que deben cumplir todos los descargadores (YouTube, CaracolPlay, etc).
    """

    @abstractmethod
    def fetch_episode(self) -> Optional[VideoMetadata]:
        """
        Obtiene los metadatos del video a descargar.
        """
        pass


class EpisodeParser(ABC):
    """
    Define las reglas para identificar y procesar títulos de episodios.
    """

    @abstractmethod
    def matches_criteria(self, title: str) -> bool:
        """Devuelve True si el video es un episodio válido que debemos descargar."""
        pass

    @abstractmethod
    def extract_number(self, title: str) -> str:
        """Extrae el número del episodio. Asume que matches_criteria ya pasó."""
        pass
