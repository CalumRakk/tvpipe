import json
from datetime import datetime
from pathlib import Path
from typing import Literal, TypedDict, Union

# Tipo de evento registrado
EventType = Literal["download", "upload"]
Source = Literal["yt_downloader", "uploader"]


class RegisterEntry(TypedDict):
    event: EventType
    episode: str
    timestamp: str
    source: Source  # quien realiza la acción (ej: "yt_downloader", "uploader")
    file_path: str


class RegisterVideoUpload(TypedDict):
    event: EventType
    source: Source
    inodo: str
    timestamp: str
    file_path: str
    message_id: int
    chat_id: int


REGISTRY_FILE = Path("registry/download_registry.json")


def _load_registry() -> list[RegisterEntry | RegisterVideoUpload]:
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_registry(data: list[RegisterEntry | RegisterVideoUpload]) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def register_event(
    episode: str, event: EventType, file_path: Union[str, Path], source: Source
):
    """
    Registra un evento (descarga o subida) de un episodio en el archivo JSON.
    """
    data = _load_registry()
    entry: RegisterEntry = {
        "event": event,
        "episode": episode,
        "timestamp": datetime.now().isoformat(),
        "source": source,
        "file_path": str(file_path),
    }
    data.append(entry)
    _save_registry(data)


def register_video_upload(message_id, chat_id, video_path):
    """
    Registra un evento (descarga o subida) de un episodio en el archivo JSON.
    """

    video_path = Path(video_path) if isinstance(video_path, str) else video_path
    inodo = f"{video_path.stat().st_dev}-{video_path.stat().st_ino}"

    data = _load_registry()
    entry: RegisterVideoUpload = {
        "inodo": inodo,
        "event": "upload",
        "source": "uploader",
        "timestamp": datetime.now().isoformat(),
        "file_path": str(video_path.resolve()),
        "message_id": message_id,
        "chat_id": chat_id,
    }
    data.append(entry)
    _save_registry(data)


def was_episode_registered(episode: str) -> bool:
    """
    Verifica si ya existe un evento registrado para un episodio.
    """
    data = _load_registry()
    event = "download"
    return any(d.get("episode") == episode and d.get("event") == event for d in data)


def was_videopath_registered(video_path):
    data = _load_registry()
    event = "upload"
    video_path = Path(video_path) if isinstance(video_path, str) else video_path
    inodo = f"{video_path.stat().st_dev}-{video_path.stat().st_ino}"
    return any(d.get("inodo") == inodo and d.get("event") == event for d in data)


def get_videopath_registered(video_path):
    """
    Devuelve el registro de un video por su ruta.
    """
    data = _load_registry()
    video_path = Path(video_path) if isinstance(video_path, str) else video_path
    inodo = f"{video_path.stat().st_dev}-{video_path.stat().st_ino}"
    for entry in data:
        if entry.get("inodo") == inodo and entry.get("event") == "upload":
            return entry
    return None


def get_all_events(event: EventType) -> list[RegisterEntry]:
    """
    Devuelve todos los eventos registrados de un tipo específico (download/upload).
    """
    return [e for e in _load_registry() if e["event"] == event]
