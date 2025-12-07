import logging
import random
import time
from datetime import datetime
from typing import List, Optional

from pyparsing import cast
from pyrogram.types import Message  # type: ignore

from proyect_x.config import MigrationConfig
from proyect_x.services.register import RegistryManager, VideoMeta
from proyect_x.services.telegram.client import TelegramService
from proyect_x.yt_downloader.core.common import sleep_progress

logger = logging.getLogger(__name__)


class ContentMigrator:
    def __init__(
        self,
        config: MigrationConfig,
        registry: RegistryManager,
        telegram_service: TelegramService,
    ):
        self.config = config
        self.registry = registry
        self.tg = telegram_service

        # Texto que aparecerá debajo de la imagen placeholder
        self.obfuscation_caption = (
            "<b>Este contenido ya no esta disponible.</b>\n\n"
            "Únete aquí para verlo: https://t.me/desafiosiglo_xxi"
            "\n\n<b>By Lein</b>"
        )

    def run_migration_batch(self):
        logger.info(
            f"Iniciando migración de ÁLBUMES desde {self.config.source_chat_id}..."
        )
        current_batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.tg.start()

        # Cache para no procesar el mismo grupo varias veces
        processed_media_groups = set()
        count = 0

        try:
            history_generator = self.tg.get_history(
                self.config.source_chat_id, limit=self.config.batch_size
            )
            history_list = list(history_generator)

            for message in reversed(history_list):
                # 1. FILTRO: Solo procesar si es parte de un álbum
                if not message.media_group_id:
                    logger.info(f"Mensaje {message.id} ignorado (no es álbum).")
                    continue

                # 2. CACHÉ: Si ya procesamos este grupo, saltar
                if message.media_group_id in processed_media_groups:
                    logger.info(f"Mensaje {message.id} ignorado (álbum ya procesado).")
                    continue

                if not message.video:
                    logger.info(f"Mensaje {message.id} ignorado (álbum sin video).")
                    continue

                # 3. PROCESAR EL GRUPO ENTERO
                success = self._process_album_batch(message, current_batch_id)

                # Marcar grupo como procesado (éxito o fallo, para no reintentar en este loop)
                processed_media_groups.add(message.media_group_id)

                if success:
                    count += 1
                    time.sleep(3)

            logger.info(f"Lote finalizado. Álbumes migrados: {count}")

        except Exception as e:
            logger.error(f"Error en batch: {e}", exc_info=True)
        finally:
            self.tg.stop()

    def _should_migrate(self, message: Message) -> bool:
        if not message.video:
            return False

        if self.registry.is_message_migrated(message.chat.id, message.id):
            return False

        return True

    def restore_message(self, message_id: int):
        """Método para revertir manualmente un mensaje específico."""
        self.tg.start()
        entry = self.registry.get_migration_entry(
            self.config.source_chat_id, message_id
        )

        if not entry:
            logger.error("No se encontró registro de migración para este mensaje.")
            return

        success = self.tg.restore_video_from_backup(
            source_chat_id=entry["source_chat_id"],
            source_message_id=entry["source_message_id"],
            backup_chat_id=entry["backup_chat_id"],
            backup_message_id=entry["backup_message_id"],
            expected_unique_id=entry["video_meta"]["file_unique_id"],
            caption=entry["original_caption"],
        )

        if success:
            logger.info(f"Mensaje {message_id} restaurado exitosamente.")

    def _process_album_batch(self, trigger_message: Message, batch_id: str) -> bool:
        """
        Maneja la lógica de migrar un álbum completo.
        trigger_message es cualquiera de los mensajes del grupo.
        """
        group_id = trigger_message.media_group_id
        chat_id = trigger_message.chat.id
        logger.info(
            f"Procesando Media Group ID: {group_id} detectado en msg {trigger_message.id}"
        )

        # Obtener todas las partes ORIGINALES del álbum
        # Pyrogram las devuelve ordenadas por ID
        source_messages = self.tg.get_media_group(chat_id, trigger_message.id)
        if not source_messages:
            return False

        # Verificar si ALGUNO de los mensajes ya fue migrado para evitar duplicados parciales
        for msg in source_messages:
            if self.registry.is_message_migrated(chat_id, msg.id):
                logger.warning(
                    f"El grupo {group_id} ya contiene partes migradas. Saltando."
                )
                return False

        # Copiar todo el bloque al Respaldo
        backup_messages = self.tg.copy_media_group(
            target_chat_id=self.config.backup_chat_id,
            from_chat_id=chat_id,
            message_id=trigger_message.id,
        )

        if not backup_messages or len(backup_messages) != len(source_messages):
            logger.error(
                "Error crítico: La cantidad de mensajes copiados no coincide con los originales."
            )
            return False

        # Emparejar (Zip) y Procesar Individualmente
        # Asumimos que el orden se mantiene (Telegram suele garantizar esto por ID incremental)
        # Ordenamos ambas listas por ID para asegurar correspondencia 1:1
        source_messages.sort(key=lambda m: m.id)
        backup_messages.sort(key=lambda m: m.id)

        all_success = True

        for i, (src_msg, bkp_msg) in enumerate(zip(source_messages, backup_messages)):
            # LÓGICA DE CAPTION ÚNICO:
            # Solo el primer elemento (índice 0) lleva el texto de aviso.

            if i == 0:
                caption_to_use = self.obfuscation_caption
            else:
                caption_to_use = ""

            if src_msg.video:

                step_success = self._register_and_obfuscate(
                    src_msg, bkp_msg, batch_id, caption_override=caption_to_use
                )

                if not step_success:
                    all_success = False
            else:
                pass

        return all_success

    def _register_and_obfuscate(
        self, src_msg: Message, bkp_msg: Message, batch_id: str, caption_override: str
    ) -> bool:
        """
        Lógica extraída para manejar el par Source <-> Backup individualmente.
        Igual que antes, pero recibe los objetos ya listos.
        """
        try:
            vid = src_msg.video
            meta: VideoMeta = {
                "file_unique_id": vid.file_unique_id,
                "width": vid.width,
                "height": vid.height,
                "duration": vid.duration,
                "file_name": vid.file_name,
                "file_size": vid.file_size,
            }

            self.registry.register_migration(
                source_chat_id=src_msg.chat.id,
                source_msg_id=src_msg.id,
                backup_chat_id=bkp_msg.chat.id,
                backup_msg_id=bkp_msg.id,
                video_meta=meta,
                original_caption=src_msg.caption,
                media_group_id=src_msg.media_group_id,
                batch_id=batch_id,
            )

            # Ofuscar
            # Al editar un mensaje dentro de un álbum, se mantiene en el álbum visualmente
            # pero el contenido cambia a foto.
            return self.tg.replace_video_with_photo(
                chat_id=src_msg.chat.id,
                message_id=src_msg.id,
                photo_path=self.config.placeholder_image_path,
                caption=caption_override,
            )
        except Exception as e:
            logger.error(f"Error procesando item individual {src_msg.id}: {e}")
            return False

    def restore_album(self, media_group_id: str):
        """
        Restaura un álbum completo usando el ID de grupo.
        """
        logger.info(f"Iniciando restauración del álbum {media_group_id}...")
        self.tg.start()

        entries = self.registry.get_entries_by_media_group(media_group_id)

        if not entries:
            logger.warning(
                f"No se encontraron registros para el álbum {media_group_id}."
            )
            return

        success_count = 0

        for entry in entries:
            if entry["status"] == "restored":
                logger.info(
                    f"Mensaje {entry['source_message_id']} ya estaba restaurado."
                )
                continue

            logger.info(f"Restaurando parte: {entry['source_message_id']}...")

            restored = self.tg.restore_video_from_backup(
                source_chat_id=entry["source_chat_id"],
                source_message_id=entry["source_message_id"],
                backup_chat_id=entry["backup_chat_id"],
                backup_message_id=entry["backup_message_id"],
                expected_unique_id=entry["video_meta"]["file_unique_id"],
                caption=entry["original_caption"],
            )

            if restored:
                self.registry.update_migration_status(
                    entry["source_chat_id"], entry["source_message_id"], "restored"
                )
                success_count += 1
            else:
                logger.error(f"Fallo al restaurar mensaje {entry['source_message_id']}")

        logger.info(
            f"Restauración de álbum completada. {success_count}/{len(entries)} mensajes recuperados."
        )
        self.tg.stop()

    def restore_batch(self, batch_id: str, delete_backup: bool = False):
        """
        Restaura TODOS los mensajes de un lote.
        Args:
            batch_id: El ID del lote.
            delete_backup: Si es True, elimina el mensaje del canal de respaldo tras restaurar.
        """
        entries = self.registry.get_entries_by_batch(batch_id)

        if not entries:
            logger.error(f"No se encontró el lote {batch_id}.")
            return

        logger.info(
            f"Iniciando restauración masiva del lote {batch_id} ({len(entries)} elementos)..."
        )
        self.tg.start()

        restored_count = 0

        for entry in entries:
            if entry["status"] == "restored":
                continue

            logger.info(f"Restaurando msg {entry['source_message_id']}...")

            success = self.tg.restore_video_from_backup(
                source_chat_id=entry["source_chat_id"],
                source_message_id=entry["source_message_id"],
                backup_chat_id=entry["backup_chat_id"],
                backup_message_id=entry["backup_message_id"],
                expected_unique_id=entry["video_meta"]["file_unique_id"],
                caption=entry["original_caption"],
            )

            if success:
                # ACTUALIZAR REGISTRO
                self.registry.update_migration_status(
                    entry["source_chat_id"], entry["source_message_id"], "restored"
                )

                # ELIMINAR RESPALDO (LIMPIEZA OPCIONAL)
                # Solo si la restauración fue exitosa, borramos la copia.
                if delete_backup:
                    del_success = self.tg.delete_messages(
                        entry["backup_chat_id"], entry["backup_message_id"]
                    )
                    if del_success:
                        logger.info(
                            f"Msg {entry['source_message_id']} restaurado y respaldo eliminado."
                        )
                    else:
                        logger.warning(
                            f"Msg {entry['source_message_id']} restaurado, pero falló el borrado del respaldo."
                        )
                else:
                    logger.info(
                        f"Msg {entry['source_message_id']} restaurado. Respaldo conservado."
                    )

                restored_count += 1
                sleep_ = random.randint(1, 4)
                sleep_progress(sleep_)
            else:
                logger.error(
                    f"Falló restauración de {entry['source_message_id']}. El respaldo NO se ha borrado."
                )

        self.tg.stop()
        logger.info(
            f"Restauración de lote completada. {restored_count}/{len(entries)} recuperados."
        )

    def get_media_group_id(self, message_id: str) -> Optional[str]:
        self.tg.start()
        message = cast(
            List[Message],
            self.tg.get_media_group(self.config.source_chat_id, int(message_id)),
        )
        for i in message:
            return i.media_group_id
        return None
