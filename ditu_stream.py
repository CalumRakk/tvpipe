import logging
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from time import sleep
from typing import Dict, Generator, List, Set, TypedDict, Union
from urllib.parse import urlparse

import requests

from proyect_x.ditu.ditu import Ditu

logger = logging.getLogger(__name__)


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


class MPDInfo(TypedDict):
    """Estructura de datos para la información de una Representation del MPD."""

    base_url: str
    init_url: str
    media_pattern: str
    start_number: int
    segments: List[ET.Element]
    mimetype: str


def get_qualities_from_mpd(mpd_text: str) -> List[Dict[str, str]]:
    """
    Extrae las calidades de video y audio del MPD.

    Args:
        mpd_text: El contenido del MPD como una cadena de texto.

    Returns:
        Una lista de diccionarios con las calidades de video y audio.
    """
    ns = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}
    root = ET.fromstring(mpd_text)  # type: ignore

    qualities = []
    for aset in root.findall(".//mpd:AdaptationSet", ns):
        for rep in aset.findall("mpd:Representation", ns):
            qualities.append(
                {
                    "representation_id": rep.attrib.get("id", ""),
                    "width": rep.attrib.get("width", ""),
                    "height": rep.attrib.get("height", ""),
                    "bandwidth": rep.attrib.get("bandwidth", ""),
                    "mimeType": aset.attrib.get("mimeType", ""),
                }
            )
    return qualities


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
    root = ET.fromstring(xml_text)  # type: ignore

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
                    mimetype=aset.attrib.get("mimeType", ""),
                )

    raise Exception(f"No se encontró Representation ID {representation_id}")


class DituStream(Ditu):

    def _get_url_dash_manifest(self, channel_id: Union[str, int]):
        """
        Obtiene la URL del manifiesto DASH para un canal en vivo.
        """
        response = self._get_dash_manifest_for_live_channel(channel_id)
        return response["resultObj"]["src"]

    def _download_dash_manifest(self, url) -> str:
        """
        Descarga el manifiesto DASH desde la URL proporcionada.

        Args:
            url: La URL del manifiesto DASH.

        Returns:
            El contenido del manifiesto como una cadena de texto.
        """
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.text

    def extract_qualities_from_mpd(self, mpd_text: str) -> List[Dict[str, str]]:
        """
        Extrae las calidades de video y audio del MPD.

        Args:
            mpd_text: El contenido del MPD como una cadena de texto.

        Returns:
            Una lista de diccionarios con las calidades de video y audio.
        """
        return get_qualities_from_mpd(mpd_text)

    def extract_mdpinfo_from_text(
        self, mpd_text: str, representation_id: str
    ) -> MPDInfo:
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
        return parse_mpd_representation(mpd_text, representation_id)

    def _download_segment(self, url, output_path: Path) -> None:
        """
        Descarga un archivo desde una URL a una ruta de destino.

        Args:
            url: La URL del archivo a descargar.
            output_path: La ruta donde se guardará el archivo.
            headers: Las cabeceras HTTP para la petición.
        """
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(r.content)
        logger.info(f"✅ Descargado: {output_path}")

    def download_mdpinfo(self, mdpinfo: dict, folder_output: Path) -> None:
        mime, ext = mdpinfo["mimetype"].split("/")
        folder_final = folder_output / mime

        initial_segment_path = folder_final / Path(f"init.{ext}")
        if not initial_segment_path.exists():
            self._download_segment(mdpinfo["init_url"], initial_segment_path)

        for idx, _ in enumerate(mdpinfo["segments"]):
            seg_num = mdpinfo["start_number"] + idx
            seg_url = mdpinfo["media_pattern"].replace("$Number$", str(seg_num))

            filename = Path(urlparse(seg_url).path).name
            seg_path = folder_final / filename

            if not seg_path.exists():
                self._download_segment(seg_url, seg_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dite = DituStream()
    channel_info = dite.get_schannel_info_by_name("Caracol TV")
    if channel_info:
        channel_id = channel_info["channelId"]
        data = dite._get_url_dash_manifest(channel_id)
        md_text = dite._download_dash_manifest(data)
        qualities = dite.extract_qualities_from_mpd(md_text)
        audio_qualities = [q for q in qualities if q["mimeType"] == "audio/mp4"]
        video_qualities = [q for q in qualities if q["mimeType"] == "video/mp4"]

        video_qualities.sort(key=lambda x: int(x["bandwidth"]), reverse=True)
        audio_qualities.sort(key=lambda x: int(x["bandwidth"]), reverse=True)

        print(video_qualities[0])
