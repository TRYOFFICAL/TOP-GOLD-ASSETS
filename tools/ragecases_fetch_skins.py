from __future__ import annotations
import csv, io, json, os, sys, time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tools" / "manifest_test_20.json"
OUT = ROOT / "assets" / "ragecases_skins_v2_test"
REPORT = OUT / "REPORT.csv"
RESOLVED = OUT / "resolved_files.json"
PREVIEW = OUT / "index.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/148 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/png,image/jpeg,image/*,*/*;q=0.8",
    "Referer": "https://ggstand.com/",
}


def has_meaningful_alpha(im: Image.Image) -> tuple[bool, float]:
    rgba = im.convert("RGBA")
    alpha = rgba.getchannel("A")
    hist = alpha.histogram()
    total = max(1, sum(hist))
    transparent = sum(hist[:250])
    return transparent > 0, transparent / total


def fetch(session: requests.Session, url: str) -> bytes:
    last = None
    for attempt in range(1, 5):
        try:
            r = session.get(url, headers=HEADERS, timeout=(20, 90), allow_redirects=True)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            if len(r.content) < 1000:
                raise RuntimeError(f"too small: {len(r.content)} bytes")
            return r.content
        except Exception as e:
            last = e
            print(f"      attempt {attempt}/4 failed: {e}")
            time.sleep(1.5 * attempt)
    raise RuntimeError(str(last) if last else "download failed")


def main() -> int:
    items = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    OUT.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    # Warm-up is optional; direct assets can work without it.
    try:
        session.get("https://ggstand.com/en/case/sttrack", headers=HEADERS, timeout=(15, 30))
    except Exception as e:
        print(f"Warm-up warning: {e}")

    rows = []
    resolved = []
    ok = fail = replaced = added = 0

    print("RAGECASES — GitHub Fetch Test 20")
    print("Output: assets/ragecases_skins_v2_test/")
    print("StatTrack prefix is ignored for filenames. All successful outputs are lossless WebP.")
    print()

    for item in items:
        idx = int(item["index"])
        name = str(item["skin_name"])
        base = str(item["output_base"])
        mode = str(item.get("mode", ""))
        dest = OUT / f"{base}.webp"
        had_old = dest.exists()
        success = False
        used = ""
        note = ""
        alpha_ratio = 0.0
        source_format = ""
        source_size = 0

        print(f"[{idx:02d}/20] {name}")
        for url in item.get("source_urls", []):
            if not url:
                continue
            print(f"   trying: {url}")
            try:
                blob = fetch(session, url)
                source_size = len(blob)
                with Image.open(io.BytesIO(blob)) as im:
                    source_format = (im.format or "unknown").upper()
                    im.load()
                    has_alpha, alpha_ratio = has_meaningful_alpha(im)
                    rgba = im.convert("RGBA")
                    tmp = dest.with_suffix(".webp.tmp")
                    rgba.save(tmp, format="WEBP", lossless=True, method=6)
                    # Re-open written output before replacing final file.
                    with Image.open(tmp) as chk:
                        chk.verify()
                    os.replace(tmp, dest)
                used = url
                note = f"source={source_format}; alpha_pixels={alpha_ratio:.4%}; source_bytes={source_size}"
                if not has_alpha:
                    note += "; WARNING_NO_TRANSPARENT_PIXELS"
                success = True
                break
            except Exception as e:
                note = str(e)
                print(f"      failed: {e}")

        if success:
            size = dest.stat().st_size
            ok += 1
            if had_old:
                replaced += 1
                action = "REPLACED_TEST_FILE"
            else:
                added += 1
                action = "ADDED_TEST_FILE"
            print(f"   OK -> {dest.name} ({size} bytes) | {note}")
            rows.append([idx, name, mode, "OK", dest.name, size, used, note])
            resolved.append({
                "skin_name": name,
                "canonical_name": item.get("canonical_name", name),
                "filename": dest.name,
                "source_url": used,
                "mode": mode,
                "action": action,
                "alpha_ratio": alpha_ratio,
            })
        else:
            fail += 1
            print(f"   FAILED -> {note}")
            rows.append([idx, name, mode, "FAILED", "", 0, used, note])

        time.sleep(0.4)

    with REPORT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "skin_name", "mode", "status", "filename", "size_bytes", "source_url", "note"])
        w.writerows(rows)

    RESOLVED.write_text(json.dumps(resolved, ensure_ascii=False, indent=2), encoding="utf-8")

    cards = []
    for r in resolved:
        alpha = f'{r["alpha_ratio"]:.2%}'
        cards.append(f'''<article><div class="pic"><img src="{r['filename']}" alt=""></div><b>{r['skin_name']}</b><small>{r['filename']}</small><small>transparent pixels: {alpha}</small></article>''')
    PREVIEW.write_text(f'''<!doctype html><meta charset="utf-8"><title>RAGECASES — Skin Test 20</title>
<style>body{{margin:0;background:#0f0f11;color:#fff;font:14px Arial;padding:24px}}h1{{color:#ffd447}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}}article{{background:#101012;border:1px solid #2b2e33;border-radius:14px;padding:12px}}.pic{{height:150px;display:grid;place-items:center;border-radius:10px;background-color:#ddd;background-image:linear-gradient(45deg,#bbb 25%,transparent 25%),linear-gradient(-45deg,#bbb 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#bbb 75%),linear-gradient(-45deg,transparent 75%,#bbb 75%);background-size:20px 20px;background-position:0 0,0 10px,10px -10px,-10px 0}}.pic img{{max-width:100%;max-height:100%;object-fit:contain}}b,small{{display:block;margin-top:8px}}small{{color:#aaa}}</style>
<h1>RAGECASES — TEST 20</h1><p>Шахматный фон показывает прозрачность. REPORT.csv содержит результат по каждому скину.</p><div class="grid">{''.join(cards)}</div>''', encoding="utf-8")

    print()
    print(f"RESULT: OK={ok} FAILED={fail} TEST_REPLACED={replaced} TEST_ADDED={added}")
    print(f"Report: {REPORT.relative_to(ROOT)}")
    print(f"Preview: {PREVIEW.relative_to(ROOT)}")
    return 0 if fail == 0 else 2

if __name__ == "__main__":
    raise SystemExit(main())
