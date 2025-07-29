import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Union, cast

import requests

from proyect_x.ditu.api.parser import MPDInfo, extract_qualities
from proyect_x.ditu.schemas.dashmanifest_response import DashManifestResponse
from proyect_x.ditu.schemas.entitlement_response import EntitlementChannelResponse

HEADERS = {
    "Host": "d1kkcfjl98zuzm.cloudfront.net",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "okhttp/4.12.0",
}


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

    def _extract_qualities(self, mpd_text: str) -> list:
        """
        Extrae las calidades disponibles desde el MPD.
        """
        return extract_qualities(mpd_text)

    def _extract_url_init(self, Representation, base_url: str) -> str:
        ns = self.namespaces
        SegmentTemplate = Representation.find("./mpd:SegmentTemplate", ns)
        if SegmentTemplate is None:
            raise ValueError("SegmentTemplate is None")
        return base_url + SegmentTemplate.get("initialization", "")

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

    def extract_mdp_info(self, mpd_text: str):
        """
        Extrae la URL de inicialización y las URLs de los segmentos de una representación específica
        en un manifiesto MPD (MPEG-DASH).

        Args:
            mpd_text (str): Contenido del archivo MPD.
            representation_id (str): ID de la representación deseada (video o audio).

        Returns:
            dict: {
                "init_url": str,
                "segments": List[str],
                "mimetype": str,
            }

        Raises:
            ValueError: Si no se encuentra alguno de los elementos necesarios.
            Exception: Si no se encuentra la representación deseada.
        """

        root = ET.fromstring(mpd_text)  # type: ignore
        ns = self.namespaces

        # BaseURL
        BaseURL = root.find("mpd:BaseURL", ns)
        if BaseURL is None or BaseURL.text is None:
            raise ValueError("BaseURL is None or empty")
        base_url = BaseURL.text

        reps = []
        for AdaptationSet in root.findall(".//mpd:AdaptationSet", ns):
            for Representation in AdaptationSet.findall("./mpd:Representation", ns):
                is_switching = AdaptationSet.get("bitstreamSwitching", "none")
                mimetype = AdaptationSet.get("mimeType", "none")

                representation_id = Representation.get("id", "none")
                init_url = self._extract_url_init(Representation, base_url)
                segments = self._extract_segments(Representation, base_url)
                sampling_rate = Representation.get("audioSamplingRate", "none")
                bandwidth = Representation.get("bandwidth", "none")
                codecs = Representation.get("codecs", "none")

                frame_rate = Representation.get("frameRate", "none")
                height = Representation.get("height", "none")
                width = Representation.get("width", "none")

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

    def _extract_best_video_adaptation_set(self, root) -> ET.Element:
        ns = self.namespaces

        AdaptationSet = root.find(".//mpd:AdaptationSet[@mimeType='video/mp4']", ns)
        if AdaptationSet is None:
            raise ValueError("AdaptationSet is None")

        return AdaptationSet
