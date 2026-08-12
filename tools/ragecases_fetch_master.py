from __future__ import annotations
import csv, html as htmlmod, io, json, os, re, sys, time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tools" / "ragecases_skins_master.json"
OVERRIDES = ROOT / "tools" / "known_source_overrides.json"
OUT = ROOT / "assets" / "ragecases_skins_v2"
REPORT = OUT / "REPORT.csv"
RESOLVED = OUT / "resolved_files.json"
FAILED = OUT / "FAILED_ITEMS.json"
MAP_JSON = OUT / "skin_images_map_v2.json"
MAP_JS = OUT / "skin_images_map_v2.js"
PREVIEW = OUT / "index.html"
READY = OUT / "READY_TO_SWITCH.txt"
BASE = "https://ggstand.com"
MIRROR_BASES = [
    "https://ggstandoff.pro",
    "https://ggstand.io",
    "https://ggstandoff.plus",
]
PAGES_BASE = "https://tryoffical.github.io/TOP-GOLD-ASSETS/assets/ragecases_skins_v2/"
FORCE = os.environ.get("FORCE_REDOWNLOAD", "false").lower() in {"1","true","yes","on"}
STRICT_REPAIR_ADD_NEW = os.environ.get("STRICT_REPAIR_ADD_NEW", "false").lower() in {"1","true","yes","on"}
REPAIR_FAILED_ONLY = os.environ.get("REPAIR_FAILED_ONLY", "false").lower() in {"1","true","yes","on"}

KNOWN_BAD_OUTPUT_FILES = {
    "butterfly_glitch.webp",
    "kunai_glitch.webp",
    "tanto_glitch.webp",
    "tec_9_glitch.webp",
    "g22_adam.webp",
    "desert_eagle_gambit.webp",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/148 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,image/png,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://ggstand.com/",
}
IMAGE_HEADERS = dict(HEADERS)
IMAGE_HEADERS["Accept"] = "image/avif,image/webp,image/apng,image/png,image/jpeg,image/*,*/*;q=0.8"

# Known page slugs. The resolver also generates automatic candidates.
PRIMARY = {
    "AKR": ["akr"], "AKR12": ["akr12"], "AWM": ["awm"],
    "Akimbo Uzi": ["akimbo-uzi", "akimbo"], "Berettas": ["berettas"],
    "FabM": ["fabm"], "Graffiti": ["graffiti"], "jKommando": ["jkommando", "j-kommando"],
    "Butterfly": ["butterfly-case", "butterfly"], "Desert Eagle": ["deagle", "desert-eagle"],
    "Dual Daggers": ["dual-daggers", "dualdaggers"], "F/S": ["f-s", "fs"],
    "FAMAS": ["famas"], "FN FAL": ["fn-fal", "fnfal"], "Fang": ["fang"],
    "G22": ["g22"], "Karambit": ["karambit"], "Kukri": ["kukri"], "Kunai": ["kunai"],
    "M16": ["m16"], "M4": ["m4"], "M40": ["m40"], "M4A1": ["m4a1"], "M60": ["m60"],
    "M9 Bayonet": ["m9-bayonet", "m9bayonet", "m9"], "MAC10": ["mac10"], "MP5": ["mp5"],
    "MP7": ["mp7"], "Mantis": ["mantis"], "P350": ["p350"], "P90": ["p90"],
    "SM1014": ["sm1014"], "SPAS": ["spas"], "Scorpion": ["scorpion"],
    "Sticker": ["sticker"], "Sting": ["sting"], "TEC-9": ["tec9", "tec-9"],
    "UMP45": ["ump", "ump45"], "USP": ["usp"], "VAL": ["val"],
    "S1 FabM": ["year-of-horse-st-collection"], "S2 F/S": ["year-of-horse-st-collection"],
    "S1 F/S": ["year-of-horse-st-collection"], "S3 FabM": ["year-of-horse-st-collection"],
    "S3 Mallard": ["year-of-horse-st-collection"],
}

SPECIAL = {
    "Sticker | Sandstone": ["sandstone", "erox"],
    "S1 FabM | Cloud Lily": ["year-of-horse-st-collection"],
    "S2 F/S | Burning Mist": ["year-of-horse-st-collection"],
    "S3 Mallard | Ink Wash": ["year-of-horse-st-collection", "ancient-coin-st"],
    "VAL | Rosa Mortal": ["dia-de-muertos-st-collection"],
    "Akimbo Uzi | Yokai": ["aguia-noob"],
    "Mantis | Eclipse": ["turbo", "ezknife-m-st"],
    "Sting | Arcane Surge": ["arcane-surge-50-on-50"],
    "Kukri | Cascade": ["syndicate-st-collection"],
    "Kukri | Prophet": ["legends-case"],
    "Kunai | Poison": ["ezknife-m-st", "turbo"],
    "MP5 | Insanity": ["subject-x-st-collection"],
    "Butterfly | Glitch": ["ezknife", "black-knives"],
    "Kunai | Glitch": ["ezknife", "kunai-pack", "black-knives"],
    "Tanto | Glitch": ["ezknife", "tanto", "black-knives"],
    "TEC-9 | Glitch": ["pubg-mobile", "fireplace", "poison-cocktail"],
    "Desert Eagle | Gambit": ["gambit", "deagle"],
    "G22 | Adam": ["g22", "division"],
}

ABSOLUTE_PAGE_HINTS = {
    "USP | Warden": [
        "https://ggstand.com/ru/case/9-years-st",
    ],
    "G22 | Adam": [
        "https://ggstand.com/ru/case/9-years-st",
    ],
    "UMP45 | Professional": [
        "https://ggstand.com/en/case/ump",
        "https://ggstand.com/ru/case/9-years-st",
    ],
    "MP7 | Frequency": [
        "https://ggstand.com/ru/case/9-years-st",
    ],
    "M4A1 | Contour": [
        "https://ggstand.com/ru/case/9-years-st",
    ],
    "FabM | Mayhem": [
        "https://ggstand.com/en/seven-keys/unommon-7keys",
        "https://ggstand.com/cis/seven-keys/unommon-7keys",
    ],
    "USP | Fiend": [
        "https://ggstand.com/en/case/fable",
        "https://ggstand.com/en/seven-keys/unommon-7keys",
    ],
    "Graffiti | Gold Skull Packed": [
        "https://ggstandoff.pro/ru/case/grafitti",
        "https://ggstandoff.pro/ru/seven-keys/unommon-7keys",
    ],
    "Karambit | Hologram": [
        "https://ggstand.io/es/case/winter-tale-st",
    ],
    "AWM | Dark Camo": [
        "https://ggstand.com/en/case/valor",
    ],
    "MAC10 | Cardboard": [
        "https://ggstand.com/en/case/valor",
    ],
    "Akimbo Uzi | No Escape": [
        "https://ggstand.io/ru/case/breakout",
    ],
    "P350 | Lab Prototype": [
        "https://ggstand.io/ru/case/breakout",
    ],
    "SPAS | Waypoint": [
        "https://ggstand.io/ru/case/breakout",
    ],
    # M4A1 | Cyber Dragon intentionally has no guessed source.
}

THEME_HINTS = {
    "Jade Stone": ["year-of-horse-st-collection"],
    "Burning Mist": ["year-of-horse-st-collection"],
    "Cloud Lily": ["year-of-horse-st-collection"],
    "Ink Wash": ["year-of-horse-st-collection"],
    "Flor de Muertos": ["dia-de-muertos-st-collection", "ancient-coin-st"],
    "Howling Ghost": ["dia-de-muertos-st-collection", "erox"],
    "Leviathan": ["dia-de-muertos-st-collection"],
    "Rosa Mortal": ["dia-de-muertos-st-collection"],
    "Arcane Surge": ["arcane-surge-50-on-50", "wild-safari-s-st"],
}

# Broad fallbacks are only fetched once because page_cache is shared.
FALLBACK = [
    "sttrack", "common", "uncommon", "rare", "epic", "legendary", "arcane",
    "ezknife-m-st", "origin", "nameless", "turbo", "millionaire", "ggstnff",
    "sandstone", "year-of-horse-st-collection", "dia-de-muertos-st-collection",
    "subject-x-st-collection", "syndicate-st-collection", "outcast-st-collection",
    "wild-safari-s-st", "summer-st-case", "reforged-st-collection",
    "ancient-coin-st", "erox", "aguia-noob", "darling-st", "legends-case",
]

def norm(s: str) -> str:
    s = htmlmod.unescape(str(s or ""))
    s = s.replace("StatTrack* ", "").replace("STATTRACK* ", "")
    return re.sub(r"\s+", " ", s).strip().casefold()

def slug_variants(weapon: str) -> list[str]:
    s = weapon.casefold().replace("&", "and")
    h = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    n = re.sub(r"[^a-z0-9]+", "", s)
    out=[]
    for x in (h,n):
        if x and x not in out: out.append(x)
    return out

def make_page_url(slug: str) -> str:
    return f"{BASE}/en/case/{slug}"

def mirror_page_urls(slug: str) -> list[str]:
    out=[]
    for base in MIRROR_BASES:
        # Mirrors are more consistently indexed in Russian, but try English too.
        for lang in ("ru","en"):
            url=f"{base}/{lang}/case/{slug}"
            if url not in out:
                out.append(url)
    return out

def best_src(tag) -> str:
    for key in ("data-src", "data-lazy-src", "data-original", "src"):
        v = tag.get(key)
        if v and not str(v).startswith("data:"):
            return str(v)
    srcset = tag.get("srcset") or tag.get("data-srcset")
    if srcset:
        return str(srcset).split(",")[-1].strip().split()[0]
    return ""

def fetch_text(session: requests.Session, url: str) -> str:
    last=None
    for attempt in range(1,4):
        try:
            headers=dict(HEADERS)
            m=re.match(r"^(https?://[^/]+)",url)
            if m:
                headers["Referer"]=m.group(1)+"/"
            r=session.get(url,headers=headers,timeout=(20,70),allow_redirects=True)
            if r.status_code >= 400: raise RuntimeError(f"HTTP {r.status_code}")
            if len(r.text) < 500: raise RuntimeError(f"HTML too small: {len(r.text)}")
            return r.text
        except Exception as e:
            last=e; time.sleep(1.2*attempt)
    raise RuntimeError(str(last) if last else "page fetch failed")

def fetch_blob(session: requests.Session, url: str) -> bytes:
    last=None
    for attempt in range(1,5):
        try:
            headers=dict(IMAGE_HEADERS)
            m=re.match(r"^(https?://[^/]+)",url)
            if m:
                headers["Referer"]=m.group(1)+"/"
            r=session.get(url,headers=headers,timeout=(20,90),allow_redirects=True)
            if r.status_code >= 400: raise RuntimeError(f"HTTP {r.status_code}")
            if len(r.content) < 900: raise RuntimeError(f"image too small: {len(r.content)}")
            return r.content
        except Exception as e:
            last=e; time.sleep(1.4*attempt)
    raise RuntimeError(str(last) if last else "image download failed")

def build_page_index(page_url: str, text: str) -> dict[str,list[str]]:
    out={}
    soup=BeautifulSoup(text,"html.parser")

    # 1) Normal rendered <img alt="Weapon | Skin" src="..."> path.
    for img in soup.find_all("img"):
        alt=img.get("alt") or img.get("title") or ""
        src=best_src(img)
        if " | " in alt and src:
            out.setdefault(norm(alt),[]).append(urljoin(page_url,src))

        # Some GGSTAND pages keep weapon/skin as nearby card text rather than alt.
        # Only inspect small ancestors so we do not mix neighbouring cards.
        if src and " | " not in alt:
            node=img
            for _ in range(3):
                node=getattr(node,"parent",None)
                if not node:
                    break
                txt=" ".join(node.stripped_strings)
                txt=re.sub(r"\s+"," ",txt).strip()
                # Exact explicit "Weapon | Skin" nearby.
                mm=re.search(r'((?:StatTrack\*\s*)?[^|]{1,70})\s*\|\s*([^|]{1,100})',txt,re.I)
                if mm:
                    title=(mm.group(1).strip()+" | "+mm.group(2).strip())
                    out.setdefault(norm(title),[]).append(urljoin(page_url,src))
                    break

    # 2) Nuxt/server payload fallbacks.
    raw=htmlmod.unescape(text)
    # Normalize common JSON escaping so URLs can be matched reliably.
    raw=raw.replace("\\/","/").replace("\\u002F","/").replace("\\u002f","/")

    rel_img=r'(/public/storage/items/[^"\'\\<>\s]+)'
    abs_img=r'(https?://[^"\'\\<>\s]+/public/storage/items/[^"\'\\<>\s]+)'
    title_pat=r'["\']([^"\']{1,90}\s\|\s[^"\']{1,120})["\']'

    # title -> image (old path)
    for img_pat in (rel_img,abs_img):
        rx=re.compile(title_pat+r'[\s\S]{0,520}?'+img_pat,re.I)
        for m in rx.finditer(raw):
            title=m.group(1)
            src=m.group(2)
            out.setdefault(norm(title),[]).append(urljoin(page_url,src))

    # image -> title (important for newer/localized GGSTAND payloads)
    for img_pat in (rel_img,abs_img):
        rx=re.compile(img_pat+r'[\s\S]{0,520}?'+title_pat,re.I)
        for m in rx.finditer(raw):
            src=m.group(1)
            title=m.group(2)
            out.setdefault(norm(title),[]).append(urljoin(page_url,src))

    # 3) JSON-object proximity fallback.
    # Accept only chunks that contain exactly one public item image and an explicit
    # "Weapon | Skin" title. This stays strict and cannot fall back by skin name alone.
    chunk_rx=re.compile(r'[^{}\n]{0,700}(?:/public/storage/items/|https?://[^"\'\s]+/public/storage/items/)[^{}\n]{0,700}',re.I)
    img_rx=re.compile(r'(https?://[^"\'\\<>\s]+/public/storage/items/[^"\'\\<>\s]+|/public/storage/items/[^"\'\\<>\s]+)',re.I)
    title_rx=re.compile(r'["\']([^"\']{1,90}\s\|\s[^"\']{1,120})["\']',re.I)
    for cm in chunk_rx.finditer(raw):
        chunk=cm.group(0)
        imgs=img_rx.findall(chunk)
        titles=title_rx.findall(chunk)
        if len(imgs)==1 and len(titles)==1:
            out.setdefault(norm(titles[0]),[]).append(urljoin(page_url,imgs[0]))

    # Deduplicate while preserving page order.
    for k,vals in list(out.items()):
        seen=[]
        for v in vals:
            if v not in seen:
                seen.append(v)
        out[k]=seen
    return out

def page_candidates(item: dict) -> list[str]:
    target=item["target_title"]
    weapon=item["weapon"]
    skin=item["skin"]

    absolute_urls=[]
    for u in ABSOLUTE_PAGE_HINTS.get(target,[]):
        if u and u not in absolute_urls:
            absolute_urls.append(u)

    direct_slugs=[]
    all_slugs=[]

    def add_direct(xs):
        for x in xs:
            if x and x not in direct_slugs:
                direct_slugs.append(x)
            if x and x not in all_slugs:
                all_slugs.append(x)

    def add_all(xs):
        for x in xs:
            if x and x not in all_slugs:
                all_slugs.append(x)

    # High-value pages: exact collection/theme and weapon pages.
    add_direct(SPECIAL.get(target,[]))
    add_direct(THEME_HINTS.get(skin,[]))
    add_direct(PRIMARY.get(weapon,[]))
    add_direct(slug_variants(weapon))

    # Breakout contains several of the remaining skins.
    if target in {
        "Akimbo Uzi | No Escape",
        "P350 | Lab Prototype",
        "SPAS | Waypoint",
    }:
        add_direct(["breakout"])

    # Keep the original rarity/general fallback search on the primary host only.
    for r in item.get("rarities",[]):
        add_all([r.casefold()])
    add_all(FALLBACK)

    urls=list(absolute_urls)

    # First: normal ggstand.com direct pages.
    for slug in direct_slugs:
        u=make_page_url(slug)
        if u not in urls:
            urls.append(u)

    # Then: mirrors for only the high-value direct pages.
    for slug in direct_slugs:
        for u in mirror_page_urls(slug):
            if u not in urls:
                urls.append(u)

    # Failed-only repair is intentionally narrow and fast:
    # exact page hints + exact weapon pages/mirrors only.
    if REPAIR_FAILED_ONLY:
        return urls

    # Finally: broad fallback pages on ggstand.com only.
    for slug in all_slugs:
        u=make_page_url(slug)
        if u not in urls:
            urls.append(u)

    return urls

def has_alpha(im: Image.Image) -> tuple[bool,float]:
    rgba=im.convert("RGBA")
    hist=rgba.getchannel("A").histogram(); total=max(1,sum(hist))
    transparent=sum(hist[:250])
    return transparent>0, transparent/total

def conservative_border_cut(im: Image.Image) -> tuple[Image.Image,bool,float]:
    """Only used when source is fully opaque. Flood-fill near-uniform border colors."""
    rgba=im.convert("RGBA")
    w,h=rgba.size
    if w<8 or h<8: return rgba,False,0.0
    px=rgba.load()
    samples=[]
    for x,y in [(0,0),(w-1,0),(0,h-1),(w-1,h-1),(w//2,0),(w//2,h-1),(0,h//2),(w-1,h//2)]:
        samples.append(px[x,y][:3])
    med=tuple(sorted(v[i] for v in samples)[len(samples)//2] for i in range(3))
    def dist(c): return sum((int(c[i])-int(med[i]))**2 for i in range(3))**0.5
    # Refuse to cut when border is not reasonably uniform.
    if sum(dist(c) for c in samples)/len(samples) > 42: return rgba,False,0.0
    from collections import deque
    q=deque(); seen=set(); tol=38
    for x in range(w): q.append((x,0)); q.append((x,h-1))
    for y in range(h): q.append((0,y)); q.append((w-1,y))
    cut=0
    while q:
        x,y=q.popleft()
        if (x,y) in seen: continue
        seen.add((x,y))
        if dist(px[x,y][:3])>tol: continue
        r,g,b,a=px[x,y]; px[x,y]=(r,g,b,0); cut+=1
        if x>0:q.append((x-1,y))
        if x+1<w:q.append((x+1,y))
        if y>0:q.append((x,y-1))
        if y+1<h:q.append((x,y+1))
    ratio=cut/max(1,w*h)
    return rgba, ratio>=0.02, ratio

def validate_existing(path: Path) -> bool:
    try:
        with Image.open(path) as im:
            im.load(); ok,ratio=has_alpha(im)
            return im.width>20 and im.height>20 and ok and ratio>0.005
    except Exception:
        return False

def main() -> int:
    items=json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    overrides=json.loads(OVERRIDES.read_text(encoding="utf-8-sig")) if OVERRIDES.exists() else {}
    OUT.mkdir(parents=True,exist_ok=True)

    previous_failed_files=set()
    if REPAIR_FAILED_ONLY and FAILED.exists():
        try:
            previous_failed=json.loads(FAILED.read_text(encoding="utf-8-sig"))
            previous_failed_files={
                str(x.get("output_file","")).strip()
                for x in previous_failed
                if str(x.get("output_file","")).strip()
            }
            print(f"Failed-only repair targets loaded: {len(previous_failed_files)}")
        except Exception as e:
            print(f"WARNING: could not read previous FAILED_ITEMS.json: {e}")
            previous_failed_files=set()

    session=requests.Session()
    page_cache={}; page_errors={}

    def index_for(url):
        if url in page_cache: return page_cache[url]
        try:
            text=fetch_text(session,url)
            idx=build_page_index(url,text)
            page_cache[url]=idx
            print(f"      page indexed: {url} ({len(idx)} titles)")
            if REPAIR_FAILED_ONLY:
                interesting=[k for k in idx if any(x in k for x in ("warden","adam","hologram","contour","frequency","cyber dragon"))]
                if interesting:
                    print("      exact repair titles found:", ", ".join(interesting[:12]))
            return idx
        except Exception as e:
            page_errors[url]=str(e); page_cache[url]={}
            print(f"      page unavailable: {url} -> {e}")
            return {}

    rows=[]; resolved=[]; failures=[]
    total=len(items); ok_count=skip_count=0
    print(f"RAGECASES — MASTER SKIN FETCH ({total} canonical images)")
    print("Output: assets/ragecases_skins_v2/")
    print("StatTrack and normal appearances share one canonical image file.")
    print(f"Force redownload: {FORCE}")
    print(f"Strict repair ADD_NEW: {STRICT_REPAIR_ADD_NEW}")
    print(f"Repair previous failed only: {REPAIR_FAILED_ONLY}\n")

    for pos,item in enumerate(items,1):
        target=item["target_title"]; dest=OUT/item["output_file"]
        print(f"[{pos:03d}/{total}] {item['canonical_name']}")
        strict_repair = STRICT_REPAIR_ADD_NEW and item.get("mode") == "ADD_NEW"
        targeted_failed_repair = REPAIR_FAILED_ONLY and dest.name in previous_failed_files
        if dest.exists() and not FORCE and not strict_repair and not targeted_failed_repair and validate_existing(dest):
            ok,ratio=has_alpha(Image.open(dest))
            public=PAGES_BASE+dest.name
            resolved.append({**item,"source_url":"EXISTING_V2","source_page":"","public_url":public,"alpha_ratio":ratio,"status":"SKIPPED_VALID"})
            rows.append([pos,item['canonical_name'],item['mode'],"SKIPPED_VALID",dest.name,dest.stat().st_size,"","",f"alpha={ratio:.4%}"])
            skip_count+=1
            print("   SKIP: valid V2 file already exists")
            continue
        if strict_repair and dest.exists():
            print("   STRICT REPAIR: existing ADD_NEW image will be re-verified by exact weapon+skin match")
        if targeted_failed_repair and dest.exists():
            print("   FAILED-ONLY REPAIR: previous failed image will be re-verified by exact weapon+skin match")

        source_urls=[]; source_page=""; resolution=""
        for u in overrides.get(item['canonical_name'],[]):
            if u and u not in source_urls: source_urls.append(u)
        if source_urls: resolution="KNOWN_OVERRIDE"

        # Discover exact weapon+skin from pages.
        # In failed-only mode, a known exact override is tried immediately without crawling.
        discovered=[]
        lookup_titles=[target] + list(item.get("target_aliases",[]) or [])
        lookup_norms=[]
        for title in lookup_titles:
            nt=norm(title)
            if nt and nt not in lookup_norms:
                lookup_norms.append(nt)

        discovery_pages=[] if (REPAIR_FAILED_ONLY and source_urls) else page_candidates(item)
        for page in discovery_pages:
            idx=index_for(page)
            vals=[]
            for nt in lookup_norms:
                for u in idx.get(nt,[]):
                    if u not in vals:
                        vals.append(u)
            if vals:
                for u in vals:
                    if u not in discovered: discovered.append(u)
                if not source_page: source_page=page
                # Once a primary page yields a match, no need to scan every broad fallback.
                if len(discovered)>=2 or page in page_candidates(item)[:8]: break
        for u in discovered:
            if u not in source_urls: source_urls.append(u)
        if discovered and resolution!="KNOWN_OVERRIDE": resolution="DISCOVERED"
        elif discovered: resolution="KNOWN_OVERRIDE+DISCOVERED"

        if not source_urls:
            note=f"No exact weapon+skin image URL found for target {target}"
            removed_wrong=False
            if ((strict_repair and dest.name in KNOWN_BAD_OUTPUT_FILES) or targeted_failed_repair) and dest.exists():
                try:
                    dest.unlink()
                    removed_wrong=True
                    note += "; removed untrusted cached image after exact-match failure"
                except Exception as e:
                    note += f"; failed to remove known-wrong cached image: {e}"
            failures.append({**item,"status":"UNRESOLVED","note":note,"pages_tried":page_candidates(item),"strict_repair":strict_repair,"removed_wrong_cached":removed_wrong})
            rows.append([pos,item['canonical_name'],item['mode'],"UNRESOLVED","",0,"",source_page,note])
            print("   FAILED: UNRESOLVED")
            continue

        success=False; last=""; chosen=""; alpha_ratio=0.0; source_fmt=""; cut_note=""
        for u in source_urls:
            print(f"   trying image: {u}")
            try:
                blob=fetch_blob(session,u)
                with Image.open(io.BytesIO(blob)) as im:
                    source_fmt=(im.format or "unknown").upper(); im.load()
                    rgba=im.convert("RGBA")
                    alpha_ok,alpha_ratio=has_alpha(rgba)
                    if not alpha_ok or alpha_ratio<0.005:
                        rgba,cut_ok,cut_ratio=conservative_border_cut(rgba)
                        if cut_ok:
                            alpha_ok=True; alpha_ratio=cut_ratio; cut_note=f"; AUTO_BORDER_CUT={cut_ratio:.4%}"
                    if not alpha_ok or alpha_ratio<0.005:
                        raise RuntimeError("source has no usable transparent background")
                    tmp=dest.with_suffix(dest.suffix+".tmp")
                    rgba.save(tmp,format="WEBP",lossless=True,method=6)
                    with Image.open(tmp) as chk:
                        chk.load(); aok,aratio=has_alpha(chk)
                        if not aok or aratio<0.005: raise RuntimeError("written WebP lost alpha")
                    os.replace(tmp,dest)
                    alpha_ratio=aratio
                chosen=u; success=True; break
            except Exception as e:
                last=str(e); print(f"      failed: {e}")

        if success:
            ok_count+=1; public=PAGES_BASE+dest.name
            status="OK_"+resolution if resolution else "OK"
            note=f"source={source_fmt}; alpha={alpha_ratio:.4%}{cut_note}"
            resolved.append({**item,"source_url":chosen,"source_page":source_page,"public_url":public,"alpha_ratio":alpha_ratio,"status":status})
            rows.append([pos,item['canonical_name'],item['mode'],status,dest.name,dest.stat().st_size,chosen,source_page,note])
            print(f"   OK -> {dest.name} | {note}")
        else:
            note=last or "all image candidates failed"
            removed_untrusted=False
            if targeted_failed_repair and dest.exists():
                try:
                    dest.unlink()
                    removed_untrusted=True
                    note += "; removed untrusted cached image after failed exact-source download"
                except Exception as e:
                    note += f"; could not remove untrusted cached image: {e}"
            failures.append({**item,"status":"DOWNLOAD_FAILED","note":note,"candidate_urls":source_urls,"source_page":source_page,"targeted_failed_repair":targeted_failed_repair,"removed_untrusted_cached":removed_untrusted})
            rows.append([pos,item['canonical_name'],item['mode'],"DOWNLOAD_FAILED","",0,"",source_page,note])
            print(f"   FAILED: {note}")
        time.sleep(.15)

    with REPORT.open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["index","canonical_name","mode","status","filename","size_bytes","source_url","source_page","note"]); w.writerows(rows)
    RESOLVED.write_text(json.dumps(resolved,ensure_ascii=False,indent=2),encoding="utf-8")
    FAILED.write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding="utf-8")

    # Map every original appearance, including STATTRACK*, to the same canonical file.
    image_map={}
    for r in resolved:
        if r["status"] not in {"SKIPPED_VALID"} and not r["status"].startswith("OK"): continue
        url=r["public_url"]
        image_map[r["canonical_name"]]=url
        for a in r.get("appears_as",[]): image_map[a]=url
    MAP_JSON.write_text(json.dumps(image_map,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    MAP_JS.write_text("/* RAGECASES V2 skin image map — generated; business logic untouched */\nvar ragecasesSkinImagesV2 = "+json.dumps(image_map,ensure_ascii=False,indent=2,sort_keys=True)+";\n",encoding="utf-8")

    cards=[]
    for r in resolved:
        if not r.get("public_url"): continue
        alpha=f"{r.get('alpha_ratio',0):.2%}"
        fn=r['output_file']
        cards.append(f'<article><div class="pic"><img loading="lazy" src="{fn}" alt=""></div><b>{htmlmod.escape(r["canonical_name"])}</b><small>{fn}</small><small>alpha: {alpha}</small><small>{htmlmod.escape(r["status"])}</small></article>')
    PREVIEW.write_text(f"""<!doctype html><meta charset="utf-8"><title>RAGECASES — MASTER skin library</title><style>body{{margin:0;background:#0f0f11;color:#fff;font:14px Arial;padding:24px}}h1{{color:#ffd447}}.summary{{color:#bbb;margin-bottom:20px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}}article{{background:#101012;border:1px solid #2b2e33;border-radius:14px;padding:12px}}.pic{{height:145px;display:grid;place-items:center;border-radius:10px;background-color:#ddd;background-image:linear-gradient(45deg,#bbb 25%,transparent 25%),linear-gradient(-45deg,#bbb 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#bbb 75%),linear-gradient(-45deg,transparent 75%,#bbb 75%);background-size:20px 20px;background-position:0 0,0 10px,10px -10px,-10px 0}}.pic img{{max-width:100%;max-height:100%;object-fit:contain}}b,small{{display:block;margin-top:7px}}small{{color:#aaa}}</style><h1>RAGECASES — SKINS MASTER</h1><div class="summary">Resolved: {len(resolved)} / {total}. Failed: {len(failures)}. StatTrack uses the same canonical render.</div><div class="grid">{''.join(cards)}</div>""",encoding="utf-8")

    if failures:
        READY.unlink(missing_ok=True)
    else:
        READY.write_text(f"RAGECASES SKINS MASTER READY\nAll {total} canonical images resolved.\nThe current site has NOT been switched automatically.\nUse skin_images_map_v2.js/json for the next safe interface-only image migration.\n",encoding="utf-8")

    print("\n================ SUMMARY ================")
    print(f"Total canonical: {total}")
    print(f"Downloaded now: {ok_count}")
    print(f"Skipped valid V2: {skip_count}")
    print(f"Failed: {len(failures)}")
    print(f"Pages fetched: {len(page_cache)}")
    print(f"Report: {REPORT.relative_to(ROOT)}")
    if failures: print("FAILED_ITEMS.json contains exact unresolved items. Re-run is safe: valid V2 files are skipped.")
    else: print("ALL IMAGES READY. READY_TO_SWITCH.txt created.")
    return 0 if not failures else 2

if __name__ == "__main__":
    raise SystemExit(main())
