import unicodedata
from datetime import datetime
import pytz
from src.supabase_client import get_client

MADRID = pytz.timezone("Europe/Madrid")


def _normalize(name: str | None) -> str:
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _build_user_lookup(users: list[dict]) -> dict[str, str]:
    return {_normalize(u["NameInGame"]): u["IDUser"] for u in users if u.get("NameInGame")}


def _find_user(lookup: dict[str, str], name: str) -> str | None:
    key = _normalize(name)
    if not key:
        return None
    if key in lookup:
        return lookup[key]
    for db_key, uid in lookup.items():
        if db_key.startswith(key):
            return uid
    return None


def sync(news: list[dict]) -> None:
    db = get_client()
    now = datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S")

    users = db.table("LeagueUsers").select("IDUser, NameInGame").execute().data or []
    lookup = _build_user_lookup(users)

    customize = [n for n in news if n.get("styp") == "customize"]

    api_ids = set()
    rows = []
    unmatched = []

    for item in customize:
        event_id = item.get("_id")
        if not event_id:
            continue

        api_ids.add(event_id)

        data = item.get("data", {})
        team_name = data.get("name", "")
        amount = data.get("money", 0)
        user_id = _find_user(lookup, team_name)

        if not user_id:
            unmatched.append(team_name)
            continue

        rows.append({
            "IDEvent": event_id,
            "EventDate": item.get("created"),
            "IDUser": user_id,
            "Amount": amount,
            "EventType": "customize",
            "Description": item.get("txt", ""),
            "UpdatedAt": now,
        })

    if rows:
        db.table("MoneyEvents").upsert(rows).execute()

    existing = db.table("MoneyEvents").select("IDEvent").execute().data or []
    db_ids = {r["IDEvent"] for r in existing}
    removed = db_ids - api_ids
    if removed:
        db.table("MoneyEvents").delete().in_("IDEvent", list(removed)).execute()

    print(f"{len(rows)} upserted, {len(removed)} eliminados", end="")
    if unmatched:
        unique = sorted(set(unmatched))
        print(f" ({len(unmatched)} sin match: {', '.join(unique)})", end="")
    print()
