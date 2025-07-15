from pathlib import Path
from typing import Union, cast

from pydantic import BaseModel
from pyrogram.types import InputMediaVideo, Message

# advertir: La orientacion de una miniatura especificada (horizontal o vertical), debe coincidir con la del video sino, la miniatura se redimensionara de forma incorrecta.
from tqdm import tqdm  # type: ignore

from get_telegram_client import client
from series_manager.utils import get_video_metadata


def progress(current, total, progress_bar: tqdm):
    # print("\t", filename, f"{current * 100 / total:.1f}%", end="\r")
    progress_bar.update(current - progress_bar.n)


class Video(BaseModel):
    path: str
    duration: int
    width: int
    height: int
    size: int
    size_mb: int
    format_name: str


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
    messages = []
    for video in videos:
        progress_bar = tqdm(
            total=video.size,
            desc="Subiendo archivos",
            unit="B",
            unit_divisor=1024,
            unit_scale=True,
            leave=True,
        )
        filename = Path(video.path).name
        message = client.send_video(
            chat_id=chat_id,
            video=video.path,
            file_name=filename,
            caption=filename,
            progress=progress,
            progress_args=(progress_bar,),
            duration=video.duration,
            width=video.width,
            height=video.height,
            thumb=thumbnail_path,
            disable_notification=True,
        )
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
