from pathlib import Path

FOLDER = Path(r"D:\github Leo\caracoltv-dl\download\capitlo 3 avance")

FILENAME = "Captilo 2"

with open(f"{FILENAME}.ts", "wb") as f:
    for path in FOLDER.iterdir():
        if not path.is_file():
            continue
        f.write(path.read_bytes())
