"""Explore Futmondo API — Phase 3: Platform Offers.

Futmondo makes automated buy offers TO users for their players.
Users can accept (sale appears in pressroom) or reject (no record).
This script probes for where rejected/pending platform offers are stored.
"""

import sys
import json
import time
import requests
from src.futmondo_api import login, get_teams, get_roster, _post, _get_session, BASE_URL
from src.config import CHAMPIONSHIP_ID


def raw_post(path, token, userid, query):
    """POST that returns the FULL response JSON, not just answer."""
    body = {
        "header": {"token": token, "userid": userid},
        "query": query,
        "answer": {},
    }
    resp = _get_session().post(f"{BASE_URL}{path}", json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def probe(label, path, token, userid, query, show_full=False):
    """Try an endpoint and print results if it responds."""
    try:
        full = raw_post(path, token, userid, query)
        answer = full.get("answer", {})

        if isinstance(answer, dict) and answer.get("error"):
            return None

        answer_str = json.dumps(answer, indent=2, ensure_ascii=False)
        if isinstance(answer, dict):
            keys = sorted(answer.keys())
        elif isinstance(answer, list):
            keys = f"list[{len(answer)}]"
        else:
            keys = type(answer).__name__

        has_content = False
        if isinstance(answer, list) and len(answer) > 0:
            has_content = True
        elif isinstance(answer, dict):
            for k, v in answer.items():
                if isinstance(v, list) and len(v) > 0:
                    has_content = True
                    break
                if isinstance(v, dict) and len(v) > 0:
                    has_content = True
                    break

        if has_content or show_full:
            print(f"\n  [HIT!] {label}: {path}")
            print(f"    Keys: {keys}")
            print(f"    Response: {answer_str[:5000]}")
            if show_full:
                full_str = json.dumps(full, indent=2, ensure_ascii=False)
                print(f"    FULL: {full_str[:3000]}")
            return answer
        else:
            print(f"  [empty] {label}: {path} -> {keys}")
            return answer
    except Exception as e:
        print(f"  [ERR] {label}: {path} -> {e}")
        return None


def explore():
    token, userid = login()
    print(f"[OK] Login: userid={userid}\n")

    teams = get_teams(token, userid)
    my_team = next((t for t in teams if t.get("userid") == userid), None)
    my_team_id = my_team.get("teamid") or my_team.get("_id") if my_team else None
    print(f"[OK] Mi equipo: {my_team.get('teamname')} (team_id={my_team_id})")

    # Get my roster to have player IDs
    print("\n--- Mi plantilla ---")
    roster = get_roster(token, userid, my_team_id)
    print(f"Jugadores en plantilla: {len(roster)}")
    player_ids = []
    for p in roster[:5]:
        pid = p.get("id", "")
        pname = p.get("name", "")
        print(f"  {pname} (id={pid})")
        player_ids.append(pid)

    # Also show full team object for clues
    print("\n--- Team object completo ---")
    print(json.dumps(my_team, indent=2, ensure_ascii=False)[:3000])

    # =========================================================
    # 1. Offer/clause endpoints — different API version prefixes
    # =========================================================
    print("\n" + "=" * 80)
    print("1. OFERTAS DE PLATAFORMA — endpoints de ofertas/cláusulas")
    print("=" * 80)

    for ver in ["1", "2", "3", "4", "5"]:
        for path_suffix in [
            "locker/offers",
            "locker/clauses",
            "locker/negotiations",
            "locker/pendingoffers",
            "locker/rejectedoffers",
            "locker/myoffers",
            "locker/offersreceived",
            "locker/offersent",
            "locker/market",
            "market/offers",
            "market/pending",
            "market/received",
            "market/rejected",
            "market/myoffers",
            "market/negotiations",
            "market/clauses",
            "offer/list",
            "offer/pending",
            "offer/received",
            "offer/rejected",
            "offer/history",
            "offers/list",
            "offers/pending",
            "offers/received",
            "clause/list",
            "clause/pending",
            "clause/active",
            "clauses/list",
            "negotiation/list",
            "negotiations/list",
        ]:
            probe(
                f"v{ver}",
                f"/{ver}/{path_suffix}",
                token, userid,
                {"championshipId": CHAMPIONSHIP_ID},
            )

    # =========================================================
    # 2. Userteam-specific offer endpoints
    # =========================================================
    print("\n" + "=" * 80)
    print("2. OFERTAS POR USERTEAM")
    print("=" * 80)

    for ver in ["1", "2", "3"]:
        for path_suffix in [
            "userteam/offers",
            "userteam/clauses",
            "userteam/negotiations",
            "userteam/pendingoffers",
            "userteam/rejectedoffers",
            "userteam/offersreceived",
            "userteam/market",
            "userteam/offersent",
        ]:
            probe(
                f"v{ver} userteam",
                f"/{ver}/{path_suffix}",
                token, userid,
                {"championshipId": CHAMPIONSHIP_ID, "userteamId": my_team_id},
            )

    # =========================================================
    # 3. Championship-level offer endpoints
    # =========================================================
    print("\n" + "=" * 80)
    print("3. OFERTAS A NIVEL CHAMPIONSHIP")
    print("=" * 80)

    for ver in ["1", "2", "3"]:
        for path_suffix in [
            "championship/offers",
            "championship/clauses",
            "championship/negotiations",
            "championship/market",
            "championship/pendingoffers",
            "championship/offerslist",
        ]:
            probe(
                f"v{ver} champ",
                f"/{ver}/{path_suffix}",
                token, userid,
                {"championshipId": CHAMPIONSHIP_ID},
            )

    # =========================================================
    # 4. Player-specific offer endpoints (using first 3 players)
    # =========================================================
    print("\n" + "=" * 80)
    print("4. OFERTAS POR JUGADOR (primeros 3 de mi plantilla)")
    print("=" * 80)

    for pid in player_ids[:3]:
        pname = next((p.get("name") for p in roster if p.get("id") == pid), pid)
        print(f"\n  --- Jugador: {pname} (id={pid}) ---")
        for ver in ["1", "2"]:
            for path_suffix in [
                "player/offers",
                "player/clauses",
                "player/negotiations",
                "player/market",
                "player/detail",
                "player/info",
                "player/history",
            ]:
                result = probe(
                    f"v{ver} player {pname[:15]}",
                    f"/{ver}/{path_suffix}",
                    token, userid,
                    {"championshipId": CHAMPIONSHIP_ID, "playerId": pid},
                    show_full=(path_suffix in ["player/detail", "player/info"]),
                )
        time.sleep(0.3)

    # =========================================================
    # 5. Try GET endpoints (some APIs use GET not POST)
    # =========================================================
    print("\n" + "=" * 80)
    print("5. ENDPOINTS GET (por si algunas rutas son GET)")
    print("=" * 80)

    get_paths = [
        f"/1/locker/offers?championshipId={CHAMPIONSHIP_ID}",
        f"/1/market/offers?championshipId={CHAMPIONSHIP_ID}",
        f"/1/offer/list?championshipId={CHAMPIONSHIP_ID}",
        f"/2/locker/offers?championshipId={CHAMPIONSHIP_ID}",
        f"/1/locker/clauses?championshipId={CHAMPIONSHIP_ID}",
        f"/1/userteam/offers?userteamId={my_team_id}&championshipId={CHAMPIONSHIP_ID}",
    ]

    for gpath in get_paths:
        try:
            resp = _get_session().get(f"{BASE_URL}{gpath}", timeout=15)
            status = resp.status_code
            body = resp.text[:2000]
            if status == 200:
                print(f"\n  [GET HIT!] {gpath}")
                print(f"    Status: {status}")
                print(f"    Body: {body}")
            else:
                print(f"  [GET {status}] {gpath}")
        except Exception as e:
            print(f"  [GET ERR] {gpath} -> {e}")

    # =========================================================
    # 6. Inspect pressroom transaction structure for offer fields
    # =========================================================
    print("\n" + "=" * 80)
    print("6. ESTRUCTURA DE TRANSACCIONES — buscar campos de ofertas")
    print("=" * 80)

    from src.futmondo_api import get_pressroom
    pr = get_pressroom(token, userid, passes=1)
    print(f"Total transacciones: {len(pr)}")

    all_keys = set()
    offer_related = []
    for item in pr:
        all_keys.update(item.keys())
        typ = item.get("type", "")
        styp = item.get("styp", "")
        if any(k in str(item).lower() for k in ["offer", "oferta", "clause", "reject", "cancel", "rechaz"]):
            offer_related.append(item)

    print(f"\nTodas las keys encontradas en transacciones:")
    for k in sorted(all_keys):
        print(f"  - {k}")

    types_found = set()
    styps_found = set()
    for item in pr:
        if "type" in item:
            types_found.add(str(item["type"]))
        if "styp" in item:
            styps_found.add(str(item["styp"]))

    print(f"\nTypes: {sorted(types_found)}")
    print(f"Styps: {sorted(styps_found)}")

    if offer_related:
        print(f"\nTransacciones con mención de 'offer/clause/reject':")
        for item in offer_related[:5]:
            print(f"  {json.dumps(item, indent=2, ensure_ascii=False)[:2000]}")

    # =========================================================
    # 7. Full news scan — look for offer/rejection subtypes
    # =========================================================
    print("\n" + "=" * 80)
    print("7. NEWS COMPLETAS — buscar subtipos de ofertas/rechazos")
    print("=" * 80)

    from src.futmondo_api import get_news
    news = get_news(token, userid, passes=1)
    print(f"Total news: {len(news)}")

    news_all_keys = set()
    news_styps = {}
    news_types = {}
    offer_news = []

    for item in news:
        news_all_keys.update(item.keys())
        styp = item.get("styp", "unknown")
        typ = item.get("type", "unknown")
        news_styps[styp] = news_styps.get(styp, 0) + 1
        news_types[typ] = news_types.get(typ, 0) + 1

        item_str = json.dumps(item, ensure_ascii=False).lower()
        if any(k in item_str for k in ["offer", "oferta", "clause", "reject", "rechaz", "negoci"]):
            offer_news.append(item)

    print(f"\nKeys en news: {sorted(news_all_keys)}")
    print(f"Styps: {json.dumps(news_styps, indent=2)}")
    print(f"Types: {json.dumps(news_types, indent=2)}")

    if offer_news:
        print(f"\nNews con mención de ofertas/rechazos ({len(offer_news)}):")
        for item in offer_news[:5]:
            print(f"  {json.dumps(item, indent=2, ensure_ascii=False)[:2000]}")

    # Show a sample of each styp
    print("\n--- Ejemplo de cada styp ---")
    seen_styps = set()
    for item in news:
        styp = item.get("styp", "unknown")
        if styp not in seen_styps:
            seen_styps.add(styp)
            print(f"\n  [{styp}]:")
            print(f"    {json.dumps(item, indent=2, ensure_ascii=False)[:1500]}")

    # =========================================================
    # 8. Try alternate body structures (some APIs need different format)
    # =========================================================
    print("\n" + "=" * 80)
    print("8. BODY STRUCTURES ALTERNATIVAS")
    print("=" * 80)

    alt_queries = [
        ("with teamId", {"championshipId": CHAMPIONSHIP_ID, "teamId": my_team_id}),
        ("with team_id", {"championshipId": CHAMPIONSHIP_ID, "team_id": my_team_id}),
        ("with userId", {"championshipId": CHAMPIONSHIP_ID, "userId": userid}),
        ("with user_id", {"championshipId": CHAMPIONSHIP_ID, "user_id": userid}),
        ("with type=offer", {"championshipId": CHAMPIONSHIP_ID, "type": "offer"}),
        ("with type=clause", {"championshipId": CHAMPIONSHIP_ID, "type": "clause"}),
        ("with status=rejected", {"championshipId": CHAMPIONSHIP_ID, "status": "rejected"}),
        ("with status=pending", {"championshipId": CHAMPIONSHIP_ID, "status": "pending"}),
        ("with filter=offers", {"championshipId": CHAMPIONSHIP_ID, "filter": "offers"}),
        ("with section=offers", {"championshipId": CHAMPIONSHIP_ID, "section": "offers"}),
    ]

    for label, query in alt_queries:
        for path in ["/1/locker/pressroom", "/2/locker/pressroom",
                     "/1/locker/news", "/2/locker/news",
                     "/1/locker/market", "/2/locker/market"]:
            probe(f"{label}", path, token, userid, query)

    # =========================================================
    # 9. Try v3/v4/v5 of core endpoints
    # =========================================================
    print("\n" + "=" * 80)
    print("9. VERSIONES SUPERIORES DE ENDPOINTS CORE")
    print("=" * 80)

    for ver in ["3", "4", "5"]:
        for path_suffix in [
            "locker/pressroom",
            "locker/news",
            "locker/market",
            "championship/teams",
            "championship/market",
            "championship/info",
            "user/info",
            "user/dashboard",
            "user/market",
        ]:
            probe(
                f"v{ver}",
                f"/{ver}/{path_suffix}",
                token, userid,
                {"championshipId": CHAMPIONSHIP_ID},
            )

    print("\n\n=== EXPLORACIÓN FASE 3 COMPLETADA ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(explore())
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
