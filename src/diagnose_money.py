"""Diagnose MoneyEvents: find missing distributions and name mismatches.

Compares ALL money events from the Futmondo API against what's stored
in Supabase, identifies unmatched names, and calculates per-user totals
to detect balance discrepancies.
"""

import sys
import unicodedata
from collections import defaultdict
from src.futmondo_api import login, get_news
from src.supabase_client import get_client


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFKD", s).casefold().strip()


def _extract_event(item: dict) -> tuple[str, int] | None:
    data = item.get("data", {})
    styp = item.get("styp", "")
    if styp == "customize":
        team_name = data.get("name", "")
        amount = data.get("money", 0)
        if team_name and amount:
            return team_name, amount
    elif styp == "bonus":
        team_name = data.get("to", "")
        amount = data.get("quantity", 0)
        if team_name and amount:
            return team_name, amount
    return None


def diagnose():
    print("=" * 90)
    print("DIAGNÓSTICO EXHAUSTIVO DE MONEY EVENTS")
    print("=" * 90)

    # 1. Get all news from API
    print("\n[1] Obteniendo news de la API (5 pasadas)...")
    token, userid = login()
    news = get_news(token, userid, passes=5)
    print(f"    Total news: {len(news)}")

    money_events_api = [n for n in news if n.get("styp") in {"customize", "bonus"}]
    print(f"    Money events en API: {len(money_events_api)}")

    # 2. Get data from Supabase
    print("\n[2] Obteniendo datos de Supabase...")
    db = get_client()
    users = db.table("LeagueUsers").select("IDUser, UserName, NameInGame").execute().data or []
    stored_events = db.table("MoneyEvents").select("*").execute().data or []
    stored_ids = {e["IDEvent"] for e in stored_events}

    print(f"    Usuarios en DB: {len(users)}")
    print(f"    MoneyEvents en DB: {len(stored_events)}")

    # Build name mappings
    name_to_id: dict[str, str] = {}
    id_to_name: dict[str, str] = {}
    for u in users:
        name = u.get("NameInGame", "")
        if name:
            name_to_id[_normalize(name)] = u["IDUser"]
        id_to_name[u["IDUser"]] = u.get("UserName", u.get("NameInGame", "???"))

    # 3. Process ALL API money events — track which matched, which didn't
    print("\n[3] Analizando TODOS los money events de la API...")

    api_totals_by_name: dict[str, int] = defaultdict(int)
    api_events_by_name: dict[str, list] = defaultdict(list)
    unmatched_names: dict[str, list] = defaultdict(list)
    matched_events = 0
    unmatched_events = 0
    already_stored = 0

    for item in money_events_api:
        event_id = item.get("_id", "")
        extracted = _extract_event(item)
        if not extracted:
            continue

        team_name, amount = extracted
        norm = _normalize(team_name)
        api_totals_by_name[team_name] += amount
        api_events_by_name[team_name].append({
            "id": event_id,
            "amount": amount,
            "date": item.get("created", ""),
            "styp": item.get("styp", ""),
            "in_db": event_id in stored_ids,
        })

        if event_id in stored_ids:
            already_stored += 1
            continue

        # Try matching
        user_id = name_to_id.get(norm)
        if not user_id:
            for db_key, uid in name_to_id.items():
                if db_key.startswith(norm) or norm.startswith(db_key):
                    user_id = uid
                    break

        if user_id:
            matched_events += 1
        else:
            unmatched_events += 1
            unmatched_names[team_name].append({
                "id": event_id,
                "amount": amount,
                "date": item.get("created", ""),
            })

    print(f"    Ya en DB: {already_stored}")
    print(f"    Nuevos con match: {matched_events}")
    print(f"    Nuevos SIN match: {unmatched_events}")

    # 4. Show ALL unique team names from API events
    print("\n" + "=" * 90)
    print("[4] TODOS LOS NOMBRES EN MONEY EVENTS DE LA API")
    print("=" * 90)

    for name in sorted(api_totals_by_name.keys()):
        norm = _normalize(name)
        uid = name_to_id.get(norm, "???")
        real_name = id_to_name.get(uid, "NO MATCH")
        events = api_events_by_name[name]
        in_db = sum(1 for e in events if e["in_db"])
        not_in_db = sum(1 for e in events if not e["in_db"])
        total = api_totals_by_name[name]
        match_status = "OK" if uid != "???" else "*** SIN MATCH ***"
        print(f"\n  [{match_status}] \"{name}\"")
        print(f"      → Usuario: {real_name} ({uid})")
        print(f"      → {len(events)} eventos, total: {total:>15,} | en DB: {in_db}, faltantes: {not_in_db}")
        if not_in_db > 0:
            for e in events:
                if not e["in_db"]:
                    print(f"        FALTA: {e['id']} | {e['amount']:>12,} | {e['date']}")

    # 5. Show unmatched names detail
    if unmatched_names:
        print("\n" + "=" * 90)
        print("[5] NOMBRES SIN MATCH — DETALLE")
        print("=" * 90)
        for name, events in sorted(unmatched_names.items()):
            total = sum(e["amount"] for e in events)
            print(f"\n  \"{name}\" — {len(events)} eventos, total: {total:>12,}")
            norm = _normalize(name)
            print(f"    Normalizado: \"{norm}\"")
            # Try to find similar names in DB
            print(f"    Nombres en DB similares:")
            for db_name_norm, uid in name_to_id.items():
                # Check if they share a significant substring
                if any(word in db_name_norm for word in norm.split() if len(word) > 3):
                    real = id_to_name.get(uid, "???")
                    print(f"      → \"{real}\" (norm: \"{db_name_norm}\") — {uid}")
            for e in events:
                print(f"    {e['id']} | {e['amount']:>12,} | {e['date']}")

    # 6. Per-user balance comparison
    print("\n" + "=" * 90)
    print("[6] BALANCE DE MONEY EVENTS POR USUARIO (DB vs esperado)")
    print("=" * 90)

    # Calculate totals from what's in the DB
    db_totals: dict[str, int] = defaultdict(int)
    db_counts: dict[str, int] = defaultdict(int)
    for e in stored_events:
        uid = e.get("IDUser", "")
        amt = e.get("Amount", 0) or 0
        db_totals[uid] += amt
        db_counts[uid] += 1

    # Calculate expected totals from API (only for matched names)
    api_totals_by_uid: dict[str, int] = defaultdict(int)
    api_counts_by_uid: dict[str, int] = defaultdict(int)
    for name, events in api_events_by_name.items():
        norm = _normalize(name)
        uid = name_to_id.get(norm)
        if not uid:
            for db_key, u in name_to_id.items():
                if db_key.startswith(norm) or norm.startswith(db_key):
                    uid = u
                    break
        if uid:
            for e in events:
                api_totals_by_uid[uid] += e["amount"]
                api_counts_by_uid[uid] += 1

    for u in sorted(users, key=lambda x: x.get("UserName", "")):
        uid = u["IDUser"]
        name = u.get("UserName", "???")
        game_name = u.get("NameInGame", "???")
        db_total = db_totals.get(uid, 0)
        db_count = db_counts.get(uid, 0)
        api_total = api_totals_by_uid.get(uid, 0)
        api_count = api_counts_by_uid.get(uid, 0)
        diff = api_total - db_total

        status = "OK" if abs(diff) < 1 else f"*** DIFF: {diff:>+12,} ***"
        print(f"\n  {name:30s} ({game_name})")
        print(f"    DB:  {db_count:3d} eventos → {db_total:>15,}")
        print(f"    API: {api_count:3d} eventos → {api_total:>15,}")
        print(f"    {status}")

    # 7. Search specifically for "martin" or similar
    print("\n" + "=" * 90)
    print("[7] BÚSQUEDA ESPECÍFICA DE 'MARTÍN' EN TODOS LOS DATOS")
    print("=" * 90)

    martin_search = ["martin", "martín", "martn"]
    for name in sorted(api_totals_by_name.keys()):
        if any(m in name.lower() for m in martin_search):
            print(f"\n  ENCONTRADO en API events: \"{name}\"")
            for e in api_events_by_name[name]:
                db_status = "EN DB" if e["in_db"] else "FALTA"
                print(f"    [{db_status}] {e['id']} | {e['amount']:>12,} | {e['date']} | {e['styp']}")

    for u in users:
        if any(m in (u.get("UserName", "") + u.get("NameInGame", "")).lower() for m in martin_search):
            uid = u["IDUser"]
            print(f"\n  ENCONTRADO en LeagueUsers: {u['UserName']} / \"{u['NameInGame']}\" ({uid})")
            my_events = [e for e in stored_events if e.get("IDUser") == uid]
            print(f"    MoneyEvents en DB: {len(my_events)}")
            for e in sorted(my_events, key=lambda x: x.get("EventDate", "")):
                print(f"      {e['IDEvent']} | {e.get('Amount', 0):>12,} | {e.get('EventDate', '')} | {e.get('Description', '')[:80]}")

    print("\n\n=== DIAGNÓSTICO COMPLETADO ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(diagnose())
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
