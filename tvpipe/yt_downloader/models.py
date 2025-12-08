from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field


class Stream(BaseModel):
    format_id: str
    url: Optional[str] = None
    ext: str

    # Datos técnicos
    vcodec: str = "none"
    acodec: str = "none"
    height: Optional[int] = None
    width: Optional[int] = None
    fps: Optional[float] = None

    filesize: Optional[int] = None
    filesize_approx: Optional[int] = None

    @computed_field
    def size_bytes(self) -> int:
        """Devuelve el tamaño real o aproximado, o 0 si no existe."""
        return self.filesize or self.filesize_approx or 0

    @property
    def is_video(self) -> bool:
        return self.vcodec != "none" and "video" not in self.vcodec

    @property
    def is_audio_only(self) -> bool:
        return self.acodec != "none" and self.vcodec == "none"

    @property
    def is_h264(self) -> bool:
        """Verifica si es compatible con MP4 estándar (avc1)."""
        return "avc1" in (self.vcodec or "").lower()

    @property
    def is_aac(self) -> bool:
        """Verifica si es audio compatible con MP4 estándar (mp4a)."""
        return "mp4a" in (self.acodec or "").lower()


class VideoMetadata(BaseModel):
    id: str
    title: str
    thumbnail_url: Optional[str] = None
    duration: Optional[int] = None
    streams: List[Stream] = Field(default_factory=list)
    timestamp: int
    was_live: bool


class DownloadedEpisode(BaseModel):
    episode_number: str
    video_path: Path
    thumbnail_path: Path
