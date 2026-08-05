from datetime import datetime
import pytz
from src.supabase_client import get_client

MADRID = pytz.timezone("Europe/Madrid")


def sync(teams: list[dict]) -> None:
    db = get_client()
    now = datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S")

    api_ids = set()
    rows = []

    for team in teams:
        user_id = team.get("userid")
        if not user_id or team.get("teamValue") is None:
            continue

        api_ids.add(user_id)
        rows.append({
            "IDUser": user_id,
            "UserName": team.get("name"),
            "NameInGame": team.get("teamname"),
            "ActualValueTeam": team.get("teamValue"),
            "UpdatedAt": now,
        })

    if rows:
        db.table("LeagueUsers").upsert(rows).execute()

    existing = db.table("LeagueUsers").select("IDUser").execute().data or []
    db_ids = {r["IDUser"] for r in existing}
    removed = db_ids - api_ids

    if removed:
        db.table("LeagueUsers").delete().in_("IDUser", list(removed)).execute()

    print(f"{len(rows)} upserted, {len(removed)} eliminados")
