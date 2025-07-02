from pathlib import Path

FOLDER = Path(r"avance\segmentos")

FILENAME = "avance 1 capítulo 2"

with open(f"{FILENAME}.ts", "wb") as f:
    for path in FOLDER.iterdir():
        if not path.is_file():
            continue
        f.write(path.read_bytes())
