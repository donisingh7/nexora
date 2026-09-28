import re
import unicodedata
from pathlib import PurePath

_INVALID_FILENAME_CHARACTERS = re.compile(r"[^A-Za-z0-9._ -]+")


def sanitize_filename(filename: str) -> str:
    normalized = unicodedata.normalize("NFKC", filename).replace("\\", "/")
    basename = PurePath(normalized).name
    cleaned = _INVALID_FILENAME_CHARACTERS.sub("_", basename).strip(" .")
    cleaned = cleaned.lstrip(".")[:255]
    return cleaned or "upload"
