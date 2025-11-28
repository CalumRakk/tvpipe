import logging
from os import getenv
from pathlib import Path
from platform import system
from typing import Sequence, Union, cast

from pydantic import BaseModel
from pyrogram import Client  # type: ignore
from pyrogram.types import Chat, InputMediaVideo, Message

from proyect_x.shared.download_register import RegistryManager
from proyect_x.uploader.settings import AppSettings
from proyect_x.uploader.utils import get_video_metadata

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


class TelegramUploader:
    def __init__(self, config: AppSettings, registry: RegistryManager):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.register = registry

    def _progress(self, current, total, step=10):
        percentage = current * 100 / total
        if int(percentage) % step == 0:
            self.logger.info(f"{percentage:.1f}%")

    def _get_videos(self, video_paths: list[str]) -> list[Video]:
        videos: list[Video] = []
        for video_path in video_paths:
            metadata = get_video_metadata(str(video_path))
            metadata["path"] = str(Path(video_path).resolve())
            videos.append(Video(**metadata))
        videos.sort(key=lambda x: x.size)
        return videos

    def _get_client(self) -> Client:
        HOME = (
            Path.home() / ".local/share"
            if system() == "Linux"
            else Path(cast(str, getenv("APPDATA")))
        )
        WORKTABLE = HOME / self.config.project_name

        # Nota: pyrogram gestiona la sesión automáticamente
        return Client(
            self.config.session_name,
            api_id=self.config.api_id,
            api_hash=self.config.api_hash,
            workdir=str(WORKTABLE),
        )

    def _process_single_video(
        self,
        client: Client,
        chat_id,
        video: Video,
        thumbnail_path: Union[str, Path],
        index: int,
        total: int,
    ):
        video_path = Path(video.path)

        if self.register.was_video_uploaded(video_path):
            self.logger.info(
                f"El video {video_path.name} ya fue registrado. Verificando si ya fue enviado."
            )
            data = self.register.get_video_uploaded(video_path)
            try:
                message = cast(
                    Message, client.get_messages(data["chat_id"], data["message_id"])
                )
                if not message.empty:
                    self.logger.info(f"Video reutilizado (ID {message.id}).")
                    return message
            except Exception:
                pass  # Si falla al obtener mensaje, lo reenviamos

            self.logger.info(
                f"El video {video_path.name} no se encuentra o no es accesible. Se reenviará."
            )

        self.logger.info(
            f"Enviando video {index}/{total}: {video_path.name} ({video.size_mb:.2f} MB)"
        )

        try:
            message = cast(
                Message,
                client.send_video(
                    chat_id=chat_id,
                    video=video.path,
                    file_name=video_path.name,
                    caption=video_path.name,
                    progress=self._progress,
                    duration=video.duration,
                    width=video.width,
                    height=video.height,
                    thumb=str(thumbnail_path),
                    disable_notification=True,
                ),
            )
            self.register.register_video_uploaded(
                message_id=message.id,
                chat_id=chat_id,
                video_path=video.path,
            )
            self.logger.info(f"Video enviado: {message.video.file_id}")
            return message
        except Exception as e:
            self.logger.error(f"Error al enviar el video {video_path.name}: {e}")
            return None

    def _send_videos_to_chat_temp(
        self, client: Client, chat_id, videos, thumbnail_path: Union[str, Path]
    ) -> list[Message]:
        if not videos:
            self.logger.error("No se han proporcionado videos para enviar.")
            return []

        try:
            chat_info = cast(Chat, client.get_chat(chat_id))
            self.logger.info(
                f"Enviando {len(videos)} videos al chat temporal ({chat_info.title or chat_id})"
            )
        except Exception as e:
            self.logger.error(f"No se pudo obtener información del chat {chat_id}: {e}")
            return []

        messages = []
        for index, video in enumerate(videos, start=1):
            message = self._process_single_video(
                client, chat_id, video, thumbnail_path, index, len(videos)
            )
            if message:
                messages.append(message)

        return messages

    def _instance_messages_to_media_group(
        self, messages: list[Message], caption: str
    ) -> list[InputMediaVideo]:
        media_group = []
        for index, message in enumerate(messages):
            if not message.video:
                continue
            inputmediavideo = InputMediaVideo(
                media=message.video.file_id, caption=caption if index == 0 else ""
            )
            media_group.append(inputmediavideo)

        if len(media_group) < 2 and media_group:
            self.logger.warning(
                "Menos de 2 videos para media group. Se enviarán pero Telegram podría tratarlos individualmente."
            )

        return media_group

    def _resend_videos_as_media_group(
        self, client: Client, chat_ids: Sequence[Union[int, str]], media_group
    ):
        for chat_id in chat_ids:
            try:
                self.logger.info(f"Reenviando grupo de medios a {chat_id}")
                client.send_media_group(chat_id, media_group)  # type: ignore
                self.logger.debug(f"Envío exitoso a {chat_id}")
            except Exception as e:
                self.logger.exception(f"Error al reenviar a {chat_id}: {e}")

    def send_media_group(
        self,
        video_paths: Sequence[Union[str, Path]],
        thumbnail_path: Union[str, Path],
        episode_number: str,
    ):
        """Método público principal para realizar el flujo de subida."""
        self.logger.info(f"Iniciando el envío de videos a Telegram")

        if not video_paths:
            self.logger.error("No se han proporcionado rutas de videos.")
            return

        video_paths_str = [str(path) for path in video_paths]
        thumb_str = str(thumbnail_path)

        # Preparar caption
        caption = self.config.caption.format(episode=episode_number)
        videos = self._get_videos(video_paths_str)
        for video in videos:
            caption += f"{video.format_name}: {video.size_mb} MB\n"

        # Iniciar cliente
        app = self._get_client()

        try:
            app.start()  # type: ignore

            # 1. Subir a chat temporal
            messages = self._send_videos_to_chat_temp(
                app, self.config.chat_id_temporary, videos, thumb_str
            )

            if not messages:
                self.logger.error("No se pudieron subir los videos al chat temporal.")
                return

            # 2. Crear Media Group
            media_group = self._instance_messages_to_media_group(messages, caption)

            if media_group:
                # 3. Reenviar a destinos finales
                self._resend_videos_as_media_group(
                    app, self.config.chat_ids, media_group
                )

            # 4. Limpieza (opcional, borra del chat 'Saved Messages' o temporal)
            try:
                app.delete_messages(
                    self.config.chat_id_temporary, [m.id for m in messages]
                )  # type: ignore
            except Exception as e:
                self.logger.warning(
                    f"No se pudieron borrar los mensajes temporales: {e}"
                )

        except Exception as e:
            self.logger.critical(
                f"Fallo crítico en el proceso de subida: {e}", exc_info=True
            )
        finally:
            app.stop()  # type: ignore
            self.logger.info("Cliente de Telegram detenido.")
