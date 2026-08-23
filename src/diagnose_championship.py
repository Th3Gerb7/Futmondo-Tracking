import sys
import json
import requests
from src import futmondo_api
from src.config import CHAMPIONSHIP_ID


def diagnose():
    print("=== Diagnóstico de Championship Config ===\n")

    print("[1] Login...")
    token, userid = futmondo_api.login()
    print("    OK\n")

    session = futmondo_api._get_session()

    endpoints = [
        ("/2/championship/info", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/championship/info", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/championship/settings", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/championship/settings", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/championship/config", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/championship/detail", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/championship/detail", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/championship/get", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/championship/league", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/locker/info", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/locker/info", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/locker/balance", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/userteam/info", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/userteam/info", {"championshipId": CHAMPIONSHIP_ID, "userteamId": ""}),
    ]

    for path, query in endpoints:
        body = {
            "header": {"token": token, "userid": userid},
            "query": query,
            "answer": {},
        }
        try:
            resp = session.post(f"https://api.futmondo.com{path}", json=body, timeout=10)
            answer = resp.json().get("answer", {})
            error = answer.get("error")
            code = answer.get("code", "")
            if error:
                print(f"  {path:45s} → ERROR code={code}")
            else:
                safe = json.dumps(answer, indent=2, ensure_ascii=False, default=str)
                if len(safe) > 2000:
                    safe = safe[:2000] + "\n  ... (truncated)"
                print(f"  {path:45s} → OK")
                print(f"  {safe}\n")
        except Exception as e:
            print(f"  {path:45s} → EXCEPTION: {e}")

    print("\n[2] Buscar campos de presupuesto en championship/teams...")
    teams = futmondo_api.get_teams(token, userid)
    if teams:
        t = teams[0]
        print(f"    Todas las claves del primer equipo: {sorted(t.keys())}")
        for key in sorted(t.keys()):
            val = t[key]
            if isinstance(val, (int, float)) and val > 1000000:
                print(f"    {key} = {val:,.0f}")

    print("\n[3] Buscar balance en userteam endpoint...")
    for t in teams[:2]:
        tid = t.get("id", t.get("teamid", ""))
        name = t.get("name", "?")
        try:
            body = {
                "header": {"token": token, "userid": userid},
                "query": {
                    "userteamId": tid,
                    "championshipId": CHAMPIONSHIP_ID,
                },
                "answer": {},
            }
            resp = session.post("https://api.futmondo.com/2/userteam/get", json=body, timeout=10)
            answer = resp.json().get("answer", {})
            if answer.get("error"):
                print(f"    {name}: ERROR {answer.get('code')}")
            else:
                for k, v in answer.items():
                    if isinstance(v, (int, float)) and v > 100000:
                        print(f"    {name}: {k} = {v:,.0f}")
                    elif isinstance(v, dict):
                        for sk, sv in v.items():
                            if isinstance(sv, (int, float)) and sv > 100000:
                                print(f"    {name}: {k}.{sk} = {sv:,.0f}")
        except Exception as e:
            print(f"    {name}: EXCEPTION {e}")

    print("\n=== Fin diagnóstico championship ===")


if __name__ == "__main__":
    try:
        diagnose()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
