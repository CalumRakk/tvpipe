import logging
import time

from pyrogram.types import Message  # type: ignore

from proyect_x.config import MigrationConfig
from proyect_x.services.register import RegistryManager, VideoMeta
from proyect_x.services.telegram.client import TelegramService

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
            "<b>Contenido Movido</b>\n\n"
            "Este video ha sido trasladado a nuestro canal de respaldo.\n"
            "Únete aquí para verlo: https://t.me/TU_CANAL"
        )

    def run_migration_batch(self):
        """Ejecuta un lote de migración."""
        logger.info(f"Iniciando migración desde {self.config.source_chat_id}...")
        self.tg.start()

        count = 0
        try:
            history = self.tg.get_history(
                self.config.source_chat_id, limit=self.config.batch_size
            )

            for message in history:
                if self._should_migrate(message):
                    success = self._process_message(message)
                    if success:
                        count += 1
                        # Pequeña pausa para evitar FloodWait
                        time.sleep(2)

            logger.info(f"Lote finalizado. Mensajes migrados: {count}")

        except Exception as e:
            logger.error(f"Error durante el lote de migración: {e}", exc_info=True)
        finally:
            self.tg.stop()

    def _should_migrate(self, message: Message) -> bool:
        # 1. Debe tener video
        if not message.video:
            return False

        # 2. No debe haber sido migrado antes
        if self.registry.is_message_migrated(message.chat.id, message.id):
            return False

        return True

    def _process_message(self, message: Message) -> bool:
        msg_id = message.id
        logger.info(f"Procesando mensaje {msg_id}...")

        # A. Extraer Metadatos (Huella Digital)
        vid = message.video
        meta: VideoMeta = {
            "file_unique_id": vid.file_unique_id,
            "width": vid.width,
            "height": vid.height,
            "duration": vid.duration,
            "file_name": vid.file_name,
            "file_size": vid.file_size,
        }

        # B. Copiar a Respaldo (Backup)
        backup_msg = self.tg.copy_message(
            target_chat_id=self.config.backup_chat_id,
            from_chat_id=message.chat.id,
            message_id=msg_id,
        )

        if not backup_msg:
            logger.error(f"Fallo al copiar mensaje {msg_id}. Abortando.")
            return False

        # C. Registrar puntero (CRÍTICO: Hacer esto antes de borrar/editar)
        self.registry.register_migration(
            source_chat_id=message.chat.id,
            source_msg_id=msg_id,
            backup_chat_id=backup_msg.chat.id,
            backup_msg_id=backup_msg.id,
            video_meta=meta,
            original_caption=message.caption,
        )

        # D. Ofuscar (Reemplazar por imagen)
        replaced = self.tg.replace_video_with_photo(
            chat_id=message.chat.id,
            message_id=msg_id,
            photo_path=self.config.placeholder_image_path,
            caption=self.obfuscation_caption,
        )

        if replaced:
            logger.info(f"Mensaje {msg_id} migrado y ofuscado correctamente.")
            return True
        else:
            logger.error(
                f"Se copió el respaldo {backup_msg.id} pero falló la ofuscación de {msg_id}."
            )
            # TODO: decidir si borrar el respaldo
            return False

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
            # Actualizar estado en registro a "restored" (tarea pendiente en registry)
