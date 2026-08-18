import unicodedata
from datetime import datetime
import pytz
from src.supabase_client import get_client

MADRID = pytz.timezone("Europe/Madrid")


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFKD", s).casefold().strip()


def sync(news: list[dict]) -> None:
    db = get_client()
    now = datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S")

    users = db.table("LeagueUsers").select("IDUser, NameInGame").execute().data or []
    name_to_id: dict[str, str] = {}
    for u in users:
        name = u.get("NameInGame", "")
        if name:
            name_to_id[_normalize(name)] = u["IDUser"]

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

        norm = _normalize(team_name)
        user_id = name_to_id.get(norm)

        if not user_id:
            for db_key, uid in name_to_id.items():
                if db_key.startswith(norm) or norm.startswith(db_key):
                    user_id = uid
                    break

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
