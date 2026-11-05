"""Fetch a small, pinned, attributed BVH pilot set; no packages required.

Downloads 12 source motions + LICENSE, never overwrites existing raw files.
Original style names are not social-status annotations. Outputs a provenance
manifest and validation report, not a perception result.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.bvh import load

REVISION = "74ead3ba1ae4696404e6086233779f60de8bf9ef"
REPOSITORY = "https://github.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset"
BASE = f"https://raw.githubusercontent.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset/{REVISION}/dataset/Bandai-Namco-Research-Motiondataset-1/"
STYLES = ("normal", "proud", "not-confident")
CONTENTS = ("walk", "walk-back", "walk-left", "walk-right")


def fetch(relative, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    # Use curl for bounded wall time and the host's configured network support.
    with tempfile.TemporaryDirectory(prefix="motion-fetch-") as temporary:
        staging = Path(temporary) / "payload"
        subprocess.run([
            "curl", "--compressed", "-fsSL", "--connect-timeout", "5",
            "--max-time", "35", "--retry", "1", "-o", str(staging), BASE + relative,
        ], check=True, capture_output=True)
        content = staging.read_bytes()
        if relative.endswith(".bvh"):
            load(staging)  # Reject malformed downloads before copying into raw data.
        with destination.open("xb") as output:
            output.write(content)


def main():
    raw = ROOT / "data/raw/bandai-pilot"
    fetch("LICENSE", raw / "LICENSE")
    fetch("README.md", raw / "SOURCE_README.md")

    def prepare(pair):
        content, style = pair
        name = f"dataset-1_{content}_{style}_001.bvh"
        path = raw / name
        relative = "data/" + name
        entry = {"file": str(path.relative_to(ROOT)), "source_url": BASE + relative,
                 "source_content": content, "source_style": style, "status_label": None}
        try:
            fetch(relative, path)
            entry.update({"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "bytes": path.stat().st_size, "validation": load(path).summary()})
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            entry["error"] = str(error)
        return entry

    with ThreadPoolExecutor(max_workers=3) as pool:
        entries = list(pool.map(prepare, [(c, s) for c in CONTENTS for s in STYLES]))
    manifest = {"repository": REPOSITORY, "revision": REVISION,
                "license": "CC BY-NC 4.0", "creator": "Bandai Namco Research Inc.",
                "purpose": "Unmodified source subset for exploratory motion inspection; not status ground truth",
                "entries": entries}
    manifest_path = ROOT / "data/pilot_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    passed = [entry for entry in entries if "error" not in entry]
    print(json.dumps({"validated": len(passed), "requested": len(entries),
                      "bytes": sum(e["bytes"] for e in passed),
                      "playback_seconds": sum(e["validation"]["playback_duration_seconds"] for e in passed),
                      "manifest": str(manifest_path),
                      "errors": [e for e in entries if "error" in e]}, ensure_ascii=False, indent=2))
    return 0 if len(passed) == len(entries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
