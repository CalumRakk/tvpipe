import concurrent.futures
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, cast
from urllib.parse import urlparse

import m3u8
import requests


def download_segment(url, folder: Path) -> Optional[tuple[str, bool]]:
    url_parsed = urlparse(url)
    filename = Path(url_parsed.path).name
    output_path = folder / filename
    if output_path.exists():
        return url, True
    try:
        response = requests.get(url)
        with open(output_path, "wb") as f:
            f.write(response.content)
        return url, True
    except requests.exceptions.RequestException as e:
        print(f"Error descargando {url}: {e}")
        return url, False


VIDEO_ID = "6866aa52c3625256db1d7648"
FILENAME = f"{VIDEO_ID}.ts"
FOLDER = Path("download") / VIDEO_ID

response = requests.get(f"https://mdstrm.com/video/{VIDEO_ID}.m3u8")
master = m3u8.M3U8(response.text)

playlist_url = cast(str, master.playlists[-1].uri)
response = requests.get(playlist_url)
master = m3u8.M3U8(response.text)


urls: list[str] = [cast(str, i.uri) for i in master.segments]
FOLDER.mkdir(parents=True, exist_ok=True)
while len(urls) > 0:

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for url in urls:
            futures.append(executor.submit(download_segment, url=url, folder=FOLDER))

        for future in concurrent.futures.as_completed(futures):
            url, is_ok = future.result()
            if is_ok:
                urls.remove(url)

# concatenar videos
urls: list[str] = [cast(str, i.uri) for i in master.segments]
output = FOLDER / FILENAME
with open(output, "wb") as f:
    for url in urls:
        url_parsed = urlparse(url)
        filename = Path(url_parsed.path).name
        segment_output = FOLDER / filename
        with open(segment_output, "rb") as segment:
            f.write(segment.read())
        segment_output.unlink()

os.system(f"ffmpeg -i \"{output}\" -c copy \"{output.with_suffix('.mp4')}\"")
