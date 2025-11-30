from typing import cast

from proyect_x.config import MigrationConfig, get_config
from proyect_x.logging_config import setup_logging
from proyect_x.services.migrator import ContentMigrator
from proyect_x.services.register import RegistryManager
from proyect_x.services.telegram.client import TelegramService

# Configuración
setup_logging("restore" + ".log")
config = get_config("config.env")
registry = RegistryManager()
tg_service = TelegramService(
    session_name=config.telegram.session_name,
    api_id=config.telegram.api_id,
    api_hash=config.telegram.api_hash,
    workdir=config.telegram.to_telegram_working,
)
migration = cast(MigrationConfig, config.migration)
migration_service = ContentMigrator(migration, registry, tg_service)
BATCH_ID = "20251130_004938"
migration_service.restore_batch(BATCH_ID, delete_backup=True)
