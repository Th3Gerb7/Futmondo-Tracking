import sys
import json
from src import futmondo_api
from src.supabase_client import get_client


def diagnose():
    print("=== Diagnóstico de Balance: campos no rastreados ===\n")

    db = get_client()

    print("[1] Login...")
    token, userid = futmondo_api.login()
    print("    OK\n")

    print("[2] Obteniendo equipos de la API con TODOS los campos...")
    teams = futmondo_api.get_teams(token, userid)

    for t in teams:
        safe = {k: v for k, v in t.items() if k not in ("photo",)}
        print(f"\n  --- {t.get('name', '?')} ({t.get('teamname', '?')}) ---")
        print(f"  {json.dumps(safe, indent=4, ensure_ascii=False, default=str)}")

    print(f"\n\n[3] Campos numéricos potencialmente monetarios:")
    for t in teams:
        name = t.get("name", "?")
        teamname = t.get("teamname", "?")
        clauses = t.get("clauses", "N/A")
        awards = t.get("awards", "N/A")
        points = t.get("points", "N/A")
        team_value = t.get("teamValue", "N/A")
        cw = t.get("cw", "N/A")
        print(f"  {name:30s} | clauses={str(clauses):>12s} | awards={str(awards):>12s} | points={str(points):>8s} | teamValue={str(team_value):>15s} | cw={cw}")

    print(f"\n[4] Comparar con balance calculado en Supabase:")
    dashboard = db.table("UserDashboard").select("*").execute().data or []

    users_db = db.table("LeagueUsers").select("IDUser, UserName, NameInGame").execute().data or []
    uid_to_name = {u["IDUser"]: u["UserName"] for u in users_db}

    team_by_userid = {}
    for t in teams:
        team_by_userid[t.get("userid")] = t

    for d in sorted(dashboard, key=lambda x: x.get("Balance", 0)):
        uid = d["IDUser"]
        name = uid_to_name.get(uid, "?")
        our_balance = d.get("Balance", 0)
        team = team_by_userid.get(uid, {})
        clauses = team.get("clauses", 0)
        awards = team.get("awards", 0)

        if isinstance(clauses, (int, float)) and clauses != 0:
            adjusted = our_balance + clauses
            print(f"  {name:30s} | Balance={our_balance:>15,.0f} | clauses={clauses:>12,.0f} | awards={awards} | Balance+clauses={adjusted:>15,.0f}")
        else:
            print(f"  {name:30s} | Balance={our_balance:>15,.0f} | clauses={clauses} | awards={awards}")

    print(f"\n[5] Intentar obtener balance real de la API (si existe):")
    for t in teams:
        name = t.get("name", "?")
        money_fields = {k: v for k, v in t.items()
                        if isinstance(v, (int, float)) and k not in ("points", "lastAccess", "isAdmin", "nln")}
        print(f"  {name:30s} | {money_fields}")

    print("\n=== Fin diagnóstico balance ===")


if __name__ == "__main__":
    try:
        diagnose()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
