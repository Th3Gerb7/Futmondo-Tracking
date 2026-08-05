import sys
import time
from datetime import datetime
import pytz
from src import futmondo_api, sync_teams, sync_pressroom
from src.supabase_client import get_client

MADRID = pytz.timezone("Europe/Madrid")


def _step(label: str):
    print(f"  [{label}] ", end="", flush=True)


def run():
    t0 = time.monotonic()
    print(f"=== Futmondo Sync - {datetime.now(MADRID).strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    _step("1/4 Login")
    token, userid = futmondo_api.login()
    print("OK")

    _step("2/4 Token > Supabase")
    db = get_client()
    db.table("AccessToken").upsert({
        "ID": "futmondo_session",
        "AccessToken": token,
        "UpdatedAt": datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S"),
    }).execute()
    print("OK")

    _step("3/4 Equipos")
    teams = futmondo_api.get_teams(token, userid)
    sync_teams.sync(teams)

    _step("4/4 Transacciones")
    news = futmondo_api.get_pressroom(token, userid)
    sync_pressroom.sync(news)

    elapsed = time.monotonic() - t0
    print(f"\n=== Completado en {elapsed:.1f}s ===")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"\nERROR FATAL: {e}", file=sys.stderr)
        sys.exit(1)
