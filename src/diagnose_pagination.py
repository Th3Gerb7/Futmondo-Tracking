import sys
import json
from src import futmondo_api
from src.config import CHAMPIONSHIP_ID


def diagnose():
    print("=== Diagnóstico de Paginación Pressroom ===\n")

    print("[1] Login...")
    token, userid = futmondo_api.login()
    print("    OK\n")

    session = futmondo_api._get_session()

    for version in ("1", "2"):
        path = f"/{version}/locker/pressroom"
        print(f"\n[{version}] Probando {path}...")

        all_items = []
        seen_ids = set()
        cursor = ""
        page = 0

        while True:
            page += 1
            body = {
                "header": {"token": token, "userid": userid},
                "query": {
                    "championshipId": CHAMPIONSHIP_ID,
                    "from": cursor,
                },
                "answer": {},
            }
            try:
                resp = session.post(f"https://api.futmondo.com{path}", json=body, timeout=30)
                if resp.status_code != 200:
                    print(f"    Page {page}: HTTP {resp.status_code}")
                    break

                data = resp.json()
                answer = data.get("answer", {})

                if answer.get("error"):
                    print(f"    Page {page}: API error = {answer.get('code')}")
                    break

                news = answer.get("news", [])
                extra_keys = [k for k in answer.keys() if k not in ("news", "error", "code")]
                if extra_keys and page == 1:
                    print(f"    Extra keys in answer: {extra_keys}")
                    for k in extra_keys:
                        v = answer[k]
                        if isinstance(v, (int, float, str, bool)):
                            print(f"      {k} = {v}")

                if not news:
                    print(f"    Page {page}: empty (0 items) → DONE")
                    break

                new_count = 0
                first_id = news[0].get("_id", "")
                last_id = news[-1].get("_id", "")
                first_date = news[0].get("created", "?")
                last_date = news[-1].get("created", "?")

                for item in news:
                    tx_id = item.get("_id", "")
                    if tx_id and tx_id not in seen_ids:
                        seen_ids.add(tx_id)
                        all_items.append(item)
                        new_count += 1

                print(f"    Page {page}: {len(news)} items in response, {new_count} new | "
                      f"first={first_id[:12]}.. ({first_date[:10]}) | "
                      f"last={last_id[:12]}.. ({last_date[:10]}) | "
                      f"total so far: {len(all_items)}")

                if new_count == 0:
                    print(f"    → All duplicates, stopping")
                    break

                cursor = last_id

                if page > 50:
                    print(f"    → Safety limit reached")
                    break

            except Exception as e:
                print(f"    Page {page}: EXCEPTION {e}")
                break

        print(f"\n    TOTAL {path}: {len(all_items)} transacciones únicas")

        if all_items:
            dates = [item.get("created", "") for item in all_items if item.get("created")]
            dates.sort()
            print(f"    Fecha más antigua: {dates[0][:10] if dates else '?'}")
            print(f"    Fecha más reciente: {dates[-1][:10] if dates else '?'}")

            from collections import Counter
            by_buyer = Counter()
            by_seller = Counter()
            for item in all_items:
                b = item.get("_buyer", {}).get("name", "")
                s = item.get("_seller", {}).get("name", "")
                if b:
                    by_buyer[b] += 1
                if s:
                    by_seller[s] += 1

            print(f"\n    Compras por usuario:")
            for name, count in by_buyer.most_common():
                print(f"      {name:40s}: {count}")
            print(f"\n    Ventas por usuario:")
            for name, count in by_seller.most_common():
                print(f"      {name:40s}: {count}")

    print("\n[3] Comparar con lo que tenemos en el sync actual...")
    current = futmondo_api.get_pressroom(token, userid)
    print(f"    get_pressroom() actual devuelve: {len(current)} transacciones")

    print("\n=== Fin diagnóstico paginación ===")


if __name__ == "__main__":
    try:
        diagnose()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
