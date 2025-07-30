import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Literal, Optional, TypedDict, Union, cast
from urllib.parse import urljoin, urlparse

import requests

from proyect_x.ditu.schemas.dashmanifest_response import DashManifestResponse
from proyect_x.ditu.schemas.entitlement_response import EntitlementChannelResponse

HEADERS = {
    "Host": "d1kkcfjl98zuzm.cloudfront.net",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "okhttp/4.12.0",
}


class Representation(TypedDict):
    representation_id: str
    init_url: str
    segments: List[str]
    mimetype: str
    is_switching: bool
    bandwidth: int

    sampling_rate: Optional[int]
    codecs: Optional[str]
    frame_rate: Optional[str]
    height: Optional[int]
    width: Optional[int]


class Dash:
    namespaces = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}

    def _get_entitlements_for_live_channel(
        self, channel_id: int
    ) -> EntitlementChannelResponse:
        """Obtiene la información de derechos de reproducción ("entitlement") y los assets disponibles (por ejemplo, LIVE_HD) para una transmisión en vivo del canal especificado. Sirve para determinar si el canal puede reproducirse y qué assets están disponibles, incluyendo su assetId, que puede usarse en otro endpoint (como el de VIDEOURL).

        Nota: No se usa de momento.
        """
        url = "https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/CONTENT/USERDATA/LIVE/20"
        params = {
            "filter_channelIds": str(channel_id),
            "filter_entitlementType": "live",
        }
        response = requests.get(url, params=params, headers=HEADERS)
        response.raise_for_status()
        return response.json()

    def get_live_channel_manifest(self, channel_id: Union[str, int]) -> str:
        """Obtiene un JSON con la URL del DASH manifest para la transmision en vivo del canal especificado."""
        url = f"https://varnish-prod.avscaracoltv.com/AGL/1.6/A/ENG/ANDROID/ALL/CONTENT/VIDEOURL/LIVE/{channel_id}/10"
        headers = {
            "Restful": "yes",
            "Accept-Encoding": "gzip, deflate, br",
            "User-Agent": "okhttp/4.12.0",
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data: DashManifestResponse = response.json()
        return data["resultObj"]["src"]

    def fetch_mpd(self, url: str) -> str:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.text

    def _extract_url_init(self, Representation, base_url: str) -> str:
        ns = self.namespaces
        SegmentTemplate = Representation.find("./mpd:SegmentTemplate", ns)
        if SegmentTemplate is None:
            raise ValueError("SegmentTemplate is None")
        return urljoin(base_url, SegmentTemplate.get("initialization", ""))

    def _extract_segments(self, Representation, base_url: str) -> list[str]:
        ns = self.namespaces
        SegmentTemplate = Representation.find("./mpd:SegmentTemplate", ns)
        if SegmentTemplate is None:
            raise ValueError("SegmentTemplate is None")

        SegmentTimeline = SegmentTemplate.find("./mpd:SegmentTimeline", ns)
        if SegmentTimeline is None:
            raise ValueError("SegmentTimeline is None")

        # Inicialización
        media_pattern = base_url + SegmentTemplate.get("media", "")
        start_number = int(SegmentTemplate.get("startNumber", 1))

        segments: List[str] = []
        current_number = start_number

        for S in SegmentTimeline.findall("mpd:S", ns):
            repeat = int(S.get("r", 0))
            for _ in range(repeat + 1):
                segments.append(media_pattern.replace("$Number$", str(current_number)))
                current_number += 1
        return segments

    def _extract_base_url(self, root) -> str:
        ns = self.namespaces
        for BaseURL in root.findall(".//mpd:BaseURL", ns):
            base_url = BaseURL.text
            if urlparse(base_url).path != "/":
                return base_url
        raise ValueError("BaseURL is None")

    def parse_mpd_representations(self, mpd_text: str) -> list[Representation]:
        """
        Este método analiza el contenido XML de un MPD para obtener detalles técnicos de cada representación de audio y video
        disponibles en los AdaptationSet del manifiesto. Entre los datos extraídos se incluyen: URLs de inicialización y segmentos,
        resoluciones, tasas de muestreo, códecs, ancho de banda y otros atributos multimedia.

        Args:
            mpd_text (str): Contenido completo del archivo MPD en formato XML.

        Returns:
            list[dict]: Una lista de diccionarios, cada uno representando una representación multimedia encontrada.
                        Cada diccionario contiene claves como:
                        - representation_id
                        - init_url
                        - segments
                        - mimetype
                        - is_switching
                        - sampling_rate
                        - bandwidth
                        - codecs
                        - frame_rate
                        - height
                        - width

        Raises:
            ValueError: Si no se encuentra o está vacío el elemento BaseURL requerido para construir las URLs absolutas.
        """

        root = ET.fromstring(mpd_text)  # type: ignore
        ns = self.namespaces

        base_url = self._extract_base_url(root)

        reps = []
        for AdaptationSet in root.findall(".//mpd:AdaptationSet", ns):
            for Representation in AdaptationSet.findall("./mpd:Representation", ns):
                is_switching = AdaptationSet.get("bitstreamSwitching", "none")
                mimetype = AdaptationSet.get("mimeType", "none")

                representation_id = int(Representation.get("id", "none"))
                init_url = self._extract_url_init(Representation, base_url)
                segments = self._extract_segments(Representation, base_url)
                bandwidth = Representation.get("bandwidth", "none")

                sampling_rate = Representation.get("audioSamplingRate", None)
                sampling_rate = int(sampling_rate) if sampling_rate else None

                codecs = Representation.get("codecs", None)
                frame_rate = Representation.get("frameRate", None)

                height = Representation.get("height", None)
                height = int(height) if height else None
                width = Representation.get("width", None)
                width = int(width) if width else None

                reps.append(
                    {
                        "representation_id": representation_id,
                        "init_url": init_url,
                        "segments": segments,
                        "mimetype": mimetype,
                        "is_switching": is_switching,
                        "sampling_rate": sampling_rate,
                        "bandwidth": bandwidth,
                        "codecs": codecs,
                        "frame_rate": frame_rate,
                        "height": height,
                        "width": width,
                    }
                )
        return reps
