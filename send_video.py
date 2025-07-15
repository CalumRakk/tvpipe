from pathlib import Path

import cv2
from pyrogram.enums import ParseMode
from pyrogram.types import InputMediaVideo
from tqdm import tqdm  # type: ignore

from get_telegram_client import client

# advertir: La orientacion de una miniatura especificada (horizontal o vertical), debe coincidir con la del video sino, la miniatura se redimensionara de forma incorrecta.


def progress(current, total, progress_bar: tqdm):
    # print("\t", filename, f"{current * 100 / total:.1f}%", end="\r")
    progress_bar.update(current - progress_bar.n)


def get_video_metadata(video_path: str, thumbnail_path=None) -> dict:
    """Devuelve un diccionario con los siguientes campos:
    {
        "width": width,
        "height": height,
        "duration": duration,
        "thumb": str(temp_folder),
        "size_mb": size_mb
    }
    """

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("Error al abrir el video")
        exit()

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = int(total_frames / fps)
    size = Path(video_path).stat().st_size
    size_mb = int(size / (1024 * 1024))

    cap.release()
    return {
        "width": width,
        "height": height,
        "duration": duration,
        "size_mb": size_mb,
        "size": size,
        "path": video_path,
        "format_name": "HD" if width > 720 else "SD",
    }


metadatas = []
for video_path in [
    Path(r"D:\Carpetas Leo\norma\video\Sin título.mp4"),
    Path(r"D:\Carpetas Leo\norma\video\Random Videos on the Internet_2.mp4"),
]:
    metadata = get_video_metadata(str(video_path))
    metadatas.append(metadata)
metadatas.sort(key=lambda x: x["size"])

caption = f"Capítulo 9 - Desafío Siglo XXI\n\n"
for metadata in metadatas:
    caption = caption + f"{metadata['format_name']}: {metadata['size_mb']} MB\n"


media_group = []
messages = []
for index, metadata in enumerate(metadatas):
    total_size = metadata["size"]
    progress_bar = tqdm(
        total=total_size,
        desc="Subiendo archivos",
        unit="B",
        unit_divisor=1024,
        unit_scale=True,
        leave=True,
    )

    video_path = metadata["path"]
    filename = Path(video_path).name
    duration = metadata["duration"]
    width = metadata["width"]
    height = metadata["height"]

    message = client.send_video(
        chat_id="me",
        video=video_path,
        file_name=filename,
        caption=filename,
        progress=progress,
        progress_args=(progress_bar,),
        duration=duration,
        width=width,
        height=height,
        thumb=r"thumbnail_watermarked.jpg",
        disable_notification=True,
    )
    messages.append(message)

for index, message in enumerate(messages):
    file_id = message.video.file_id
    inputmediavideo = InputMediaVideo(
        media=file_id, caption=caption if index == 0 else ""
    )
    media_group.append(inputmediavideo)

print("Moviendo archivos al grupo espeficado")
message = client.send_media_group("me", media_group)

client.delete_messages("me", [message.id for message in messages])  # type: ignore

client.stop()  # type: ignore

print("Listo")
