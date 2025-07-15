import json
from pathlib import Path
from typing import Union, cast

from pydantic import BaseModel
from pyrogram.types import InputMediaVideo, Message
from tqdm import tqdm  # type: ignore

from get_telegram_client import client
from series_manager.utils import get_video_metadata

CACHE_PATH = "meta/upload_cache.json"


class Video(BaseModel):
    path: str
    duration: int
    width: int
    height: int
    size: int
    size_mb: int
    format_name: str


def progress(current, total, progress_bar: tqdm):
    # print("\t", filename, f"{current * 100 / total:.1f}%", end="\r")
    progress_bar.update(current - progress_bar.n)


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
    chat_id: Union[int, str], videos: list[Video], thumbnail_path: str
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

        progress_bar = tqdm(
            total=video.size,
            desc="Subiendo archivos",
            unit="B",
            unit_divisor=1024,
            unit_scale=True,
            leave=True,
        )
        message = cast(
            Message,
            client.send_video(
                chat_id=chat_id,
                video=video.path,
                file_name=video_path.name,
                caption=video_path.name,
                progress=progress,
                progress_args=(progress_bar,),
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
    chat_id: Union[int, str], caption: str, messages: list[Message]
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


def main(
    chat_id: Union[int, str], caption: str, video_paths: list[str], thumbnail_path: str
):
    videos = get_videos(video_paths)

    caption_final = add_subcaption(caption, videos)
    messages = send_videos(chat_id, videos, thumbnail_path)
    resend_videos_as_media_group(chat_id, caption=caption_final, messages=messages)
    client.delete_messages(chat_id, [message.id for message in messages])  # type: ignore
    client.stop()  # type: ignore
    clear_cache()
    print("Listo")


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
