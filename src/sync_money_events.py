from datetime import datetime
import pytz
from src.supabase_client import get_client

MADRID = pytz.timezone("Europe/Madrid")


def sync(news: list[dict]) -> None:
    db = get_client()
    now = datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S")

    known_ids = {
        u["IDUser"]
        for u in (db.table("LeagueUsers").select("IDUser").execute().data or [])
    }

    customize = [n for n in news if n.get("styp") == "customize"]

    if customize:
        sample = customize[0]
        raw_sample = sample.get("u")
        print(f"  [DEBUG] Total customize events: {len(customize)}")
        print(f"  [DEBUG] known_ids: {known_ids}")
        print(f"  [DEBUG] Sample u field: {raw_sample}")
        print(f"  [DEBUG] Sample u type: {type(raw_sample).__name__}")
        if isinstance(raw_sample, dict):
            print(f"  [DEBUG] u keys: {list(raw_sample.keys())}")

    api_ids = set()
    rows = []
    unmatched = []

    for item in customize:
        event_id = item.get("_id")
        if not event_id:
            continue

        api_ids.add(event_id)

        data = item.get("data", {})
        raw_u = item.get("u")
        if isinstance(raw_u, dict):
            user_id = raw_u.get("userid") or raw_u.get("_id") or raw_u.get("id")
        else:
            user_id = raw_u
        amount = data.get("money", 0)
        team_name = data.get("name", "")

        if not user_id or user_id not in known_ids:
            unmatched.append(f"{team_name} (u={user_id})")
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
        result = db.table("MoneyEvents").upsert(rows).execute()
        print(f"  [DEBUG] Upsert result count: {len(result.data) if result.data else 0}")

    after = db.table("MoneyEvents").select("IDEvent, IDUser, Amount").execute().data or []
    print(f"  [DEBUG] MoneyEvents in DB after upsert: {len(after)}")
    if after:
        for r in after[:3]:
            print(f"  [DEBUG]   {r}")

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
