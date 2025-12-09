from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel


class DownloadedEpisode(BaseModel):
    episode_number: str
    video_path: Path
    thumbnail_path: Path
    source: Literal["youtube"]


class BaseDownloader(ABC):
    """
    Contrato que deben cumplir todos los descargadores (YouTube, CaracolPlay, etc).
    """

    @abstractmethod
    def find_and_download(
        self, manual_url: Optional[str] = None
    ) -> Optional[DownloadedEpisode]:
        """
        Busca y descarga el episodio del día.
        Debe retornar un objeto DownloadedEpisode con las rutas locales, o None.
        """
        pass
