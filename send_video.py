import json
import logging
from os import getenv
from pathlib import Path
from platform import system
from typing import Union, cast

from pydantic import BaseModel
from pyrogram import Client  # type: ignore
from pyrogram.types import InputMediaVideo, Message
from tqdm import tqdm  # type: ignore

from config import API_HASH, API_ID, CHAT_ID, PROJECT_NAME
from series_manager.utils import get_video_metadata

CACHE_PATH = "meta/upload_cache.json"
logger = logging.getLogger(__name__)


class Video(BaseModel):
    path: str
    duration: int
    width: int
    height: int
    size: int
    size_mb: int
    format_name: str


def progress(current, total, step=10):
    # Solo imprime cuando se cruza un múltiplo de step
    percentage = current * 100 / total
    if percentage % step < (100 / total):
        print(f"{percentage:.1f}%")


def load_cache() -> dict[str, dict]:
    if Path(CACHE_PATH).exists():
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict[str, dict]):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4)


def clear_cache():
    Path(CACHE_PATH).unlink(missing_ok=True)


def get_videos(video_paths: list[str]) -> list[Video]:
    """Devuelve una lista de videos (Video)."""
    videos: list[Video] = []
    for video_path in video_paths:
        metadata = get_video_metadata(video_path)
        videos.append(Video(**metadata))

    videos.sort(key=lambda x: x.size)
    return videos


def send_videos(
    client: Client, chat_id: Union[int, str], videos: list[Video], thumbnail_path: str
) -> list[Message]:
    """Sube los videos a Telegram y devuelve una lista de mensajes."""
    # TODO: La orientacion de una miniatura especificada (horizontal o vertical), debe coincidir con la del video sino, la miniatura se redimensionara de forma incorrecta.
    cache = load_cache()
    messages = []
    for video in videos:
        video_path = Path(video.path)
        video_inodo = f"{video_path.stat().st_dev}-{video_path.stat().st_ino}"
        if video_inodo in cache:
            print(f"✔ Video ya subido: {video_path}")
            message = client.get_messages(chat_id, cache[video_inodo]["message_id"])
            messages.append(message)
            continue

        message = cast(
            Message,
            client.send_video(
                chat_id=chat_id,
                video=video.path,
                file_name=video_path.name,
                caption=video_path.name,
                progress=progress,
                duration=video.duration,
                width=video.width,
                height=video.height,
                thumb=thumbnail_path,
                disable_notification=True,
            ),
        )
        cache[video_inodo] = {
            "message_id": message.id,
            "file_id": message.video.file_id,
            "video_path": video.path,
        }
        save_cache(cache)
        messages.append(message)
    return messages


def resend_videos_as_media_group(
    client: Client, chat_id: Union[int, str], caption: str, messages: list[Message]
) -> list[Message]:
    """Reenvia los videos como un grupo de medios, con un caption personalizado."""
    media_group = []
    for index, message in enumerate(messages):
        file_id = message.video.file_id
        inputmediavideo = InputMediaVideo(
            media=file_id, caption=caption if index == 0 else ""
        )
        media_group.append(inputmediavideo)
    messages = cast(list[Message], client.send_media_group(chat_id, media_group))
    return messages


def add_subcaption(caption: str, videos: list[Video]) -> str:
    caption = caption
    for video in videos:
        caption = caption + f"{video.format_name}: {video.size_mb} MB\n"
    return caption


def get_client_started(session_name: str = "leo") -> Client:
    # Nota: Se usa una session que contiene pers guardados y permiten interactuar con varios chats de la cuenta.
    # FIXME: Corregir, el script está acoplado a esta sesión (session_name). En caso que no exista la session se debe crear manualmente.
    HOME = (
        Path.home() / ".local/share"
        if system() == "Linux"
        else Path(cast(str, getenv("APPDATA")))
    )
    WORKTABLE = HOME / PROJECT_NAME

    client = Client(
        session_name,
        api_id=API_ID,
        api_hash=API_HASH,
        workdir=str(WORKTABLE),
    )
    client.start()  # type: ignore
    return client


def main(
    chat_id: Union[int, str], caption: str, video_paths: list[str], thumbnail_path: str
):
    logger.info("Iniciando el envío de videos a Telegram")
    videos = get_videos(video_paths)
    client = get_client_started()
    caption_final = add_subcaption(caption, videos)
    messages = send_videos(client, chat_id, videos, thumbnail_path)
    resend_videos_as_media_group(
        client, chat_id, caption=caption_final, messages=messages
    )
    client.delete_messages(chat_id, [message.id for message in messages])  # type: ignore
    client.stop()  # type: ignore
    clear_cache()
    logger.info("Envío de videos completado")


if __name__ == "__main__":
    # --- CONFIGURACIÓN ---
    caption = "Capítulo 9 - Desafío Siglo XXI\n\n"
    video_paths = [
        r"D:\Carpetas Leo\norma\video\Sin título.mp4",
        r"D:\Carpetas Leo\norma\video\Random Videos on the Internet_2.mp4",
    ]
    chat_id = "me"
    thumbnail_path = "thumbnail_watermarked.jpg"

    # ---------------------
    main(
        chat_id=chat_id,
        caption=caption,
        video_paths=video_paths,
        thumbnail_path=thumbnail_path,
    )
