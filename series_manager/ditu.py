# _live_dash_downloader.py

import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Set, TypedDict

import requests
from pydantic import BaseModel

# ============================
# CONFIGURACIÓN

OUTPUT_DIR_VIDEO = "output_dash/video"
OUTPUT_DIR_AUDIO = "output_dash/audio"
REPRESENTATION_ID_VIDEO = "3"
REPRESENTATION_ID_AUDIO = "4"

# ============================

logger = logging.getLogger(__name__)
MPD_URL = "https://d1kkcfjl98zuzm.cloudfront.net/v1/dash/f4489bb8f722c0b62ee6ef7424a5804a17ae814a/El-Desafio/out/v1/ab964e48d2c041579637cfe179ff2359/index.mpd"
PARAMS: Dict[str, str] = {
    "ads.deviceType": "mobile",
    "ads.rdid": "05166e3c-d22e-4386-9d0a-6aadf1d5c62f",
    "ads.is_lat": "0",
    "ads.idtype": "adid",
    "ads.vpa": "auto",
}
HEADERS: Dict[str, str] = {
    "Host": "d1kkcfjl98zuzm.cloudfront.net",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "okhttp/4.12.0",
}


class Schedule(BaseModel):
    start_time: datetime
    end_time: datetime
    title: str
    start_time_12hours: str
    end_time_12hours: str
    content_id: int
    long_description: str
    episode_title: str
    episode_number: int
    season: int
    duration: int
    episode_id: int


class Ditu:

    def _fetch_all_schedules(self, url, headers, params):
        url = "https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/TRAY/EPG"
        params = {
            "orderBy": "orderId",
            "sortOrder": "asc",
            "filter_startTime": "1752978600000",
            "filter_endTime": "1753000200000",
        }
        headers = {
            "User-Agent": "okhttp/4.12.0",
            "Accept-Encoding": "gzip, deflate, br",
        }

        response = requests.get(url, headers=headers, params=params)
        return response.json()

    def _extract_data_ditu(self):
        for data in self._fetch_all_schedules(MPD_URL, HEADERS, PARAMS)["resultObj"][
            "containers"
        ]:
            if data["id"] == "43":  # channelId= Desafio siglo xxi
                return data

    def get_schedule(self):
        schedules = []
        contents = self._extract_data_ditu()
        if contents is None:
            raise Exception("No se pudo obtener la programación")

        for data in [i["metadata"] for i in contents["containers"]]:
            start_time = datetime.fromtimestamp(data["airingStartTime"] / 1000)
            end_time = datetime.fromtimestamp(data["airingEndTime"] / 1000)
            title = data["title"].strip()
            start_time_12hours = start_time.strftime("%Y-%m-%d %I:%M %p")
            end_time_12hours = end_time.strftime("%Y-%m-%d %I:%M %p")
            content_id = data["contentId"]
            long_description = data["longDescription"].strip()
            episode_title = data["episodeTitle"].strip()
            episode_number = data["episodeNumber"]
            season = data["season"]
            duration = data["duration"]
            episode_id = data["episodeId"]

            schedules.append(
                Schedule(
                    start_time=start_time,
                    end_time=end_time,
                    title=title,
                    start_time_12hours=start_time_12hours,
                    end_time_12hours=end_time_12hours,
                    content_id=content_id,
                    long_description=long_description,
                    episode_title=episode_title,
                    episode_number=episode_number,
                    season=season,
                    duration=duration,
                    episode_id=episode_id,
                )
            )
        return schedules


class MPDInfo(TypedDict):
    """Estructura de datos para la información de una Representation del MPD."""

    base_url: str
    init_url: str
    media_pattern: str
    start_number: int
    segments: List[ET.Element]


def download_mpd(url: str, headers: Dict[str, str], params: Dict[str, str]) -> str:
    """
    Descarga el archivo de manifiesto MPD.

    Args:
        url: La URL del manifiesto MPD.
        headers: Las cabeceras HTTP para la petición.
        params: Los parámetros de la query string para la petición.

    Returns:
        El contenido del MPD como una cadena de texto.
    """
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.text


def parse_mpd_representation(xml_text: str, representation_id: str) -> MPDInfo:
    """
    Parsea el texto del MPD y extrae la información para un Representation ID específico.

    Args:
        xml_text: El contenido del MPD como una cadena de texto.
        representation_id: El ID de la representación (video o audio) a buscar.

    Returns:
        Un diccionario MPDInfo con los datos de la representación.

    Raises:
        Exception: Si no se encuentra la representación con el ID especificado.
    """
    ns = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}
    root = ET.fromstring(xml_text)

    base_url_element = root.find("mpd:BaseURL", ns)
    base_url = base_url_element.text if base_url_element is not None else ""

    for aset in root.findall(".//mpd:AdaptationSet", ns):
        for rep in aset.findall("mpd:Representation", ns):
            if rep.attrib.get("id") == representation_id:
                template = rep.find("mpd:SegmentTemplate", ns)
                timeline = template.find("mpd:SegmentTimeline", ns)  # type: ignore

                # Construcción de las URLs completas
                init_url = base_url + template.attrib["initialization"]  # type: ignore
                media_pattern = base_url + template.attrib["media"]  # type: ignore

                segments: List[ET.Element] = []
                for s in timeline.findall("mpd:S", ns):  # type: ignore
                    # El atributo 'r' (repeat) indica cuántas veces más se repite el segmento.
                    # r=0 significa 1 segmento, r=1 significa 2 segmentos, etc.
                    repeat_count = int(s.attrib.get("r", 0))
                    segments.extend([s] * (repeat_count + 1))

                return MPDInfo(
                    base_url=base_url,  # type: ignore
                    init_url=init_url,
                    media_pattern=media_pattern,
                    start_number=int(template.attrib["startNumber"]),  # type: ignore
                    segments=segments,
                )

    raise Exception(f"No se encontró Representation ID {representation_id}")


def download_file(url: str, output_path: str, headers: Dict[str, str]) -> None:
    """
    Descarga un archivo desde una URL a una ruta de destino.

    Args:
        url: La URL del archivo a descargar.
        output_path: La ruta donde se guardará el archivo.
        headers: Las cabeceras HTTP para la petición.
    """
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(r.content)
    logger.info(f"✅ Descargado: {output_path}")


class RepresentationDownloader:
    """Gestiona la descarga de todos los segmentos para una única Representation."""

    def __init__(
        self, representation_id: str, output_dir: str, headers: Dict[str, str]
    ):
        self.representation_id = representation_id
        self.output_dir = output_dir
        self.headers = headers
        self.downloaded_segment_numbers: Set[int] = set()
        self.initial_segment_downloaded = False

    def process_segments_from_mpd(self, mpd_text: str) -> None:
        """
        Parsea el MPD y descarga los segmentos nuevos para esta representación.

        Args:
            mpd_text: El contenido del MPD como una cadena de texto.
        """
        try:
            mpd_info = parse_mpd_representation(mpd_text, self.representation_id)
        except Exception as e:
            logger.info(
                f"⚠️ No se pudo procesar la representación {self.representation_id}: {e}"
            )
            return

        # Descargar el segmento de inicialización si aún no se ha hecho
        if not self.initial_segment_downloaded:
            init_path = os.path.join(self.output_dir, "init.mp4")
            download_file(mpd_info["init_url"], init_path, self.headers)
            self.initial_segment_downloaded = True

        # Descargar los segmentos de medios
        for idx, _ in enumerate(mpd_info["segments"]):
            seg_num = mpd_info["start_number"] + idx
            if seg_num not in self.downloaded_segment_numbers:
                seg_url = mpd_info["media_pattern"].replace("$Number$", str(seg_num))
                seg_path = os.path.join(self.output_dir, f"segment_{seg_num}.mp4")

                download_file(seg_url, seg_path, self.headers)
                self.downloaded_segment_numbers.add(seg_num)


def main(folder_output: Path) -> Generator[None, None, None]:
    """Función principal que ejecuta el bucle de descarga."""

    # Crear los objetos que gestionarán las descargas de video y audio
    output_video = str(folder_output / "video")
    video_downloader = RepresentationDownloader(
        REPRESENTATION_ID_VIDEO, output_video, HEADERS
    )
    output_audio = str(folder_output / "audio")
    audio_downloader = RepresentationDownloader(
        REPRESENTATION_ID_AUDIO, output_audio, HEADERS
    )

    logger.info("🚀 Iniciando descarga de stream en vivo...")

    while True:
        try:
            logger.info("\n📥 Actualizando MPD...")
            mpd_text = download_mpd(MPD_URL, HEADERS, PARAMS)

            logger.info(f"--- Procesando Video (ID: {REPRESENTATION_ID_VIDEO}) ---")
            video_downloader.process_segments_from_mpd(mpd_text)

            logger.info(f"--- Procesando Audio (ID: {REPRESENTATION_ID_AUDIO}) ---")
            audio_downloader.process_segments_from_mpd(mpd_text)

            logger.info("\n🕒 Esperando 5 segundos para el próximo ciclo...")
            time.sleep(5)
            yield None

        except KeyboardInterrupt:
            logger.info("\n⏹️ Proceso cancelado por el usuario.")
            break
        except requests.exceptions.RequestException as e:
            logger.info(f"❌ Error de red: {e}")
            logger.info("🕒 Reintentando en 10 segundos...")
            time.sleep(5)
        except Exception as e:
            logger.info(f"❌ Ocurrió un error inesperado: {e}")
            logger.info("🕒 Reintentando en 10 segundos...")
            time.sleep(5)


if __name__ == "__main__":
    ditu = Ditu()
    schedule = ditu.get_schedule()
    print(schedule)
