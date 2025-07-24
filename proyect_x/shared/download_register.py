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


REGISTRY_FILE = Path("registry/download_registry.json")


def _load_registry() -> list[RegisterEntry]:
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_registry(data: list[RegisterEntry]) -> None:
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


def was_event_registered(episode: str, event: EventType) -> bool:
    """
    Verifica si ya existe un evento registrado para un episodio.
    """
    data = _load_registry()
    return any(d["episode"] == episode and d["event"] == event for d in data)


def get_all_events(event: EventType) -> list[RegisterEntry]:
    """
    Devuelve todos los eventos registrados de un tipo específico (download/upload).
    """
    return [e for e in _load_registry() if e["event"] == event]
