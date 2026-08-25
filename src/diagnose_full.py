"""Full diagnostic: compare API transactions vs Supabase by ID.

1. PressRoom: fetch ALL transactions from API (multi-pass), compare IDs vs DB
2. MoneyEvents: fetch ALL news from API, filter customize events, compare IDs vs DB
3. Report missing in both directions + auto-recover missing from API
"""

import sys
import time
from src.supabase_client import get_client
from src import futmondo_api
from src.sync_pressroom import sync as sync_pressroom, _build_teamid_lookup


def diagnose():
    db = get_client()

    print("=" * 100)
    print("=== DIAGNÓSTICO COMPLETO POR IDs: API vs Supabase ===")
    print("=" * 100)

    # --- Login and get teams ---
    token, userid = futmondo_api.login()
    print(f"\n[1] Login OK")

    teams = futmondo_api.get_teams(token, userid)
    print(f"[2] {len(teams)} equipos en la liga")

    # =========================================================
    # PART A: PressRoom
    # =========================================================
    print(f"\n{'=' * 100}")
    print("PARTE A: PressRoom (transacciones de mercado)")
    print(f"{'=' * 100}")

    # Fetch from API with extra passes for maximum coverage
    print(f"\n[A1] Descargando transacciones de la API (5 pasadas)...")
    api_pressroom = futmondo_api.get_pressroom(token, userid, passes=5)
    api_pr_by_id = {item.get("_id"): item for item in api_pressroom if item.get("_id")}
    print(f"     Total único en API: {len(api_pr_by_id)}")

    # Fetch from Supabase
    db_pr = db.table("PressRoom").select(
        "IDTransaction, FootballPlayer, IDPurchaseUser, IDSalesUser, "
        "PurchaseAmount, SalesAmount, TransactionType, TransactionDate"
    ).execute().data or []
    db_pr_by_id = {r["IDTransaction"]: r for r in db_pr}
    print(f"[A2] Total en Supabase: {len(db_pr_by_id)}")

    # Compare
    api_ids = set(api_pr_by_id.keys())
    db_ids = set(db_pr_by_id.keys())

    in_api_not_db = api_ids - db_ids
    in_db_not_api = db_ids - api_ids
    in_both = api_ids & db_ids

    print(f"\n[A3] Comparación por ID:")
    print(f"     En ambos:              {len(in_both)}")
    print(f"     En API pero NO en DB:  {len(in_api_not_db)}")
    print(f"     En DB pero NO en API:  {len(in_db_not_api)}")

    if in_api_not_db:
        print(f"\n[A4] *** FALTAN EN SUPABASE (se van a insertar): ***")
        missing_items = []
        for tx_id in sorted(in_api_not_db):
            item = api_pr_by_id[tx_id]
            player = item.get("_player", {}).get("name", "?")
            price = item.get("price", 0)
            buyer = item.get("_buyer", {}).get("name", "?")
            seller = item.get("_seller", {}).get("name", "?")
            date = (item.get("created") or "?")[:10]
            print(f"     {tx_id} | {date} | {player:25s} | {price:>14,.0f} | {buyer} → {seller}")
            missing_items.append(item)

        print(f"\n     Insertando {len(missing_items)} transacciones faltantes...")
        sync_pressroom(missing_items, teams)
        print(f"     Upsert completado.")
    else:
        print(f"\n[A4] OK - No faltan transacciones de la API en Supabase")

    if in_db_not_api:
        print(f"\n[A5] En DB pero NO encontradas en API ({len(in_db_not_api)}):")
        print(f"     (Se conservan — pueden ser recuperaciones manuales o transacciones antiguas)")
        for tx_id in sorted(in_db_not_api):
            r = db_pr_by_id[tx_id]
            player = r.get("FootballPlayer", "?")
            amount = r.get("PurchaseAmount") or r.get("SalesAmount") or 0
            tx_type = r.get("TransactionType", "?")
            date = (r.get("TransactionDate") or "?")[:10]
            print(f"     {tx_id} | {date} | {player:25s} | {amount:>14,.0f} | {tx_type}")
    else:
        print(f"\n[A5] OK - No hay transacciones extra en DB")

    # =========================================================
    # PART B: MoneyEvents
    # =========================================================
    print(f"\n{'=' * 100}")
    print("PARTE B: MoneyEvents (repartos de dinero)")
    print(f"{'=' * 100}")

    print(f"\n[B1] Descargando news de la API...")
    api_news = futmondo_api.get_news(token, userid)
    api_customize = [n for n in api_news if n.get("styp") == "customize"]
    api_me_by_id = {item.get("_id"): item for item in api_customize if item.get("_id")}
    print(f"     Total news en API: {len(api_news)}")
    print(f"     Money events (customize) en API: {len(api_me_by_id)}")

    # Fetch from Supabase
    db_me = db.table("MoneyEvents").select(
        "IDEvent, IDUser, Amount, Description, EventDate"
    ).execute().data or []
    db_me_by_id = {r["IDEvent"]: r for r in db_me}
    print(f"[B2] MoneyEvents en Supabase: {len(db_me_by_id)}")

    # Compare
    api_me_ids = set(api_me_by_id.keys())
    db_me_ids = set(db_me_by_id.keys())

    me_in_api_not_db = api_me_ids - db_me_ids
    me_in_db_not_api = db_me_ids - api_me_ids
    me_in_both = api_me_ids & db_me_ids

    print(f"\n[B3] Comparación por ID:")
    print(f"     En ambos:              {len(me_in_both)}")
    print(f"     En API pero NO en DB:  {len(me_in_api_not_db)}")
    print(f"     En DB pero NO en API:  {len(me_in_db_not_api)}")

    if me_in_api_not_db:
        print(f"\n[B4] *** MONEY EVENTS FALTAN EN SUPABASE: ***")
        for event_id in sorted(me_in_api_not_db):
            item = api_me_by_id[event_id]
            data = item.get("data", {})
            team_name = data.get("name", "?")
            amount = data.get("money", 0)
            txt = item.get("txt", "?")
            date = (item.get("created") or "?")[:10]
            print(f"     {event_id} | {date} | {team_name:25s} | {amount:>14,.0f} | {txt}")
    else:
        print(f"\n[B4] OK - No faltan MoneyEvents de la API en Supabase")

    if me_in_db_not_api:
        print(f"\n[B5] MoneyEvents en DB pero NO en API ({len(me_in_db_not_api)}):")
        for event_id in sorted(me_in_db_not_api):
            r = db_me_by_id[event_id]
            user_id = r.get("IDUser", "?")
            amount = r.get("Amount", 0)
            desc = r.get("Description", "?")[:50]
            date = (r.get("EventDate") or "?")[:10]
            print(f"     {event_id} | {date} | {user_id} | {amount:>14,.0f} | {desc}")
    else:
        print(f"\n[B5] OK - No hay MoneyEvents extra en DB")

    # =========================================================
    # PART C: Per-user balance summary
    # =========================================================
    print(f"\n{'=' * 100}")
    print("PARTE C: Resumen de balances por usuario (post-corrección)")
    print(f"{'=' * 100}")

    # Re-fetch after potential inserts
    all_pr = db.table("PressRoom").select(
        "IDTransaction, IDPurchaseUser, IDSalesUser, PurchaseAmount, SalesAmount"
    ).execute().data or []

    all_me = db.table("MoneyEvents").select("IDUser, Amount").execute().data or []

    users = db.table("LeagueUsers").select("IDUser, UserName, NameInGame").execute().data or []

    purchases_by_user: dict[str, float] = {}
    sales_by_user: dict[str, float] = {}
    purchase_count: dict[str, int] = {}
    sales_count: dict[str, int] = {}

    for tx in all_pr:
        buyer = tx.get("IDPurchaseUser")
        seller = tx.get("IDSalesUser")
        if buyer:
            purchases_by_user[buyer] = purchases_by_user.get(buyer, 0) + (tx.get("PurchaseAmount") or 0)
            purchase_count[buyer] = purchase_count.get(buyer, 0) + 1
        if seller:
            sales_by_user[seller] = sales_by_user.get(seller, 0) + (tx.get("SalesAmount") or 0)
            sales_count[seller] = sales_count.get(seller, 0) + 1

    money_by_user: dict[str, float] = {}
    money_count: dict[str, int] = {}
    for me in all_me:
        uid = me.get("IDUser")
        if uid:
            money_by_user[uid] = money_by_user.get(uid, 0) + (me.get("Amount") or 0)
            money_count[uid] = money_count.get(uid, 0) + 1

    print(f"\n{'Usuario':25s} | {'Compras':>8s} | {'Ventas':>8s} | {'Money':>8s} | {'Balance':>15s}")
    print("-" * 80)

    for user in sorted(users, key=lambda u: u.get("UserName", "")):
        uid = user["IDUser"]
        uname = user.get("UserName", "?")
        p = purchases_by_user.get(uid, 0)
        s = sales_by_user.get(uid, 0)
        m = money_by_user.get(uid, 0)
        pc = purchase_count.get(uid, 0)
        sc = sales_count.get(uid, 0)
        mc = money_count.get(uid, 0)
        balance = 200_000_000 + p + s + m
        print(f"{uname:25s} | {pc:>8d} | {sc:>8d} | {mc:>8d} | {balance:>15,.0f}")

    print(f"\nTotal PressRoom: {len(all_pr)} transacciones")
    print(f"Total MoneyEvents: {len(all_me)} eventos")

    # =========================================================
    # SUMMARY
    # =========================================================
    print(f"\n{'=' * 100}")
    print("=== RESUMEN FINAL ===")
    print(f"{'=' * 100}")
    print(f"PressRoom: {len(in_api_not_db)} faltaban en DB (insertados), {len(in_db_not_api)} solo en DB")
    print(f"MoneyEvents: {len(me_in_api_not_db)} faltan en DB, {len(me_in_db_not_api)} solo en DB")

    if in_api_not_db or me_in_api_not_db:
        print("\n*** SE ENCONTRARON Y CORRIGIERON DISCREPANCIAS ***")
        return 1
    else:
        print("\nTodo OK - API y Supabase están sincronizados.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(diagnose())
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
