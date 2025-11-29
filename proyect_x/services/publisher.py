import logging
from pathlib import Path
from typing import List, cast

from proyect_x.create_thumbnail_with_watermaker import add_watermark_to_image
from proyect_x.services.register import RegistryManager
from proyect_x.services.telegram.client import TelegramService
from proyect_x.services.telegram.schemas import UploadedVideo
from proyect_x.uploader.settings import AppSettings

logger = logging.getLogger(__name__)


class EpisodePublisher:
    def __init__(self, config: AppSettings, registry: RegistryManager):
        self.config = config
        self.registry = registry
        self.watermark_text = "https://t.me/DESAFIO_SIGLO_XXI"

        # Inicializamos el servicio independiente
        # Nota: La ruta de session debería venir mejor formada desde config
        from os import getenv
        from platform import system

        HOME = (
            Path.home() / ".local/share"
            if system() == "Linux"
            else Path(cast(str, getenv("APPDATA")))
        )
        WORKTABLE = HOME / self.config.project_name

        self.tg_service = TelegramService(
            session_name=self.config.session_name,
            api_id=self.config.api_id,
            api_hash=self.config.api_hash,
            workdir=WORKTABLE,
        )

    def process_episode(self, episode_dled) -> bool:
        """
        Orquesta la marca de agua, el registro y la subida de un episodio.
        Retorna True si el proceso fue exitoso.
        """
        episode_number = episode_dled.episode_number
        videos = episode_dled.video_paths
        thumbnail_path = episode_dled.thumbnail_path

        logger.info(f"Iniciando flujo de publicación para episodio {episode_number}")

        try:
            # 1. Registrar descarga
            self._register_downloads(episode_number, videos)

            # 2. Procesar Miniatura
            watermarked_thumb = Path("thumbnail_watermarked.jpg")
            add_watermark_to_image(
                str(thumbnail_path), self.watermark_text, str(watermarked_thumb)
            )

            # 3. Preparar Videos (Subir o Reutilizar Caché)
            self.tg_service.start()
            uploaded_videos_info = self._prepare_videos_for_album(
                videos, watermarked_thumb
            )

            if not uploaded_videos_info:
                logger.error("No se obtuvieron videos válidos para publicar.")
                return False

            # 4. Enviar Álbum a destinos finales
            caption = self.config.caption.format(episode=episode_number)
            # Agregar info técnica al caption (como tenías antes)
            for vid in uploaded_videos_info:
                size_mb = vid.size_bytes / (1024 * 1024)
                format_name = "HD" if vid.width > 720 else "SD"
                caption += f"{format_name}: {size_mb:.2f} MB\n"

            target_chats = self.tg_service.send_album(
                files=uploaded_videos_info,
                caption=caption,
                dest_chat_ids=self.config.chat_ids,
            )

            if not target_chats:
                logger.warning("No se pudo enviar el álbum a ningún chat de destino.")
                return False

            # 5. Registrar Publicación
            self.registry.register_episode_publication(episode_number)

            user_info = self.tg_service.get_me()
            logger.info(
                f"Publicación del episodio {episode_number} completada por {user_info.username}."
            )
            return True

        except Exception as e:
            logger.error(
                f"Error procesando la publicación del episodio {episode_number}: {e}",
                exc_info=True,
            )
            raise e
        finally:
            self.tg_service.stop()

    def _prepare_videos_for_album(
        self, video_paths: List[Path], thumbnail_path: Path
    ) -> List[UploadedVideo]:
        """
        Itera sobre los videos. Si existen en caché y son válidos en Telegram, obtiene su ID.
        Si no, los sube al chat temporal y guarda su ID.
        """
        final_list: List[UploadedVideo] = []
        total = len(video_paths)

        for index, video_path in enumerate(video_paths, start=1):
            video_path = video_path.resolve()
            cached_entry = None

            # A. Verificar Caché
            if self.registry.was_video_uploaded(video_path):
                logger.info(f"Verificando video registrado: {video_path.name}")
                try:
                    data = self.registry.get_video_uploaded(video_path)
                    # Verificar si el mensaje aún existe en Telegram (chat temporal)
                    msg = self.tg_service.get_message(
                        data["chat_id"], data["message_id"]
                    )

                    if msg and msg.video:
                        logger.info(f"Video reutilizado desde caché (ID {msg.id}).")
                        # Reconstruimos el objeto UploadedVideo desde el mensaje real + datos locales
                        cached_entry = UploadedVideo(
                            file_id=msg.video.file_id,
                            message_id=msg.id,
                            chat_id=msg.chat.id,
                            file_path=video_path,
                            file_name=video_path.name,
                            size_bytes=msg.video.file_size,
                            width=msg.video.width,
                            height=msg.video.height,
                            duration=msg.video.duration,
                        )
                    else:
                        logger.warning(
                            "El mensaje en caché ya no existe o es inválido."
                        )
                except Exception as e:
                    logger.warning(f"Error validando caché: {e}")

                if not cached_entry:
                    logger.info("Entrada de caché inválida. Limpiando registro.")
                    self.registry.remove_video_entry(video_path)

            # B. Si no hay caché válido, subir video
            if cached_entry:
                final_list.append(cached_entry)
            else:
                logger.info(f"Subiendo video {index}/{total} al chat temporal...")
                uploaded_video = self.tg_service.upload_video(
                    video_path=video_path,
                    thumbnail_path=thumbnail_path,
                    target_chat_id=self.config.chat_id_temporary,
                    caption=video_path.name,  # Caption temporal
                )

                # Guardar en registro para la próxima
                self.registry.register_video_uploaded(
                    message_id=uploaded_video.message_id,
                    chat_id=uploaded_video.chat_id,
                    video_path=video_path,
                )
                final_list.append(uploaded_video)

        # Ordenar por tamaño (lógica de tu uploader original) para que quede estético el álbum
        final_list.sort(key=lambda x: x.size_bytes)
        return final_list

    def _register_downloads(self, episode_number: str, videos: List[Path]):
        for video_path in videos:
            self.registry.register_episode_downloaded(episode_number, video_path)
