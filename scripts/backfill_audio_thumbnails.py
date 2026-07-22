from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import audio_directory
from app import load_audio_tracks
from app import save_audio_tracks
from app import save_youtube_thumbnail


def main() -> None:
    tracks = load_audio_tracks()
    total = 0
    updated = 0
    skipped = 0
    failed = 0

    for track in tracks:
        if track.get("source_type") != "youtube":
            continue
        total += 1
        current = track.get("thumbnail_filename", "")
        if current and (audio_directory() / current).exists():
            skipped += 1
            continue

        thumbnail_filename = save_youtube_thumbnail(track.get("url", ""))
        if thumbnail_filename:
            track["thumbnail_filename"] = thumbnail_filename
            updated += 1
            save_audio_tracks(tracks)
            print(f"updated {updated}: {track.get('id', '')}", flush=True)
        else:
            failed += 1
            print(f"failed {failed}: {track.get('id', '')}", flush=True)

    print(f"total={total}")
    print(f"updated={updated}")
    print(f"skipped={skipped}")
    print(f"failed={failed}")


if __name__ == "__main__":
    main()
