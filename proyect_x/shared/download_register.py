import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, TypedDict, Union, cast

# Tipo de evento registrado
EventType = Literal["download", "upload", "publication"]
Source = Literal["yt_downloader", "uploader", "orchestrator"]


def get_inodo(path: Union[str, Path]) -> str:
    path = Path(path)
    return f"{path.stat().st_dev}-{path.stat().st_ino}"


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


class RegisterPublication(TypedDict):
    event: EventType
    episode_number: str
    episode_day: str
    timestamp: str
    source: Source


RegistryEntry = Union[RegisterEntry, RegisterVideoUpload, RegisterPublication]
REGISTRY_FILE = Path.cwd() / "registry/download_registry.json"


def _load_registry() -> list[RegistryEntry]:
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error leyendo el archivo de registro: {e}")
            return []
    return []


def _save_registry(
    data: list[RegistryEntry],
) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def register_episode_downloaded(episode: str, file_path: Union[str, Path]):
    data = _load_registry()
    entry: RegisterEntry = {
        "event": "download",
        "episode": episode,
        "timestamp": datetime.now().isoformat(),
        "source": "yt_downloader",
        "file_path": str(file_path),
    }
    data.append(entry)
    _save_registry(data)


def register_video_uploaded(
    message_id: int, chat_id: int, video_path: Union[str, Path]
) -> None:
    video_path = Path(video_path) if isinstance(video_path, str) else video_path
    inodo = get_inodo(video_path)

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


def register_episode_publication(episode: str):
    data = _load_registry()
    entry: RegisterPublication = {
        "event": "publication",
        "episode_number": episode,
        "episode_day": str(datetime.now().date()),
        "timestamp": datetime.now().isoformat(),
        "source": "orchestrator",
    }
    data.append(entry)
    _save_registry(data)
    print(f"Registro de publicación para el episodio {episode} guardado.")


def was_episode_downloaded(episode: str) -> bool:
    data = _load_registry()
    event = "download"
    return any(d.get("episode") == episode and d.get("event") == event for d in data)


def was_video_uploaded(video_path) -> bool:
    data = _load_registry()
    event = "upload"
    video_path = Path(video_path) if isinstance(video_path, str) else video_path
    inodo = get_inodo(video_path)
    return any(d.get("inodo") == inodo and d.get("event") == event for d in data)


def get_video_uploaded(video_path) -> Optional[RegisterVideoUpload]:
    data = _load_registry()
    video_path = Path(video_path) if isinstance(video_path, str) else video_path
    inodo = get_inodo(video_path)
    for entry in data:
        if entry.get("inodo") == inodo and entry.get("event") == "upload":
            return cast(RegisterVideoUpload, entry)
    return None
