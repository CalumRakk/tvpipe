import logging
from pathlib import Path
from typing import List, Optional, Union, cast

from pyrogram import Client, enums  # type: ignore
from pyrogram.errors import ChatWriteForbidden, PeerIdInvalid  # type: ignore
from pyrogram.types import (  # type: ignore
    Chat,
    ChatMember,
    InputMediaVideo,
    Message,
    User,
)

from .exceptions import AuthenticationError, PermissionDeniedError
from .schemas import UploadedVideo, UploaderSessionInfo
from .utils import get_video_metadata

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, session_name: str, api_id: int, api_hash: str, workdir: Path):
        self.client = Client(
            name=session_name, api_id=api_id, api_hash=api_hash, workdir=str(workdir)
        )
        self._me = None

    def start(self):
        """Inicia el cliente y carga la info del usuario."""
        if not self.client.is_connected:
            try:
                self.client.start()  # type: ignore
                self._me = cast(User, self.client.get_me())
                logger.info(
                    f"Telegram Client iniciado como: {self._me.first_name} (@{self._me.username}) ID: {self._me.id}"
                )
            except Exception as e:
                logger.critical(f"Error al iniciar sesión en Telegram: {e}")
                raise AuthenticationError(f"No se pudo conectar a Telegram: {e}")

    def stop(self):
        """Detiene el cliente."""
        if self.client.is_connected:
            self.client.stop()  # type: ignore
            logger.info("Telegram Client detenido.")

    def get_me(self) -> UploaderSessionInfo:
        """Devuelve la info de la sesión actual."""
        if not self._me:
            self.start()

        user = cast(User, self._me)
        return UploaderSessionInfo(
            id=user.id,
            username=user.username,
            first_name=user.first_name,
            is_bot=user.is_bot,
        )

    def verify_permissions(self, chat_id: Union[int, str]) -> bool:
        """Verifica si el usuario actual tiene permisos de escritura en el chat."""
        if not self.client.is_connected:
            self.start()

        try:
            chat = cast(Chat, self.client.get_chat(chat_id))
            member: ChatMember = self.client.get_chat_member(chat_id, "me")  # type: ignore

            can_write = False
            if chat.type == enums.ChatType.PRIVATE:
                can_write = True
            elif member.status in [
                enums.ChatMemberStatus.OWNER,
                enums.ChatMemberStatus.ADMINISTRATOR,
            ]:
                if member.status == enums.ChatMemberStatus.OWNER:
                    can_write = True
                else:
                    can_write = (
                        member.privileges.can_post_messages
                        if chat.type == enums.ChatType.CHANNEL
                        else True
                    )
            elif member.status == enums.ChatMemberStatus.MEMBER:
                can_write = (
                    chat.permissions.can_send_media_messages
                    if chat.permissions
                    else True
                )

            if not can_write:
                logger.warning(f"Permisos insuficientes en chat {chat_id}")

            return can_write

        except (ChatWriteForbidden, PeerIdInvalid) as e:
            logger.error(f"Acceso denegado o chat inválido {chat_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error verificando permisos en {chat_id}: {e}")
            return False

    def get_message(self, chat_id: int, message_id: int) -> Optional[Message]:
        """Obtiene un mensaje si existe y es accesible."""
        if not self.client.is_connected:
            self.start()
        try:
            msg = self.client.get_messages(chat_id, message_id)
            if not msg or msg.empty:  # type: ignore
                return None
            return cast(Message, msg)
        except Exception:
            return None

    def upload_video(
        self,
        video_path: Path,
        thumbnail_path: Path,
        target_chat_id: Union[int, str],
        caption: str = "",
    ) -> UploadedVideo:
        """Sube un video individual a un chat específico."""
        if not self.client.is_connected:
            self.start()

        meta = get_video_metadata(str(video_path))

        def progress(current, total):
            if total > 0 and (current * 100 // total) % 20 == 0:
                logger.info(f"Subiendo {video_path.name}: {current * 100 / total:.1f}%")

        try:
            msg = cast(
                Message,
                self.client.send_video(
                    chat_id=target_chat_id,
                    video=str(video_path),
                    caption=caption or video_path.name,
                    duration=meta["duration"],
                    width=meta["width"],
                    height=meta["height"],
                    thumb=str(thumbnail_path),
                    progress=progress,
                    disable_notification=True,
                ),
            )

            return UploadedVideo(
                file_id=msg.video.file_id,
                message_id=msg.id,
                chat_id=msg.chat.id,
                file_path=video_path,
                file_name=video_path.name,
                size_bytes=meta["size"],
                width=meta["width"],
                height=meta["height"],
                duration=meta["duration"],
                caption=caption,
            )
        except Exception as e:
            logger.error(f"Fallo subiendo {video_path}: {e}")
            raise e

    def send_album(
        self,
        files: List[UploadedVideo],
        caption: str,
        dest_chat_ids: List[Union[int, str]],
    ) -> List[int]:
        """Envía un grupo de videos (álbum) a una lista de chats."""
        if not self.client.is_connected:
            self.start()

        # Validar permisos primero
        valid_chats = []
        for chat_id in dest_chat_ids:
            if self.verify_permissions(chat_id):
                valid_chats.append(chat_id)

        if not valid_chats:
            raise PermissionDeniedError("No hay chats de destino válidos con permisos.")

        # Construir Media Group
        media_group = []
        for i, vid in enumerate(files):
            # Solo el primer video lleva el caption final
            cap = caption if i == 0 else ""
            media_group.append(InputMediaVideo(media=vid.file_id, caption=cap))

        # Enviar
        successful_chats = []
        for chat_id in valid_chats:
            try:
                logger.info(f"Enviando álbum a {chat_id}")
                self.client.send_media_group(chat_id, media_group)  # type: ignore
                successful_chats.append(chat_id)
            except Exception as e:
                logger.error(f"Error enviando a destino {chat_id}: {e}")

        return cast(List[int], successful_chats)
