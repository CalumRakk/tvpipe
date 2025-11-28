import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, TypedDict, Union, cast

# Tipos de eventos y fuentes
EventType = Literal["download", "upload", "publication"]
Source = Literal["yt_downloader", "uploader", "orchestrator"]


# Tipos de registro
class RegisterEntry(TypedDict):
    event: EventType
    episode: str
    timestamp: str
    source: Source
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


class RegistryManager:
    def __init__(self, registry_file: Optional[Union[str, Path]] = None):
        self.registry_file = (
            REGISTRY_FILE if registry_file is None else Path(registry_file)
        )
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[RegistryEntry]:
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error leyendo el archivo de registro: {e}")
        return []

    def _save(self, data: list[RegistryEntry]) -> None:
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _get_inodo(self, path: Union[str, Path]) -> str:
        path = Path(path)
        return f"{path.stat().st_dev}-{path.stat().st_ino}"

    def register_episode_downloaded(
        self, episode: str, file_path: Union[str, Path]
    ) -> None:
        file_path = Path(file_path).resolve()
        entry: RegisterEntry = {
            "event": "download",
            "episode": episode,
            "timestamp": datetime.now().isoformat(),
            "source": "yt_downloader",
            "file_path": str(file_path),
        }
        data = self._load()
        data.append(entry)
        self._save(data)

    def register_video_uploaded(
        self, message_id: int, chat_id: int, video_path: Union[str, Path]
    ) -> None:
        video_path = Path(video_path).resolve()
        inodo = self._get_inodo(video_path)
        entry: RegisterVideoUpload = {
            "event": "upload",
            "source": "uploader",
            "inodo": inodo,
            "timestamp": datetime.now().isoformat(),
            "file_path": str(video_path),
            "message_id": message_id,
            "chat_id": chat_id,
        }
        data = self._load()
        data.append(entry)
        self._save(data)

    def register_episode_publication(self, episode: str) -> None:
        entry: RegisterPublication = {
            "event": "publication",
            "episode_number": episode,
            "episode_day": str(datetime.now().date()),
            "timestamp": datetime.now().isoformat(),
            "source": "orchestrator",
        }
        data = self._load()
        data.append(entry)
        self._save(data)
        print(f"Registro de publicación para el episodio {episode} guardado.")

    def was_episode_downloaded(self, episode: str) -> bool:
        data = self._load()
        return any(
            d.get("episode") == episode and d.get("event") == "download" for d in data
        )

    def was_video_uploaded(self, video_path: Union[str, Path]) -> bool:
        video_path = Path(video_path).resolve()
        inodo = self._get_inodo(video_path)
        data = self._load()
        return any(d.get("inodo") == inodo and d.get("event") == "upload" for d in data)

    def was_episode_published(self, episode_number: str) -> bool:
        """Verifica si un episodio ha sido publicado."""
        data = self._load()
        return any(
            d.get("episode_number") == episode_number
            and d.get("event") == "publication"
            for d in data
        )

    def get_video_uploaded(self, video_path: Union[str, Path]) -> RegisterVideoUpload:
        video_path = Path(video_path).resolve()
        inodo = self._get_inodo(video_path)
        data = self._load()
        for entry in data:
            if entry.get("inodo") == inodo and entry.get("event") == "upload":
                return cast(RegisterVideoUpload, entry)
        raise ValueError(
            f"No se encontró el registro de carga para el video: {video_path}"
        )

    def remove_video_entry(self, video_path: Union[str, Path]) -> None:
        """Elimina las entradas de un video específico para limpiar caché inválido."""
        video_path = Path(video_path).resolve()

        inodo = self._get_inodo(video_path)
        data = self._load()
        new_data = [
            d
            for d in data
            if not (d.get("inodo") == inodo and d.get("event") == "upload")
        ]

        if len(new_data) < len(data):
            self._save(new_data)
            print(f"Entrada inválida eliminada del registro para: {video_path.name}")
