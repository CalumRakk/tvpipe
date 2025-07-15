import logging
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from logging_config import setup_logging
from utils.caracolstream import CaracolLiveStream

setup_logging("capture_stream.log")

logger = logging.getLogger(__name__)
caracol = CaracolLiveStream()
FOLDER = Path("download")
while True:
    playlist = caracol.fetch_best_playlist()
    urls = [i.uri for i in playlist.segments]

    for url in urls:
        parsed = urlparse(url)
        filename = Path(parsed.path).name  # type: ignore

        output = FOLDER / filename
        if output.exists():
            logger.info("Skipping " + filename)
            continue

        logger.info("Downloading " + filename)
        response = requests.get(url)
        response.raise_for_status()
        output.write_bytes(response.content)

    time.sleep(20)
