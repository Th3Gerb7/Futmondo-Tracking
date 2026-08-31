import unicodedata
from datetime import datetime
import pytz
from src.supabase_client import get_client

MADRID = pytz.timezone("Europe/Madrid")

MONEY_STYPS = {"customize", "bonus"}


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFKD", s).casefold().strip()


HISTORICAL_NAMES: dict[str, str] = {
    _normalize("\U0001f468\U0001f3fb‍✈️IL CONSTRUTORE WL"): "5a60ebbc7f21925d0b1b70d6",  # Marc Galvez
    _normalize("Ivan burkiewicz"): "684b04144e95775f1fce5faa",  # Ivan burkiewicz
}


def _extract_event(item: dict) -> tuple[str, int] | None:
    """Extract (team_name, amount) from a money event regardless of styp."""
    data = item.get("data", {})
    styp = item.get("styp", "")

    if styp == "customize":
        team_name = data.get("name", "")
        amount = data.get("money", 0)
        if team_name and amount:
            return team_name, amount
    elif styp == "bonus":
        team_name = data.get("to", "")
        amount = data.get("quantity", 0)
        if team_name and amount:
            return team_name, amount

    return None


def sync(news: list[dict]) -> None:
    db = get_client()
    now = datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S")

    users = db.table("LeagueUsers").select("IDUser, NameInGame").execute().data or []
    name_to_id: dict[str, str] = {}
    for u in users:
        name = u.get("NameInGame", "")
        if name:
            name_to_id[_normalize(name)] = u["IDUser"]

    money_events = [n for n in news if n.get("styp") in MONEY_STYPS]

    existing = db.table("MoneyEvents").select("IDEvent").execute().data or []
    existing_ids = {r["IDEvent"] for r in existing}

    rows = []
    unmatched = []

    for item in money_events:
        event_id = item.get("_id")
        if not event_id or event_id in existing_ids:
            continue

        extracted = _extract_event(item)
        if not extracted:
            continue
        team_name, amount = extracted

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
            "EventType": item.get("styp", "unknown"),
            "Description": item.get("txt", ""),
            "UpdatedAt": now,
        })

    if rows:
        db.table("MoneyEvents").insert(rows).execute()

    print(f"{len(rows)} nuevos, {len(existing_ids)} en BD", end="")
    if unmatched:
        unique = sorted(set(unmatched))
        print(f" ({len(unmatched)} sin match: {', '.join(unique)})", end="")
    print()
