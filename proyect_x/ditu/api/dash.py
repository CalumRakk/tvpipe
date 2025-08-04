import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
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
logger = logging.getLogger(__name__)


@dataclass
class Representation:
    id: int
    codecs: str
    bandwidth: int
    # Estos no son atributos directos. Son atributos extradios de campos hijos.
    url_initial: str
    media: str
    segments: List[str]

    height: Optional[int]
    width: Optional[int]
    frameRate: Optional[str]
    audioSamplingRate: Optional[str]


@dataclass
class AdaptationSet:
    id: int
    bitstreamSwitching: str
    mimeType: str
    segmentAlignment: str
    startWithSAP: str
    representations: List[Representation]

    subsegmentAlignment: Optional[bool]
    subsegmentStartsWithSAP: Optional[int]
    lang: Optional[str]

    @property
    def is_video(self) -> bool:
        return "video" in self.mimeType

    @property
    def mimetype(self) -> str:
        return self.mimeType

    def get_best_representation(self, key: Optional[str] = None) -> Representation:
        """Devuelve la 'best' representacion que tenga un AdaptationSet independientemente de si es video o audio. Si se pasa un key, es importante que sea un atributo de la representacion."""
        if self.is_video:
            key = "height" if key is None else key
        else:
            key = "audioSamplingRate" if key is None else key
        return sorted(
            self.representations, key=lambda x: getattr(x, key) or 0, reverse=True
        )[0]


@dataclass
class Period:
    id: str
    start: str
    BaseURL: str
    AdaptationSets: List[AdaptationSet]

    @property
    def base_url(self) -> str:
        return self.BaseURL

    def best_video_representation(self, key: Optional[str] = None) -> Representation:
        for adapt in self.AdaptationSets:
            if adapt.is_video:
                repr = adapt.get_best_representation()
                logger.info(
                    f"🔍 Mejor representación de video: {repr.id}, {repr.height}p, {repr.bandwidth}bps"
                )
                return repr
        raise ValueError("No hay representaciones de video")

    def best_audio_representation(self, key: Optional[str] = None) -> Representation:
        for adapt in self.AdaptationSets:
            if not adapt.is_video:
                repre = adapt.get_best_representation()
                logger.info(
                    f"🔍 Mejor representación de audio: {repre.id}, {repre.audioSamplingRate}Hz, {repre.bandwidth}bps"
                )
                return repre
        raise ValueError("No hay representaciones de audio")


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
        url = data["resultObj"]["src"]

        logger.info(f"🔗 URL del DASH manifest: {url}")
        return url

    def fetch_mpd(self, url: str) -> str:
        logger.info(f"Descargando MPD: {url}")
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        logger.info(f"📄 MPD descargado correctamente")
        return response.text

    # def _extract_base_url(self, root) -> str:
    #     ns = self.namespaces
    #     for BaseURL in root.findall(".//mpd:BaseURL", ns):
    #         base_url = BaseURL.text
    #         if urlparse(base_url).path != "/":
    #             return base_url
    #     raise ValueError("BaseURL is None")

    def _extract_additional_from_childs(self, representation: ET.Element) -> dict:
        ns = self.namespaces
        segmentTemplate = representation.find("./mpd:SegmentTemplate", ns)
        assert segmentTemplate is not None, "SegmentTemplate is None"

        initialization = segmentTemplate.attrib["initialization"]
        media = segmentTemplate.attrib["media"]
        presentationTimeOffset = segmentTemplate.attrib["presentationTimeOffset"]
        startNumber = segmentTemplate.attrib["startNumber"]
        timescale = segmentTemplate.attrib["timescale"]
        return {
            "initialization": initialization,
            "media": media,
            "presentationTimeOffset": presentationTimeOffset,
            "startNumber": startNumber,
            "timescale": timescale,
        }

        # urljoin(base_url, SegmentTemplate.get("initialization", ""))

    def _extract_segments(
        self,
        representation: ET.Element,
        media: str,
        startNumber: Union[int, str],
        base_url: str,
    ) -> list[str]:
        ns = self.namespaces
        media_pattern = media

        segments: List[str] = []
        current_number = int(startNumber)
        for S in representation.findall(".//mpd:S", ns):
            repeat = int(S.get("r", 0))
            for _ in range(repeat + 1):
                url = urljoin(
                    base_url, media_pattern.replace("$Number$", str(current_number))
                )
                segments.append(url)
                current_number += 1
        return segments

    def _extract_representations(
        self, adaptationSet: ET.Element, base_url: str
    ) -> list[Representation]:
        ns = self.namespaces
        representations: List[Representation] = []
        for representation in adaptationSet.findall(".//mpd:Representation", ns):
            representation_id = int(representation.attrib["id"])
            codecs = representation.attrib["codecs"]
            bandwidth = int(representation.attrib["bandwidth"])

            data_additional = self._extract_additional_from_childs(representation)
            url_initial = urljoin(base_url, data_additional["initialization"])
            media = data_additional["media"]
            start_number = data_additional["startNumber"]
            segments = self._extract_segments(
                representation, media, start_number, base_url
            )

            frameRate = representation.get("frameRate", None)
            audioSamplingRate = representation.get("audioSamplingRate", None)

            height = representation.get("height", None)
            height = int(height) if height else None

            width = representation.get("width", None)
            width = int(width) if width else None

            logger.debug(
                f"📦 Representación encontrada: {representation_id}, "
                f"codecs: {codecs}, bandwidth: {bandwidth}, "
                f"init_url: {url_initial}, segments: {len(segments)}"
                f", height: {height}, width: {width}, "
            )
            representations.append(
                Representation(
                    id=representation_id,
                    codecs=codecs,
                    bandwidth=bandwidth,
                    url_initial=url_initial,
                    media=media,
                    segments=segments,
                    height=height,
                    width=width,
                    frameRate=frameRate,
                    audioSamplingRate=audioSamplingRate,
                )
            )
        return representations

    def _extract_adaptation_sets(
        self, period: ET.Element, base_url: str
    ) -> list[AdaptationSet]:
        ns = self.namespaces
        adaptationSets: List[AdaptationSet] = []
        for apdationSet in period.findall(".//mpd:AdaptationSet", ns):
            adationSet_id = int(apdationSet.attrib["id"])
            bitstreamSwitching = apdationSet.attrib["bitstreamSwitching"]
            mimeType = apdationSet.attrib["mimeType"]
            segmentAlignment = apdationSet.attrib["segmentAlignment"]
            startWithSAP = apdationSet.attrib["startWithSAP"]
            representations = self._extract_representations(apdationSet, base_url)

            subsegmentAlignment = apdationSet.get("subsegmentAlignment", None)
            subsegmentAlignment = (
                bool(subsegmentAlignment)
                if isinstance(subsegmentAlignment, str)
                else None
            )
            subsegmentStartsWithSAP = apdationSet.get("subsegmentStartsWithSAP", None)
            subsegmentStartsWithSAP = (
                int(subsegmentStartsWithSAP)
                if isinstance(subsegmentStartsWithSAP, str)
                else None
            )
            lang = apdationSet.get("lang", None)

            adaptationSets.append(
                AdaptationSet(
                    id=adationSet_id,
                    bitstreamSwitching=bitstreamSwitching,
                    mimeType=mimeType,
                    segmentAlignment=segmentAlignment,
                    startWithSAP=startWithSAP,
                    representations=representations,
                    subsegmentAlignment=subsegmentAlignment,
                    subsegmentStartsWithSAP=subsegmentStartsWithSAP,
                    lang=lang,
                )
            )
        return adaptationSets

    def _extract_periods(self, root: ET.Element) -> list[Period]:
        ns = self.namespaces

        periods: List[Period] = []
        for period_element in root.findall(".//mpd:Period", ns):
            period_id = period_element.attrib["id"]
            start = period_element.attrib["start"]

            baseurl = period_element.find("./mpd:BaseURL", ns)
            assert baseurl is not None
            base_url = cast(str, baseurl.text)

            adaptationSets = self._extract_adaptation_sets(period_element, base_url)

            logger.debug(f"📦 Periodo parseado: Id {period_id} | BaseUrl {base_url}")
            periods.append(
                Period(
                    id=period_id,
                    start=start,
                    BaseURL=base_url,
                    AdaptationSets=adaptationSets,
                )
            )
        logger.info(f"📦 Periodos extraidos del MPD: {len(periods)}")
        return periods

    def parse_periods(self, mpd_text: str) -> list[Period]:
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
        return self._extract_periods(root)
