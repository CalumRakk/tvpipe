import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, TypedDict, Union, get_args

from series_manager.schemes import QUALITY

SOURCES = Literal["caracol", "ditu", "youtube"]
METHOD_TYPE = Literal["download", "stream_capture"]


class EpisodeDownloaded(TypedDict):
    episode: int
    source: SOURCES
    method: str
    quality: QUALITY
    datetime: str
    filename: Optional[str]


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
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
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
        filename: Optional[str] = None,
    ) -> EpisodeDownloaded:
        episode = int(episode) if isinstance(episode, str) else episode
        assert source in get_args(SOURCES), f"Invalid source: {source}"
        assert method in get_args(METHOD_TYPE), f"Invalid method: {method}"
        assert quality in get_args(QUALITY), f"Invalid quality: {quality}"

        entry: EpisodeDownloaded = {
            "episode": episode,
            "source": source,
            "method": method,
            "quality": quality,
            "datetime": datetime.now().isoformat(),
            "filename": None,
        }

        if filename:
            entry["filename"] = filename

        self.data["downloads"].append(entry)
        self.save()
        return entry

    def get_all_downloads(self):
        return self.data["downloads"]

    def get_last_downloaded_episode(self):
        return self.data["last_episode_downloaded"]

    def __repr__(self):
        return f"<DownloadRegistry(series='{self.data['series_title']}', last_episode={self.data['last_episode_downloaded']})>"
