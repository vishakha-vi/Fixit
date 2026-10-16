#!/usr/bin/env python3
"""Vendor static assets (Bootstrap CSS/JS and HTMX) into static/vendor/."""

import hashlib
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VENDOR_DIR = BASE_DIR / "static" / "vendor"

ASSETS = [
    {
        "name": "bootstrap.min.css",
        "version": "5.3.3",
        "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
    },
    {
        "name": "bootstrap.bundle.min.js",
        "version": "5.3.3",
        "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
    },
    {
        "name": "htmx.min.js",
        "version": "2.0.4",
        "url": "https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js",
    },
]


def download_and_vendor():
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    print(f"Vendoring static assets into: {VENDOR_DIR}")
    for item in ASSETS:
        dest = VENDOR_DIR / item["name"]
        print(f"Fetching {item['name']} (v{item['version']}) from {item['url']}...")
        try:
            req = urllib.request.Request(
                item["url"],
                headers={"User-Agent": "FixIt-Asset-Vendoring/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
        except Exception as exc:
            print(f"ERROR: Failed to download {item['name']}: {exc}", file=sys.stderr)
            return False

        sha256 = hashlib.sha256(data).hexdigest()
        dest.write_bytes(data)
        size_kb = len(data) / 1024
        print(f"  -> Saved {item['name']} ({size_kb:.1f} KB) SHA-256: {sha256}")
        manifest.append(f"{item['name']} (v{item['version']}) - {sha256}")

    # Write manifest log
    manifest_path = VENDOR_DIR / "manifest.txt"
    manifest_path.write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(f"Vendor manifest written to {manifest_path}")
    return True


if __name__ == "__main__":
    success = download_and_vendor()
    sys.exit(0 if success else 1)
