import logging
from pathlib import Path

from tvpipe.config import AppConfig, get_config
from tvpipe.container import ServiceContainer
from tvpipe.logging_config import setup_logging
from tvpipe.services.register import RegistryManager
from tvpipe.services.telegram import TelegramService
from tvpipe.services.telegram.schemas import UploadedVideo
from tvpipe.utils import (
    ReliabilityGuard,
    should_skip_weekends,
    sleep_progress,
    wait_end_of_day,
)

logger = logging.getLogger("Orchestrator")


def get_or_upload_video(
    video_path: Path,
    thumbnail_path: Path,
    config: AppConfig,
    register: RegistryManager,
    tg_service: TelegramService,
) -> UploadedVideo:
    """
    Intenta recuperar el video del caché (registro + validación en TG).
    Si no existe o no es válido, lo sube y registra el evento.
    """
    if register.was_video_uploaded(video_path):
        data = register.get_video_uploaded(video_path)
        chat_id = data["chat_id"]
        message_id = data["message_id"]

        if tg_service.exists_video_in_chat(chat_id, message_id):
            logger.info(f"Video reutilizado desde caché: {video_path.name}")
            return tg_service.fetch_video_uploaded(chat_id, message_id)
        else:
            logger.warning(
                f"Entrada de caché inválida para {video_path.name}. Limpiando registro."
            )
            register.remove_video_entry(video_path)

    logger.info(f"🚀 Subiendo archivo nuevo: {video_path.name}")
    uploaded_video = tg_service.upload_video(
        video_path=video_path,
        thumbnail_path=thumbnail_path,
        target_chat_id=config.telegram.chat_id_temporary,
        caption=video_path.name,
    )

    register.register_video_uploaded(
        uploaded_video.message_id, uploaded_video.chat_id, video_path
    )

    return uploaded_video


def run_orchestrator():
    setup_logging(f"logs/{Path(__file__).stem}.log")
    config = get_config("config.env")
    services = ServiceContainer(config)
    guard = ReliabilityGuard()

    logger.info(">>> SISTEMA INICIADO: Orquestador en control <<<")
    consecutive_errors = 0
    while consecutive_errors < 15:
        with guard:
            # Si `config.youtube.url` está definido, se trata de un modo manual.
            if not config.youtube.url:
                # Comprobación de fin de semana
                if config.youtube.skip_weekends and should_skip_weekends():
                    logger.info("Es fin de semana. No hay emisión.")
                    wait_end_of_day()
                    continue

                # Comprobacion de Horario
                if services.monitor.should_wait():
                    services.monitor.wait_until_release()
                    continue

                episode_meta = services.downloader.fetch_episode()
                if not episode_meta:
                    logger.info("Video no disponible aún. Reintentando en 2 minutos...")
                    sleep_progress(120)
                    continue
            else:
                episode_meta = services.downloader.fetch_episode()
                if episode_meta is None:
                    raise Exception("No se pudo descargar el episodio.")

            logger.info(f"Procesando episodio: {episode_meta.title}")

            # Descarga de video
            ep_dled = services.downloader.download_episode(episode_meta)
            services.register.register_downloads(
                ep_dled.episode_number, ep_dled.video_paths
            )

            # Descarga de thumbnail
            thumbnail_path = services.downloader.download_thumbnail(episode_meta)
            with services.watermark.temporary_watermarked_image(
                input_path=thumbnail_path, text="https://t.me/DESAFIO_SIGLO_XXI"
            ) as watermarked_thumb:
                ready_to_publish_list = []
                for video_path in ep_dled.video_paths:
                    if services.register.was_video_uploaded(video_path):
                        data = services.register.get_video_uploaded(video_path)
                        chat_id = data["chat_id"]
                        message_id = data["message_id"]
                        if services.tg.exists_video_in_chat(chat_id, message_id):
                            logger.info("Video reutilizado desde caché.")
                            uploaded_video = services.tg.fetch_video_uploaded(
                                chat_id, message_id
                            )
                            ready_to_publish_list.append(uploaded_video)
                            continue
                        else:
                            logger.info(
                                "Entrada de caché inválida. Limpiando registro."
                            )
                            services.register.remove_video_entry(video_path)

                    uploaded_video = services.tg.upload_video(
                        video_path=video_path,
                        thumbnail_path=watermarked_thumb,
                        target_chat_id=config.telegram.chat_id_temporary,
                        caption=video_path.name,
                    )
                    ready_to_publish_list.append(uploaded_video)
                    chat_id = uploaded_video.chat_id
                    message_id = uploaded_video.message_id
                    services.register.register_video_uploaded(
                        message_id, chat_id, video_path
                    )

                succes = services.publisher.publish(
                    ep_dled.episode_number, ready_to_publish_list
                )
                if succes:
                    services.register.register_episode_publication(
                        ep_dled.episode_number
                    )
                    logger.info(f"Episodio {ep_dled.episode_number} publicado.")
                    consecutive_errors = 0
                else:
                    logger.error("No se pudo publicar el episodio.")
                    raise Exception("Fallo en la publicación del álbum")

            if config.youtube.url:
                logger.info("Modo manual finalizado.")
                break

    logger.info("Orchestrator finalizado.")


if __name__ == "__main__":
    run_orchestrator()
