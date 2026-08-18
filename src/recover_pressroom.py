import sys
import time
from src import futmondo_api
from src.supabase_client import get_client
from src.sync_pressroom import sync


def recover():
    print("=== Recuperación de historial PressRoom ===\n")
    db = get_client()

    existing = db.table("PressRoom").select("IDTransaction").execute().data or []
    print(f"Registros actuales en Supabase: {len(existing)}\n")

    print("[1] Login en Futmondo...")
    token, userid = futmondo_api.login()
    print("    OK\n")

    all_news = []
    seen_ids = set()
    cursor = ""
    page = 0

    while True:
        page += 1
        print(f"[2] Página {page} (from='{cursor[:20]}...' )" if cursor else f"[2] Página {page} (primera)")

        answer = futmondo_api._post("/1/locker/pressroom", token, userid, {
            "championshipId": futmondo_api.CHAMPIONSHIP_ID,
            "from": cursor,
        })
        news = answer.get("news", [])

        if not news:
            print(f"    Sin resultados. Fin de paginación.\n")
            break

        new_count = 0
        oldest_id = None
        for item in news:
            tx_id = item.get("_id")
            if tx_id and tx_id not in seen_ids:
                seen_ids.add(tx_id)
                all_news.append(item)
                new_count += 1
                oldest_id = tx_id

        print(f"    Recibidas: {len(news)} | Nuevas: {new_count} | Total acumulado: {len(all_news)}")

        if new_count == 0:
            print(f"    Todas duplicadas. Fin de paginación.\n")
            break

        if len(news) < 50:
            print(f"    Página parcial ({len(news)} < 50). Probable fin.\n")
            cursor = oldest_id or ""
            if cursor:
                time.sleep(1)
                continue
            break

        cursor = oldest_id or ""
        time.sleep(1)

    print(f"Total transacciones recuperadas de la API: {len(all_news)}")
    print(f"Registros previos en Supabase: {len(existing)}\n")

    if all_news:
        print("[3] Sincronizando todas las transacciones...")
        sync(all_news)
        print("    Hecho.\n")

        final = db.table("PressRoom").select("IDTransaction").execute().data or []
        print(f"Registros finales en Supabase: {len(final)}")
        print(f"Nuevos registros añadidos: {len(final) - len(existing)}")
    else:
        print("No se recuperaron transacciones.")


if __name__ == "__main__":
    try:
        recover()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
