import re

from tvpipe.interfaces import EpisodeParser


class CaracolDesafioParser(EpisodeParser):
    def __init__(self):
        self._regex = re.compile(r"ap[íi]tulo\s+(\d+)", re.IGNORECASE)
        self._forbidden_keyword = "avance"

    def matches_criteria(self, title: str) -> bool:
        title_lower = title.lower()
        if self._forbidden_keyword in title_lower:
            return False

        return bool(self._regex.search(title))

    def extract_number(self, title: str) -> str:
        match = self._regex.search(title)
        if match:
            return match.group(1)
        raise ValueError(f"No se pudo extraer número del título: {title}")
