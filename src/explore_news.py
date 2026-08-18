import sys
import json
from src import futmondo_api
from src.config import CHAMPIONSHIP_ID


def explore():
    print("=== Exploración detallada /2/locker/news ===\n")

    print("[1] Login...")
    token, userid = futmondo_api.login()
    print(f"    OK\n")

    answer = futmondo_api._post("/2/locker/news", token, userid, {
        "championshipId": CHAMPIONSHIP_ID,
        "from": "",
    })

    news = answer.get("news", [])
    print(f"Total elementos: {len(news)}\n")

    # Show all unique types
    types = {}
    for item in news:
        key = f"{item.get('typ', '?')}:{item.get('styp', '?')}"
        types[key] = types.get(key, 0) + 1
    print("Tipos de eventos:")
    for t, count in sorted(types.items()):
        print(f"  {t}: {count}")
    print()

    # Filter customize events (money distributions)
    customize = [n for n in news if n.get("styp") == "customize"]
    print(f"Eventos 'customize' (repartos de dinero): {len(customize)}\n")

    # Dump full structure of first 5
    print("--- Detalle completo de los primeros 5 eventos customize ---\n")
    for i, item in enumerate(customize[:5]):
        print(f"Evento {i+1}:")
        print(json.dumps(item, ensure_ascii=False, indent=2, default=str))
        print()

    # Dump ALL customize events (compact)
    print("--- Todos los eventos customize (compacto) ---\n")
    for item in customize:
        created = item.get("created", "?")
        txt = item.get("txt", "")
        data = item.get("data", {})
        u = item.get("u", "?")
        print(f"  {created[:10]} | u={u} | data={json.dumps(data, ensure_ascii=False, default=str)[:150]} | txt={txt[:120]}")

    # Check if there are more pages
    print(f"\n--- Paginación ---")
    if news:
        last_id = news[-1].get("_id", "")
        print(f"Último ID: {last_id}")
        answer2 = futmondo_api._post("/2/locker/news", token, userid, {
            "championshipId": CHAMPIONSHIP_ID,
            "from": last_id,
        })
        news2 = answer2.get("news", [])
        print(f"Página 2 con from='{last_id}': {len(news2)} elementos")
        customize2 = [n for n in news2 if n.get("styp") == "customize"]
        if customize2:
            print(f"  Customize en página 2: {len(customize2)}")
            for item in customize2[:3]:
                print(f"    {item.get('created', '?')[:10]} | {item.get('txt', '')[:120]}")


if __name__ == "__main__":
    try:
        explore()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
