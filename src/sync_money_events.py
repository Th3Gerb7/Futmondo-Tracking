import unicodedata
from datetime import datetime
import pytz
from src.supabase_client import get_client

MADRID = pytz.timezone("Europe/Madrid")


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFKD", s).casefold().strip()


HISTORICAL_NAMES: dict[str, str] = {
    _normalize("\U0001f468\U0001f3fb‍✈️IL CONSTRUTORE WL"): "5a60ebbc7f21925d0b1b70d6",  # Marc Galvez
}


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

    existing = db.table("MoneyEvents").select("IDEvent").execute().data or []
    existing_ids = {r["IDEvent"] for r in existing}

    rows = []
    unmatched = []

    for item in customize:
        event_id = item.get("_id")
        if not event_id:
            continue

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
            user_id = HISTORICAL_NAMES.get(norm)

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

    new_count = sum(1 for r in rows if r["IDEvent"] not in existing_ids)
    updated = len(rows) - new_count
    parts = [f"{new_count} nuevos"]
    if updated:
        parts.append(f"{updated} verificados")
    parts.append(f"{len(existing_ids)} en BD")
    print(", ".join(parts), end="")
    if unmatched:
        unique = sorted(set(unmatched))
        print(f" ({len(unmatched)} sin match: {', '.join(unique)})", end="")
    print()
