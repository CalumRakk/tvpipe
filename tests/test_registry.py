import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.getcwd())
from tvpipe.services.register import RegistryManager, VideoMeta


class TestRegistryManager(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.test_dir.name)

        self.fake_reg_file = self.temp_path / "download_registry.json"
        self.fake_mig_file = self.temp_path / "migration_registry.json"

        self.manager = RegistryManager(registry_file=self.fake_reg_file)

        self.migration_patcher = patch(
            "tvpipe.services.register.MIGRATION_REGISTRY_FILE", self.fake_mig_file
        )
        self.migration_patcher.start()

    def tearDown(self):
        self.migration_patcher.stop()
        self.test_dir.cleanup()

    def test_register_and_check_download(self):
        """Verifica que se guarda un episodio descargado y se reconoce después."""
        ep_num = "99"
        path = self.temp_path / "video.mp4"

        self.assertFalse(self.manager.was_episode_downloaded(ep_num))

        self.manager.register_episode_downloaded(ep_num, path)

        self.assertTrue(self.fake_reg_file.exists(), "El archivo JSON debe crearse")
        self.assertTrue(self.manager.was_episode_downloaded(ep_num))

        with open(self.fake_reg_file, "r") as f:
            data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["event"], "download")
            self.assertEqual(data[0]["episode"], ep_num)

    def test_register_publication(self):
        """Verifica el flujo de publicación."""
        ep_num = "50"
        self.assertFalse(self.manager.was_episode_published(ep_num))

        self.manager.register_episode_publication(ep_num)

        self.assertTrue(self.manager.was_episode_published(ep_num))

    @patch.object(RegistryManager, "_get_inodo")
    def test_video_upload_cache_logic(self, mock_inode):
        """
        Verifica que el sistema de caché por inodos funciona.
        Si el archivo cambia de nombre pero es el mismo inodo, debe detectarlo.
        """
        # Simulamos que el inodo es "12345" siempre para este test
        mock_inode.return_value = "dev-12345"

        video_path = self.temp_path / "capitulo_final.mp4"
        # Creamos archivo dummy para que resolve() funcione
        video_path.touch()

        msg_id = 1001
        chat_id = -500
        self.manager.register_video_uploaded(msg_id, chat_id, video_path)

        self.assertTrue(self.manager.was_video_uploaded(video_path))

        data = self.manager.get_video_uploaded(video_path)
        self.assertEqual(data["message_id"], msg_id)
        self.assertEqual(data["inodo"], "dev-12345")

        self.manager.remove_video_entry(video_path)
        self.assertFalse(self.manager.was_video_uploaded(video_path))

    def test_migration_lifecycle(self):
        """Prueba el ciclo completo: Migrar -> Verificar -> Actualizar Estado."""
        src_chat, src_msg = -100, 50
        bkp_chat, bkp_msg = -200, 60
        batch_id = "lote_1"

        video_meta = VideoMeta(
            **{
                "file_unique_id": "uid_123",
                "width": 1920,
                "height": 1080,
                "duration": 60,
                "file_name": "vid.mp4",
                "file_size": 1024,
            }
        )

        self.manager.register_migration(
            src_chat,
            src_msg,
            bkp_chat,
            bkp_msg,
            video_meta,
            "caption",
            "group_1",
            batch_id,
        )

        self.assertTrue(self.manager.is_message_migrated(src_chat, src_msg))

        entry = self.manager.get_migration_entry(src_chat, src_msg)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["status"], "migrated")  # type: ignore

        # Verificar búsqueda por batch
        batch_entries = self.manager.get_entries_by_batch(batch_id)
        self.assertEqual(len(batch_entries), 1)

        # Actualizar estado (simulando restauración)
        self.manager.update_migration_status(src_chat, src_msg, "restored")

        # Volvemos a leer para asegurar persistencia
        updated_entry = self.manager.get_migration_entry(src_chat, src_msg)
        self.assertEqual(updated_entry["status"], "restored")  # type: ignore

    def test_corrupt_json_handling(self):
        """
        Si el JSON está corrupto (ej: corte de luz a mitad de escritura),
        la clase no debería explotar, sino iniciar una lista vacía (o manejarlo).
        """

        with open(self.fake_reg_file, "w") as f:
            f.write("{ esto no es un json valido ...")

        try:
            result = self.manager.was_episode_downloaded("1")
            self.assertFalse(result)
        except Exception as e:
            self.fail(f"RegistryManager falló con JSON corrupto: {e}")

        self.manager.register_episode_downloaded("1", "path")
        self.assertTrue(self.manager.was_episode_downloaded("1"))


if __name__ == "__main__":
    unittest.main()
