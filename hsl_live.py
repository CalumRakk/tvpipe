import os
import re
import time

SEGMENTS_DIR = "./HSL_LIVE"
PLAYLIST_FILE = os.path.join(SEGMENTS_DIR, "playlist.m3u8")
TARGET_DURATION = 2  # Duración estimada de cada segmento
WINDOW_SIZE = 10  # Cuántos segmentos mantener en la lista
NO_NEW_SEGMENT_THRESHOLD = 10  # Segundos para disparar CUE-OUT


def extract_seq_number(filename):
    """
    Extrae el número de secuencia final del nombre.
    E.g. media_1800_20250703T005234_309551.ts --> 309551
    """
    match = re.search(r"_(\d+)\.ts$", filename)
    if match:
        return int(match.group(1))
    return None


def get_segments():
    segments = []
    for f in os.listdir(SEGMENTS_DIR):
        if f.endswith(".ts"):
            seq = extract_seq_number(f)
            if seq is not None:
                segments.append((seq, f))
    segments.sort()  # Orden ascendente por número
    return segments


def write_playlist(segments, media_sequence, cue_out=False, cue_in=False):
    with open(PLAYLIST_FILE, "w") as f:
        f.write("#EXTM3U\n")
        f.write("#EXT-X-VERSION:3\n")
        f.write(f"#EXT-X-TARGETDURATION:{TARGET_DURATION}\n")
        f.write(f"#EXT-X-MEDIA-SEQUENCE:{media_sequence}\n\n")

        if cue_out:
            f.write("#EXT-X-CUE-OUT:Duration=99999\n")
        if cue_in:
            f.write("#EXT-X-CUE-IN\n")

        for _, segment_name in segments:
            f.write(f"#EXTINF:{TARGET_DURATION:.3f},\n")
            f.write(f"{segment_name}\n")

    print(
        f"Actualizado playlist.m3u8: SEQ={media_sequence} [{len(segments)} segmentos] "
        f"{'CUE-OUT' if cue_out else 'CUE-IN' if cue_in else ''}"
    )


def main():
    last_update_time = time.time()
    known_segments = []
    cue_out = False
    last_media_seq = None

    index = 0
    while True:
        all_segments = get_segments()

        segments = all_segments[: WINDOW_SIZE + index]
        if segments:
            last_update_time = time.time()
            media_sequence = segments[0][0]

            write_playlist(segments, media_sequence, cue_in=cue_out)
            cue_out = False

            known_segments = segments
            index += WINDOW_SIZE
        else:
            elapsed = time.time() - last_update_time
            if elapsed > NO_NEW_SEGMENT_THRESHOLD and not cue_out:
                # Sin nuevos segmentos por más del umbral => insertar CUE-OUT
                if known_segments:
                    last_segments = known_segments[-WINDOW_SIZE:]
                    media_sequence = last_segments[0][0]
                    write_playlist(last_segments, media_sequence, cue_out=True)
                    cue_out = True

        time.sleep(10)


if __name__ == "__main__":
    main()
