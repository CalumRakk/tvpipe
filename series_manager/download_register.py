import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, TypedDict, Union, get_args

from series_manager.schemes import QUALITY

SOURCES = Literal["caracol", "ditu", "youtube"]
METHOD_TYPE = Literal["download", "stream_capture"]
logger = logging.getLogger(__name__)


class EpisodeDownloaded(TypedDict):
    episode: int
    source: SOURCES
    method: str
    quality: QUALITY
    datetime: str
    path: str


class DownloadRegistry:
    def __init__(
        self,
        filepath: Union[str, Path] = "meta/download_registry.json",
        series_title: str = "Desafio Siglo XXI 2025",
    ):
        self.filepath = Path(filepath) if isinstance(filepath, str) else filepath
        self.data = self._load_or_initialize(series_title)

    def _load_or_initialize(self, series_title: str) -> dict:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.warning(f"Error al leer el archivo JSON: {e}")
        return {
            "series_title": series_title,
            "last_episode_downloaded": 0,
            "downloads": [],
        }

    def save(self):
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def is_download_registered(
        self, episode: int, source: str, method: Optional[str] = None
    ) -> bool:
        for entry in self.data["downloads"]:
            if entry["episode"] == episode and entry["source"] == source:
                if method is None or entry["method"] == method:
                    return True
        return False

    def register_download(
        self,
        episode: Union[int, str],
        source: SOURCES,
        method: METHOD_TYPE,
        quality: QUALITY,
        path: Union[str, Path],
    ) -> EpisodeDownloaded:
        episode = int(episode) if isinstance(episode, str) else episode
        path = path if isinstance(path, str) else str(path.resolve())
        assert source in get_args(SOURCES), f"Invalid source: {source}"
        assert method in get_args(METHOD_TYPE), f"Invalid method: {method}"
        assert type(quality) in get_args(QUALITY) or quality in get_args(
            QUALITY
        ), f"Invalid quality: {quality}"

        entry: EpisodeDownloaded = {
            "episode": episode,
            "source": source,
            "method": method,
            "quality": quality,
            "datetime": datetime.now().isoformat(),
            "path": path,
        }

        self.data["downloads"].append(entry)
        self.save()
        return entry

    def get_all_downloads(self):
        return self.data["downloads"]

    def get_last_downloaded_episode(self):
        return self.data["last_episode_downloaded"]

    def __repr__(self):
        return f"<DownloadRegistry(series='{self.data['series_title']}', last_episode={self.data['last_episode_downloaded']})>"

    def get_download_episodes(self, number: Union[int, str]) -> list[EpisodeDownloaded]:
        number = int(number) if isinstance(number, str) else number
        episodes = []
        for episode in self.data["downloads"]:
            if episode["episode"] == number and Path(episode["path"]).exists():
                episodes.append(episode)

        return episodes
