import sys
import json
from src import futmondo_api
from src.config import CHAMPIONSHIP_ID


def try_endpoint(token, userid, path, query, label):
    print(f"\n--- {label} ---")
    print(f"    POST {path}")
    print(f"    Query: {json.dumps(query, ensure_ascii=False)}")
    try:
        body = {
            "header": {"token": token, "userid": userid},
            "query": query,
            "answer": {},
        }
        resp = futmondo_api._get_session().post(
            f"{futmondo_api.BASE_URL}{path}", json=body, timeout=15
        )
        print(f"    Status: {resp.status_code}")
        data = resp.json()
        answer = data.get("answer", {})

        if isinstance(answer, dict) and answer.get("error"):
            print(f"    Error: {answer.get('code', 'unknown')}")
            return

        if isinstance(answer, list):
            print(f"    Respuesta: lista con {len(answer)} elementos")
            if answer:
                print(f"    Primer elemento keys: {list(answer[0].keys()) if isinstance(answer[0], dict) else type(answer[0])}")
                for item in answer[:3]:
                    print(f"    → {json.dumps(item, ensure_ascii=False, default=str)[:200]}")
        elif isinstance(answer, dict):
            print(f"    Keys: {list(answer.keys())}")
            for key, val in answer.items():
                if isinstance(val, list):
                    print(f"    {key}: lista con {len(val)} elementos")
                    if val and isinstance(val[0], dict):
                        print(f"      Keys: {list(val[0].keys())}")
                        for item in val[:3]:
                            print(f"      → {json.dumps(item, ensure_ascii=False, default=str)[:200]}")
                elif isinstance(val, dict):
                    print(f"    {key}: {json.dumps(val, ensure_ascii=False, default=str)[:150]}")
                else:
                    print(f"    {key}: {val}")
        else:
            print(f"    Respuesta: {str(answer)[:300]}")

    except Exception as e:
        print(f"    Exception: {e}")


def explore():
    print("=== Exploración API Futmondo ===\n")

    print("[1] Login...")
    token, userid = futmondo_api.login()
    print(f"    OK (userid: {userid})\n")

    # Endpoints to try for money events / lockerroom / news
    endpoints = [
        ("/1/locker/news", {"championshipId": CHAMPIONSHIP_ID, "from": ""}, "Locker News"),
        ("/1/locker/lockerroom", {"championshipId": CHAMPIONSHIP_ID, "from": ""}, "Locker Room"),
        ("/1/locker/lockerroom", {"championshipId": CHAMPIONSHIP_ID}, "Locker Room (sin from)"),
        ("/2/locker/news", {"championshipId": CHAMPIONSHIP_ID, "from": ""}, "Locker News v2"),
        ("/2/locker/lockerroom", {"championshipId": CHAMPIONSHIP_ID, "from": ""}, "Locker Room v2"),
        ("/1/championship/news", {"championshipId": CHAMPIONSHIP_ID}, "Championship News"),
        ("/2/championship/news", {"championshipId": CHAMPIONSHIP_ID}, "Championship News v2"),
        ("/1/championship/lockerroom", {"championshipId": CHAMPIONSHIP_ID}, "Championship Lockerroom"),
        ("/1/locker/money", {"championshipId": CHAMPIONSHIP_ID}, "Locker Money"),
        ("/1/locker/events", {"championshipId": CHAMPIONSHIP_ID}, "Locker Events"),
        ("/1/championship/events", {"championshipId": CHAMPIONSHIP_ID}, "Championship Events"),
        ("/1/championship/history", {"championshipId": CHAMPIONSHIP_ID}, "Championship History"),
        ("/1/locker/history", {"championshipId": CHAMPIONSHIP_ID, "from": ""}, "Locker History"),
        ("/5/locker/news", {"championshipId": CHAMPIONSHIP_ID, "from": ""}, "Locker News v5"),
        ("/1/locker/wall", {"championshipId": CHAMPIONSHIP_ID, "from": ""}, "Locker Wall"),
        ("/2/locker/wall", {"championshipId": CHAMPIONSHIP_ID, "from": ""}, "Locker Wall v2"),
    ]

    for path, query, label in endpoints:
        try_endpoint(token, userid, path, query, label)

    # Also re-check pressroom for money-related entries
    print("\n\n--- Revisando pressroom por entradas de dinero ---")
    news = futmondo_api.get_pressroom(token, userid)
    money_related = [n for n in news if any(
        k in str(n).lower() for k in ["money", "reparto", "prize", "reward", "bonus", "income", "9000000", "9.000.000"]
    )]
    print(f"Entradas con keywords de dinero: {len(money_related)}")
    for item in money_related[:5]:
        print(f"  → {json.dumps(item, ensure_ascii=False, default=str)[:250]}")


if __name__ == "__main__":
    try:
        explore()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
