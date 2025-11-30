from typing import cast

from proyect_x.config import MigrationConfig, get_config
from proyect_x.logging_config import setup_logging
from proyect_x.services.migrator import ContentMigrator
from proyect_x.services.register import RegistryManager
from proyect_x.services.telegram.client import TelegramService

setup_logging(__file__ + ".log")
config = get_config(r"config.env")
registry = RegistryManager()
tg_service = TelegramService(
    session_name=config.telegram.session_name,
    api_id=config.telegram.api_id,
    api_hash=config.telegram.api_hash,
    workdir=config.telegram.to_telegram_working,
)
config = cast(MigrationConfig, config.migration)
migrator = ContentMigrator(config, registry, tg_service)
# tg_service.force_refresh_peers()

group_media= migrator.get_media_group_id("87")
if group_media:
    migrator.restore_album(group_media)