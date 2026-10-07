import json
import os
import subprocess
from datetime import datetime, timezone

# ============================
# PATHS (ABSOLUTE)
# ============================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHANNELS_FILE = os.path.join(BASE_DIR, "channels.txt")
OUTPUT_DIR = os.path.join(BASE_DIR, "categories")
DATA_DIR = os.path.join(BASE_DIR, "data")


CATEGORY_MAP = {
    "music": ["music", "song", "songs", "gaana"],
    "gaming": ["gaming", "game", "bgmi", "freefire"],
    "news": ["news", "khabar", "samachar"],
    "sports": ["sports", "cricket", "football"],
    "movies": ["movie", "film", "trailer"],
    "comedy": ["comedy", "funny", "meme"],
    "education": ["education", "learn", "tutorial"],
    "vlog": ["vlog", "daily"],
    "tech": ["tech", "gadget", "review"],
    "devotional": ["bhajan", "devotional", "mandir"],
    "other": [],
}


def guess_category(text: str) -> str:
    t = text.lower()
    for cat, keys in CATEGORY_MAP.items():
        for k in keys:
            if k in t:
                return cat
    return "other"


YTDLP_ARGS = [
    "yt-dlp",
    "--flat-playlist",
    "--dump-json",
    "--no-warnings",
    "--ignore-errors",
]


def fetch(query: str):
    """yt-dlp se videos fetch karo"""
    try:
        proc = subprocess.run(
            YTDLP_ARGS + [query],
            capture_output=True,
            text=True,
            timeout=240,
        )
    except subprocess.TimeoutExpired:
        print(f"[WARN] timeout: {query}")
        return []

    videos = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        vid = data.get("id")
        if not vid:
            continue

        videos.append({
            "id": vid,
            "title": data.get("title", ""),
            "url": f"https://www.youtube.com/watch?v={vid}",
            "channel": data.get("channel") or data.get("uploader") or "",
            "thumbnail": data.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "duration": data.get("duration") or 0,
            "category": "",
        })
    return videos


def dedupe(videos):
    seen = set()
    out = []
    for v in videos:
        if v["id"] in seen:
            continue
        seen.add(v["id"])
        out.append(v)
    return out


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    # ===== DEBUG: paths print karo =====
    print(f"[DEBUG] BASE_DIR: {BASE_DIR}")
    print(f"[DEBUG] CHANNELS_FILE: {CHANNELS_FILE}")
    print(f"[DEBUG] File exists: {os.path.exists(CHANNELS_FILE)}")

    # channels.txt padho
    if not os.path.exists(CHANNELS_FILE):
        print("[ERROR] channels.txt not found")
        return

    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        queries = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    print(f"[INFO] Total queries: {len(queries)}")

    # Category wise collect
    category_videos = {}

    for query in queries:
        print(f"[QUERY] {query}")
        vids = fetch(query)
        print(f"  → {len(vids)} videos")

        for v in vids:
            cat = guess_category(v["title"] + " " + v["channel"] + " " + query)
            v["category"] = cat
            category_videos.setdefault(cat, []).append(v)

    # Har category ka alag JSON banao
    manifest_categories = []

    for cat, vids in category_videos.items():
        vids = dedupe(vids)

        path = os.path.join(OUTPUT_DIR, f"{cat}.json")
        old = load_json(path)
        old_videos = old.get("videos", []) if isinstance(old, dict) else []

        existing_ids = {v["id"] for v in old_videos}
        for v in vids:
            if v["id"] not in existing_ids:
                old_videos.append(v)

        out = {
            "category": cat,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "videos": old_videos,
        }
        save_json(path, out)
        print(f"[DONE] {path} — {len(old_videos)} videos")

        manifest_categories.append({
            "name": cat,
            "file": f"{cat}.json",
            "count": len(old_videos),
        })

    # manifest.json
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": manifest_categories,
    }
    save_json(os.path.join(OUTPUT_DIR, "manifest.json"), manifest)
    print(f"[DONE] manifest.json — {len(manifest_categories)} categories")

    # Combined data/api.json
    all_videos = []
    for cat, vids in category_videos.items():
        all_videos.extend(vids)
    all_videos = dedupe(all_videos)

    combined = {
        "videos": all_videos,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_json(os.path.join(DATA_DIR, "api.json"), combined)
    print(f"[DONE] data/api.json — {len(all_videos)} total videos")


if __name__ == "__main__":
    main()
