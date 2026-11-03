"""Download checksum-verified XLSX source records from Mendeley version 4."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "data/metadata/mendeley_v7p6y654ft_v4.json"


def main():
    metadata = json.loads(METADATA.read_text(encoding="utf8"))
    assert metadata["version"] == 4
    raw = ROOT / "data/raw/pla_v7p6y654ft_v4"
    raw.mkdir(parents=True, exist_ok=True)
    selected = [f for f in metadata["files"] if f["filename"].lower().endswith(".xlsx")]
    assert len({f["filename"] for f in selected}) == len(selected)

    def acquire(record):
        details = record["content_details"]
        path = raw / record["filename"]
        if path.exists():
            blob = path.read_bytes()
        else:
            request = urllib.request.Request(details["download_url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=90) as response:
                blob = response.read()
        actual = hashlib.sha256(blob).hexdigest()
        assert actual == details["sha256_hash"], record["filename"]
        assert len(blob) == details["size"], record["filename"]
        if not path.exists():
            path.write_bytes(blob)
        return {"filename": record["filename"], "source_id": record["id"],
                "source_url": details["download_url"], "bytes": len(blob),
                "sha256": actual, "expected_sha256": details["sha256_hash"],
                "local_path": path.relative_to(ROOT).as_posix()}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        manifest = list(pool.map(acquire, selected))
    report = {"doi": "10.17632/v7p6y654ft.4", "version": 4,
              "metadata_sha256": hashlib.sha256(METADATA.read_bytes()).hexdigest(),
              "license": metadata["data_licence"], "downloaded": manifest,
              "repository_file_count": len(metadata["files"]),
              "selection": "All XLSX files; geometric STL and deformation photographs omitted"}
    (ROOT / "data/metadata/pla_download_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    print("Downloaded and SHA256-verified", len(manifest), "files;", sum(f["bytes"] for f in manifest), "bytes")


if __name__ == "__main__":
    main()
