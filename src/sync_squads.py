from datetime import datetime
import pytz
from src.supabase_client import get_client
from src import futmondo_api

MADRID = pytz.timezone("Europe/Madrid")


def sync(token: str, userid: str, teams: list[dict]) -> None:
    db = get_client()
    now = datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S")

    all_rows = []
    fetched_users: set[str] = set()
    for team in teams:
        user_id = team.get("userid")
        team_id = team.get("teamid")
        if not user_id or not team_id:
            continue

        try:
            roster = futmondo_api.get_roster(token, userid, team_id)
        except Exception as e:
            print(f"    WARN roster {team.get('name')}: {e}")
            continue

        fetched_users.add(user_id)
        for p in roster:
            all_rows.append({
                "IDUser": user_id,
                "PlayerId": p.get("id", ""),
                "PlayerName": p.get("name"),
                "Position": p.get("role"),
                "RealTeam": p.get("team"),
                "CurrentValue": p.get("value", 0),
                "BuyPrice": p.get("buyPrice", 0),
                "UpdatedAt": now,
            })

    if all_rows:
        db.table("SquadPlayers").upsert(all_rows).execute()

    existing = db.table("SquadPlayers").select("IDUser,PlayerId").execute().data or []
    current_keys = {(r["IDUser"], r["PlayerId"]) for r in all_rows}
    to_delete = [
        r for r in existing
        if r["IDUser"] in fetched_users
        and (r["IDUser"], r["PlayerId"]) not in current_keys
    ]

    for r in to_delete:
        db.table("SquadPlayers").delete().eq(
            "IDUser", r["IDUser"]
        ).eq("PlayerId", r["PlayerId"]).execute()

    skipped = len(teams) - len(fetched_users)
    msg = f"{len(all_rows)} jugadores upserted, {len(to_delete)} eliminados"
    if skipped:
        msg += f" ({skipped} equipos sin respuesta, preservados)"
    print(msg)
