import json
import logging
from os import getenv
from pathlib import Path
from platform import system
from typing import List, Optional, Sequence, Union, cast

from pydantic import BaseModel
from pyrogram import Client  # type: ignore
from pyrogram.errors.exceptions import BadRequest
from pyrogram.types import Chat, InputMediaVideo, Message
from tqdm import tqdm  # type: ignore

from proyect_x.upload.settings import AppSettings
from proyect_x.upload.utils import get_video_metadata

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
    if int(percentage) % step == 0:
        logger.info(f"{percentage:.1f}%")


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
        metadata = get_video_metadata(str(video_path))
        metadata["path"] = str(Path(video_path).resolve())
        videos.append(Video(**metadata))

    videos.sort(key=lambda x: x.size)
    return videos


def send_videos_to_chat_temp(
    client, chat_id, videos, thumbnail_path: Union[str, Path]
) -> list[Message]:
    """Sube los videos a Telegram y devuelve una lista de mensajes."""
    # TODO: La orientacion de una miniatura especificada (horizontal o vertical), debe coincidir con la del video sino, la miniatura se redimensionara de forma incorrecta.
    if len(videos) == 0:
        logger.error("No se han proporcionado videos para enviar.")
        return []

    try:
        chat_info = cast(Chat, client.get_chat(chat_id))
        username = chat_info.username or chat_info.id
        logger.info(f"Informacion del chat_id : {username} ({chat_id})")
    except BadRequest as e:
        logger.error(f"Error al obtener información del chat {chat_id}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error inesperado al obtener información del chat {chat_id}: {e}")
        return []

    logger.info(
        f"Enviando {len(videos)} videos al chat ({chat_id}), con la miniatura {thumbnail_path}"
    )
    messages = []
    for index, video in enumerate(videos, start=1):
        video_path = Path(video.path)
        # video_inodo = f"{video_path.stat().st_dev}-{video_path.stat().st_ino}"
        logger.info(
            f"Enviando video {index}/{len(videos)}: {video_path.name} ({video.size_mb:.2f} MB)"
        )
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
        messages.append(message)
        logger.info(f"Video enviado: {message.video.file_id}")

    logger.info(f"Total de videos enviados: {len(messages)}")
    return messages


def instance_messages_to_media_group(
    messages: list[Message], caption
) -> list[InputMediaVideo]:
    """Instancia los mensajes de video a un grupo de medios."""
    media_group = []
    for index, message in enumerate(messages, start=0):
        if not message.video:
            logger.warning(
                f"El mensaje (chat_id={message.chat.id}, message_id={message.id}) no contiene un video. Se omitirá."
            )
            continue
        file_id = message.video.file_id
        logger.debug(
            f"Agregando video (chat_id={message.chat.username}, message_id={message.id}) a media group: file_id={file_id}"
        )
        inputmediavideo = InputMediaVideo(
            media=file_id, caption=caption if index == 0 else ""
        )
        media_group.append(inputmediavideo)

    if not media_group:
        logger.error("No se pudo construir el grupo de medios: no hay videos válidos.")
        return []
    elif len(media_group) < 2:
        logger.warning(
            "Se está intentando enviar un grupo de medios con menos de 2 videos. Se esperará a que haya más videos."
        )
        return []

    logger.info(f"Grupo de medios creado con {len(media_group)} videos.")
    return media_group


def reensend_media_group(
    client: Client,
    chat_ids: Sequence[Union[int, str]],
    media_group: List[InputMediaVideo],
):
    """Reenvía un grupo de medios a un chats específicos."""

    logger.debug(f"Lista final de destinos: {chat_ids}")
    sent_messages = []
    for chat_id in chat_ids:
        try:
            logger.info(f"Reenviando grupo de medios a {chat_id}")
            messages = cast(
                list[Message], client.send_media_group(chat_id, media_group)  # type: ignore
            )
            sent_messages.extend(cast(list[Message], messages))
            logger.debug(f"Envío exitoso a {chat_id}")
        except Exception as e:
            logger.exception(f"Error al reenviar a {chat_id}: {e}")

    logger.info(f"Reenvío completado. Total de mensajes enviados: {len(sent_messages)}")


def resend_videos_as_media_group(
    client: Client, chat_ids: Sequence[Union[int, str]], media_group
) -> list[Message]:
    """Reenvia los videos como un grupo de medios, con un caption personalizado."""

    sent_messages = []
    for chat_id in chat_ids:
        try:
            logger.info(f"Reenviando grupo de medios a {chat_id}")
            result = cast(list[Message], client.send_media_group(chat_id, media_group))
            sent_messages.extend(cast(list[Message], result))
            logger.debug(f"Envío exitoso a {chat_id}")
        except Exception as e:
            logger.exception(f"Error al reenviar a {chat_id}: {e}")

    logger.info(f"Reenvío completado. Total de mensajes enviados: {len(sent_messages)}")
    return sent_messages


def add_subcaption(caption: str, videos: list[Video]) -> str:
    caption = caption
    for video in videos:
        caption = caption + f"{video.format_name}: {video.size_mb} MB\n"
    return caption


def get_client_started(config: AppSettings) -> Client:
    # Nota: Se usa una session que contiene pers guardados y permiten interactuar con varios chats de la cuenta.
    # FIXME: Corregir, el script está acoplado a esta sesión (session_name). En caso que no exista la session se debe crear manualmente.
    HOME = (
        Path.home() / ".local/share"
        if system() == "Linux"
        else Path(cast(str, getenv("APPDATA")))
    )
    WORKTABLE = HOME / config.project_name

    client = Client(
        config.session_name,
        api_id=config.api_id,
        api_hash=config.api_hash,
        workdir=str(WORKTABLE),
    )
    client.start()  # type: ignore
    return client


def send_videos_as_media_group(
    video_paths: Sequence[Union[str, Path]],
    thumbnail_path: Union[str, Path],
    episode_number,
    config: AppSettings,
):
    logger.info(f"Iniciando el envío de videos a Telegram")
    if len(video_paths) == 0:
        logger.error("No se han proporcionado rutas de videos.")
        return
    video_paths = [str(path) for path in video_paths]
    thumbnail_path = (
        str(thumbnail_path) if isinstance(thumbnail_path, Path) else thumbnail_path
    )
    chat_ids = config.chat_ids
    chat_temp = config.chat_id_temporary
    caption = config.caption.format(episode=episode_number)
    # Obtiene metadatos de videos para completar el caption del media_group
    videos = get_videos([str(i) for i in video_paths])
    caption_final = add_subcaption(caption, videos)

    client = get_client_started(config)
    messages = send_videos_to_chat_temp(client, chat_temp, videos, thumbnail_path)
    media_group = instance_messages_to_media_group(messages, caption_final)

    resend_videos_as_media_group(client, chat_ids, media_group)

    client.delete_messages(chat_id, [message.id for message in messages])  # type: ignore
    client.stop()  # type: ignore
    clear_cache()
    logger.info("Envío de videos completado")
