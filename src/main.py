import sys
from datetime import datetime
import pytz
from src import futmondo_api, sync_teams, sync_pressroom
from src.supabase_client import get_client


def run():
    madrid = pytz.timezone("Europe/Madrid")
    print(f"=== Futmondo Sync - {datetime.now(madrid).strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    print("[1/4] Login en Futmondo...")
    token, userid = futmondo_api.login()
    print("  OK\n")

    print("[2/4] Guardando token en Supabase...")
    db = get_client()
    now = datetime.now(madrid).strftime("%Y-%m-%d %H:%M:%S")
    db.table("AccessToken").upsert({
        "ID": "futmondo_session",
        "AccessToken": token,
        "UpdatedAt": now,
    }).execute()
    print("  OK\n")

    print("[3/4] Sincronizando equipos...")
    teams = futmondo_api.get_teams(token, userid)
    sync_teams.sync(teams)
    print()

    print("[4/4] Sincronizando transacciones...")
    news = futmondo_api.get_pressroom(token, userid)
    sync_pressroom.sync(news)
    print()

    print("=== Sync completado ===")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"\nERROR FATAL: {e}", file=sys.stderr)
        sys.exit(1)
