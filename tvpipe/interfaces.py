from abc import ABC, abstractmethod
from typing import Optional

from tvpipe.services.youtube.models import DownloadedEpisode


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
