"""One-time recovery: retry pressroom API pagination multiple times to find
transactions that fell outside the normal pagination window, then upsert them."""

import sys
import time
from src.supabase_client import get_client
from src import futmondo_api
from src.sync_pressroom import sync, _build_name_lookup, _build_teamid_lookup


def recover():
    print("=== PressRoom Recovery ===\n")

    token, userid = futmondo_api.login()
    print("[1] Login OK\n")

    teams = futmondo_api.get_teams(token, userid)
    print(f"[2] {len(teams)} equipos\n")

    db = get_client()
    db_rows = db.table("PressRoom").select("IDTransaction").execute().data or []
    db_ids = {r["IDTransaction"] for r in db_rows}
    print(f"[3] {len(db_ids)} transacciones en Supabase\n")

    all_api_items: dict[str, dict] = {}
    attempts = 10

    print(f"[4] Intentando {attempts} llamadas a la API para capturar transacciones faltantes...\n")

    for i in range(attempts):
        try:
            news = futmondo_api.get_pressroom(token, userid)
            new_found = 0
            for item in news:
                tx_id = item.get("_id")
                if tx_id and tx_id not in all_api_items:
                    all_api_items[tx_id] = item
                    if tx_id not in db_ids:
                        new_found += 1
            print(f"    Intento {i+1}: {len(news)} de API, {len(all_api_items)} únicos acumulados, {new_found} nuevos para DB")
        except Exception as e:
            print(f"    Intento {i+1}: ERROR - {e}")

        if i < attempts - 1:
            time.sleep(2)

    missing_in_db = {tid: item for tid, item in all_api_items.items() if tid not in db_ids}
    print(f"\n[5] Resumen:")
    print(f"    Total únicos encontrados en API: {len(all_api_items)}")
    print(f"    Ya en Supabase: {len(all_api_items) - len(missing_in_db)}")
    print(f"    Faltan en Supabase: {len(missing_in_db)}")

    if missing_in_db:
        print(f"\n[6] Recuperando {len(missing_in_db)} transacciones faltantes...")
        for tid, item in missing_in_db.items():
            player = item.get("_player", {}).get("name", "?")
            price = item.get("price", 0)
            print(f"    - {player}: {price:,.0f}")

        sync(list(missing_in_db.values()), teams)
        print(f"\n    Upsert completado.")
    else:
        print("\n[6] No hay transacciones nuevas que recuperar.")

    extra_in_db = db_ids - set(all_api_items.keys())
    if extra_in_db:
        print(f"\n[7] {len(extra_in_db)} transacciones en Supabase NO encontradas en API (se conservan):")
        extra_rows = db.table("PressRoom").select(
            "IDTransaction, FootballPlayer, PurchaseAmount, SalesAmount"
        ).in_("IDTransaction", list(extra_in_db)).execute().data or []
        for r in extra_rows:
            player = r.get("FootballPlayer", "?")
            amount = r.get("PurchaseAmount") or r.get("SalesAmount") or 0
            print(f"    - {player}: {amount:,.0f}")

    final_count = db.table("PressRoom").select("IDTransaction", count="exact").execute().count
    print(f"\n[8] Total final en Supabase: {final_count}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(recover())
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
