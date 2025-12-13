import logging
from pathlib import Path

from tvpipe.config import get_config
from tvpipe.container import ServiceContainer
from tvpipe.logging_config import setup_logging
from tvpipe.utils import (
    ReliabilityGuard,
)

logger = logging.getLogger("Orchestrator")


def run_orchestrator():
    setup_logging(f"logs/{Path(__file__).stem}.log")
    config = get_config("config.env")
    services = ServiceContainer(config)
    guard = ReliabilityGuard()

    logger.info(">>> SISTEMA INICIADO: Orquestador en control <<<")
    consecutive_errors = 0
    while consecutive_errors < 15:
        with guard:

            episode_meta = services.monitor.wait_for_next_episode()

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
                    uploaded = services.publisher.prepare_video(
                        video_path=video_path, thumbnail_path=watermarked_thumb
                    )
                    ready_to_publish_list.append(uploaded)

                succes = services.publisher.publish(
                    ep_dled.episode_number, ready_to_publish_list
                )
                if succes:
                    logger.info(f"Episodio {ep_dled.episode_number} publicado.")
                    consecutive_errors = 0
                else:
                    raise Exception("Fallo en la publicación del álbum")

            if config.youtube.url:
                logger.info("Modo manual finalizado.")
                break

    logger.info("Orchestrator finalizado.")


if __name__ == "__main__":
    run_orchestrator()
