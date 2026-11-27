import json
import os
import time
import urllib.request
from datetime import datetime, timezone

CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
CLIENT_SECRET = os.environ["TWITCH_CLIENT_SECRET"]

def get_access_token():
    url = f"https://id.twitch.tv/oauth2/token?client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&grant_type=client_credentials"
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())["access_token"]

def fetch_igdb_releases(token):
    now_ts = int(time.time())
    end_ts = now_ts + (90 * 24 * 60 * 60)  # Next 90 days

    query = f"""
    fields game.id, game.name, game.summary, game.hypes,
           game.cover.image_id, game.genres.name,
           game.screenshots.image_id,
           game.involved_companies.company.name,
           game.involved_companies.developer,
           game.involved_companies.publisher,
           date, platform;
    where platform = (167, 48) & date >= {now_ts} & date <= {end_ts};
    sort date asc;
    limit 250;
    """

    req = urllib.request.Request(
        "https://api.igdb.com/v4/release_dates",
        data=query.encode("utf-8"),
        headers={
            "Client-ID": CLIENT_ID,
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def build_clean_json(raw_items):
    games_map = {}
    for item in raw_items:
        game = item.get("game")
        ts = item.get("date")
        plat_id = item.get("platform")
        if not game or not ts:
            continue

        gid = game["id"]
        plat_name = "PS5" if plat_id == 167 else "PS4"
        release_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

        if gid not in games_map:
            cover_id = (game.get("cover") or {}).get("image_id")
            cover_url = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{cover_id}.jpg" if cover_id else None

            screenshots = [
                f"https://images.igdb.com/igdb/image/upload/t_screenshot_med/{s['image_id']}.jpg"
                for s in (game.get("screenshots") or [])[:4]
                if s.get("image_id")
            ]

            developers, publishers = [], []
            for ic in game.get("involved_companies") or []:
                cname = (ic.get("company") or {}).get("name")
                if not cname:
                    continue
                if ic.get("developer"):
                    developers.append(cname)
                if ic.get("publisher"):
                    publishers.append(cname)

            hypes = game.get("hypes") or 0
            games_map[gid] = {
                "id": gid,
                "title": game.get("name", "Unknown"),
                "releaseDate": release_date,
                "releaseTimestamp": ts,
                "platforms": [plat_name],
                "coverUrl": cover_url,
                "summary": game.get("summary") or "",
                "genres": [g["name"] for g in (game.get("genres") or [])],
                "developers": developers,
                "publishers": publishers,
                "screenshots": screenshots,
                "hypes": hypes,
                "isMajor": hypes >= 10,
            }
        else:
            if plat_name not in games_map[gid]["platforms"]:
                games_map[gid]["platforms"].append(plat_name)
            if release_date < games_map[gid]["releaseDate"]:
                games_map[gid]["releaseDate"] = release_date
                games_map[gid]["releaseTimestamp"] = ts

    sorted_games = sorted(games_map.values(), key=lambda x: (x["releaseDate"], -x["hypes"]))
    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(sorted_games),
        "releases": sorted_games,
    }

if __name__ == "__main__":
    token = get_access_token()
    raw = fetch_igdb_releases(token)
    output = build_clean_json(raw)
    with open("releases.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Saved {output['count']} games to releases.json")
