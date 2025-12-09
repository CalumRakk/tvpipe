import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(os.getcwd())
from tvpipe.config import DownloaderConfig
from tvpipe.interfaces import EpisodeParser
from tvpipe.services.register import RegistryManager
from tvpipe.services.youtube.client import YtDlpClient
from tvpipe.services.youtube.models import Stream, StreamPair, VideoMetadata
from tvpipe.services.youtube.service import YouTubeFetcher


class TestYouTubeFetcher(unittest.TestCase):

    def setUp(self):
        self.mock_config = MagicMock(spec=DownloaderConfig)
        self.mock_config.channel_url = "https://youtube.com/channel"
        self.mock_config.qualities = ["1080p"]
        self.mock_config.output_as_mp4 = True
        self.mock_config.download_folder = Path("/tmp/downloads")

        self.mock_config.generate_filename.return_value = "video.mp4"

        # 2. Mock del Registro
        self.mock_registry = MagicMock(spec=RegistryManager)

        # 3. Mock del Parser
        self.mock_parser = MagicMock(spec=EpisodeParser)

        # 4. Mock del Cliente YtDlp
        self.mock_client = MagicMock(spec=YtDlpClient)

        # clase a probar
        self.fetcher = YouTubeFetcher(
            config=self.mock_config,
            registry=self.mock_registry,
            episode_parser=self.mock_parser,
            client=self.mock_client,
        )

    def _create_dummy_metadata(self, title="Capitulo 50", days_offset=0):
        """Helper para crear metadatos válidos de Pydantic"""
        timestamp = datetime.now().timestamp() - (days_offset * 86400)

        stream_mock = Stream(format_id="1", ext="mp4", height=1080)

        return VideoMetadata(
            id="video123",
            title=title,
            thumbnail_url="http://thumb.jpg",
            duration=3600,
            streams=[stream_mock],
            timestamp=int(timestamp),
            was_live=False,
            url="https://youtu.be/video123",
        )

    @patch("tvpipe.services.youtube.service.download_thumbnail")
    def test_automatic_download_success(self, mock_dl_thumb):
        """
        Escenario:
        - Hay un video nuevo en el canal.
        - Es de HOY.
        - Coincide con el regex del parser.
        - No ha sido publicado antes.

        Result: Debe descargarse.
        """

        self.mock_client.get_latest_channel_entries.return_value = [
            {"title": "Desafio Cap 50", "url": "url_video"}
        ]
        self.mock_parser.matches_criteria.return_value = True
        self.mock_parser.extract_number.return_value = "50"

        # Simulamos que el video es de hoy
        meta = self._create_dummy_metadata("Desafio Cap 50", days_offset=0)
        self.mock_client.get_metadata.return_value = meta

        self.mock_registry.was_episode_published.return_value = False

        # Simulamos la selección de stream
        dummy_stream = StreamPair(
            video=Stream(format_id="v", ext="mp4", height=1080),
            audio=Stream(format_id="a", ext="m4a"),
        )
        self.mock_client.select_best_pair.return_value = dummy_stream

        result = self.fetcher.fetch_and_download()

        self.assertIsNotNone(result)
        self.assertEqual(result.episode_number, "50")  # type: ignore

        self.mock_client.get_latest_channel_entries.assert_called_once()
        self.mock_registry.was_episode_published.assert_called_with("50")
        self.mock_client.download_stream.assert_called_once()

    def test_skip_if_already_published(self):
        """
        Escenario: El video es válido y de hoy, pero el registro dice que ya se publicó.
        Result: Retorna None y no descarga.
        """
        self.mock_client.get_latest_channel_entries.return_value = [
            {"title": "Desafio Cap 50", "url": "url_video"}
        ]
        self.mock_parser.matches_criteria.return_value = True
        self.mock_parser.extract_number.return_value = "50"

        meta = self._create_dummy_metadata(days_offset=0)
        self.mock_client.get_metadata.return_value = meta

        self.mock_registry.was_episode_published.return_value = True

        result = self.fetcher.fetch_and_download()

        self.assertIsNone(result)
        self.mock_client.download_stream.assert_not_called()

    def test_skip_old_videos(self):
        """
        Escenario: Encuentra un video que coincide con el título, pero es de AYER.
        Result: Lo ignora y sigue buscando (o termina).
        """
        self.mock_client.get_latest_channel_entries.return_value = [
            {"title": "Desafio Cap 49", "url": "url_old"}
        ]
        self.mock_parser.matches_criteria.return_value = True

        # Es de ayer (offset=1 día)
        meta = self._create_dummy_metadata(days_offset=1)
        self.mock_client.get_metadata.return_value = meta

        result = self.fetcher.fetch_and_download()

        self.assertIsNone(result)

        # Nunca debió llegar a preguntar al registro ni a descargar
        self.mock_registry.was_episode_published.assert_not_called()
        self.mock_client.download_stream.assert_not_called()

    @patch("tvpipe.services.youtube.service.download_thumbnail")
    def test_manual_mode(self, mock_dl_thumb):
        """
        Escenario: Se provee una URL manual.
        Result: Salta la búsqueda en el canal y descarga directo.
        """
        manual_url = "https://youtube.com/manual"

        self.mock_parser.extract_number.return_value = "99"
        meta = self._create_dummy_metadata("Manual Cap 99")
        self.mock_client.get_metadata.return_value = meta
        self.mock_registry.was_episode_published.return_value = False

        dummy_stream = StreamPair(
            video=Stream(format_id="v", ext="mp4", height=720),
            audio=Stream(format_id="a", ext="m4a"),
        )
        self.mock_client.select_best_pair.return_value = dummy_stream

        result = self.fetcher.fetch_and_download(manual_url=manual_url)

        self.assertIsNotNone(result)
        self.assertEqual(result.episode_number, "99")  # type: ignore

        # No debió buscar en el canal
        self.mock_client.get_latest_channel_entries.assert_not_called()
        # Debió pedir metadatos de la URL manual
        self.mock_client.get_metadata.assert_called_with(manual_url)


if __name__ == "__main__":
    unittest.main()
