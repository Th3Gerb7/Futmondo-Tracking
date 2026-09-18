"""Explore Futmondo API for bid/offer data — Phase 2.

Focused on finding cancelled/rejected bids, specifically a Vinicius bid.
Examines pressroom bids field, probes notification/activity endpoints,
and searches for player-specific offer data.
"""

import sys
import json
import time
from src.futmondo_api import login, get_teams, get_pressroom, _post
from src.config import CHAMPIONSHIP_ID


def explore():
    token, userid = login()
    print(f"[OK] Login: userid={userid}\n")

    teams = get_teams(token, userid)
    my_team = next((t for t in teams if t.get("userid") == userid), None)
    my_team_id = my_team.get("teamid") or my_team.get("_id") if my_team else None
    print(f"[OK] Mi equipo: {my_team.get('teamname')} (team_id={my_team_id})")

    # =========================================================
    # 1. Scan ALL pressroom for items with non-empty "bids"
    # =========================================================
    print("\n" + "=" * 80)
    print("1. PRESSROOM COMPLETA — buscar transacciones con bids no vacíos")
    print("=" * 80)

    all_pr = get_pressroom(token, userid, passes=3)
    print(f"\nTotal transacciones pressroom: {len(all_pr)}")

    bids_found = 0
    vinicius_items = []
    for item in all_pr:
        bids = item.get("bids", [])
        player_name = item.get("_player", {}).get("name", "")

        if bids:
            bids_found += 1
            print(f"\n  [BIDS!] {player_name} — {len(bids)} pujas")
            print(f"    {json.dumps(item, indent=2, ensure_ascii=False)[:2000]}")

        if "vinic" in player_name.lower() or "vini" in player_name.lower():
            vinicius_items.append(item)

    print(f"\nResumen: {bids_found} transacciones con bids de {len(all_pr)} total")

    if vinicius_items:
        print(f"\n  [VINICIUS] Encontrado en {len(vinicius_items)} transacción(es):")
        for v in vinicius_items:
            print(f"    {json.dumps(v, indent=2, ensure_ascii=False)[:2000]}")
    else:
        print("\n  [VINICIUS] No encontrado en pressroom (la puja cancelada no generó transacción)")

    # =========================================================
    # 2. Probe notification/activity endpoints
    # =========================================================
    print("\n" + "=" * 80)
    print("2. PROBING — endpoints de notificaciones/actividad/pujas")
    print("=" * 80)

    probe_configs = [
        # Notifications
        ("/1/locker/notifications", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/locker/notifications", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/notifications/list", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/user/notifications", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/user/activity", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/user/activity", {"championshipId": CHAMPIONSHIP_ID}),
        # Locker activity
        ("/1/locker/activity", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/locker/activity", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/locker/history", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/locker/history", {"championshipId": CHAMPIONSHIP_ID}),
        # Bids/offers specific
        ("/1/locker/bids", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/locker/bids", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/locker/offers", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/locker/offers", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/locker/negotiations", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/locker/negotiations", {"championshipId": CHAMPIONSHIP_ID}),
        # Market with team context
        ("/1/market/mybids", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/market/myoffers", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/market/pending", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/market/history", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/market/history", {"championshipId": CHAMPIONSHIP_ID}),
        # Userteam bids
        ("/1/userteam/bids", {"championshipId": CHAMPIONSHIP_ID, "userteamId": my_team_id}),
        ("/2/userteam/bids", {"championshipId": CHAMPIONSHIP_ID, "userteamId": my_team_id}),
        ("/1/userteam/offers", {"championshipId": CHAMPIONSHIP_ID, "userteamId": my_team_id}),
        ("/2/userteam/offers", {"championshipId": CHAMPIONSHIP_ID, "userteamId": my_team_id}),
        ("/1/userteam/activity", {"championshipId": CHAMPIONSHIP_ID, "userteamId": my_team_id}),
        ("/1/userteam/history", {"championshipId": CHAMPIONSHIP_ID, "userteamId": my_team_id}),
        # Championship offers
        ("/1/championship/offers", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/championship/offers", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/championship/bids", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/championship/negotiations", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/championship/activity", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/championship/market", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/championship/market", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/championship/history", {"championshipId": CHAMPIONSHIP_ID}),
        # Player-specific
        ("/1/player/bids", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/player/offers", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/player/market", {"championshipId": CHAMPIONSHIP_ID}),
        # Transfer-specific
        ("/1/transfer/pending", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/transfer/history", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/transfer/bids", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/transfer/offers", {"championshipId": CHAMPIONSHIP_ID}),
        # Clauses (seen in team object)
        ("/1/locker/clauses", {"championshipId": CHAMPIONSHIP_ID}),
        ("/2/locker/clauses", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/userteam/clauses", {"championshipId": CHAMPIONSHIP_ID, "userteamId": my_team_id}),
        # Wallet/balance history
        ("/1/locker/wallet", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/locker/balance", {"championshipId": CHAMPIONSHIP_ID}),
        ("/1/userteam/wallet", {"championshipId": CHAMPIONSHIP_ID, "userteamId": my_team_id}),
    ]

    for path, query in probe_configs:
        try:
            answer = _post(path, token, userid, query)
            answer_str = json.dumps(answer, indent=2, ensure_ascii=False)
            keys = sorted(answer.keys()) if isinstance(answer, dict) else type(answer).__name__
            print(f"\n  [HIT!] {path}")
            print(f"    Keys: {keys}")
            print(f"    Response: {answer_str[:3000]}")
        except Exception:
            pass

    # =========================================================
    # 3. Search Vinicius in roster to get player ID
    # =========================================================
    print("\n" + "=" * 80)
    print("3. BUSCAR VINICIUS EN ROSTERS")
    print("=" * 80)

    from src.futmondo_api import get_roster
    vini_player_id = None

    for team in teams:
        team_id = team.get("teamid") or team.get("_id", "")
        if not team_id:
            continue
        try:
            roster = get_roster(token, userid, team_id)
            for player in roster:
                pname = (player.get("name") or "").lower()
                if "vinic" in pname or "vini" in pname:
                    print(f"\n  [FOUND] {player.get('name')} en {team.get('teamname')}")
                    print(f"    Player ID: {player.get('id')}")
                    print(f"    Completo: {json.dumps(player, indent=2, ensure_ascii=False)[:1500]}")
                    vini_player_id = player.get("id")
        except Exception as e:
            print(f"  Error roster {team.get('teamname')}: {e}")
        time.sleep(0.5)

    # =========================================================
    # 4. If we found Vinicius player ID, probe player-specific endpoints
    # =========================================================
    if vini_player_id:
        print("\n" + "=" * 80)
        print(f"4. PROBING ENDPOINTS ESPECÍFICOS DE VINICIUS (id={vini_player_id})")
        print("=" * 80)

        player_probes = [
            ("/1/player/info", {"playerId": vini_player_id, "championshipId": CHAMPIONSHIP_ID}),
            ("/2/player/info", {"playerId": vini_player_id, "championshipId": CHAMPIONSHIP_ID}),
            ("/1/player/detail", {"playerId": vini_player_id, "championshipId": CHAMPIONSHIP_ID}),
            ("/2/player/detail", {"playerId": vini_player_id, "championshipId": CHAMPIONSHIP_ID}),
            ("/1/player/market", {"playerId": vini_player_id, "championshipId": CHAMPIONSHIP_ID}),
            ("/1/player/offers", {"playerId": vini_player_id, "championshipId": CHAMPIONSHIP_ID}),
            ("/1/player/bids", {"playerId": vini_player_id, "championshipId": CHAMPIONSHIP_ID}),
            ("/1/player/history", {"playerId": vini_player_id, "championshipId": CHAMPIONSHIP_ID}),
            ("/1/player/stats", {"playerId": vini_player_id, "championshipId": CHAMPIONSHIP_ID}),
            ("/2/player/stats", {"playerId": vini_player_id, "championshipId": CHAMPIONSHIP_ID}),
        ]

        for path, query in player_probes:
            try:
                answer = _post(path, token, userid, query)
                answer_str = json.dumps(answer, indent=2, ensure_ascii=False)
                keys = sorted(answer.keys()) if isinstance(answer, dict) else type(answer).__name__
                print(f"\n  [HIT!] {path}")
                print(f"    Keys: {keys}")
                has_vini = "vinic" in answer_str.lower() or "vini" in answer_str.lower()
                has_bid = "bid" in answer_str.lower() or "offer" in answer_str.lower() or "puja" in answer_str.lower()
                if has_bid:
                    print(f"    *** CONTIENE DATOS DE PUJAS ***")
                print(f"    Response: {answer_str[:5000]}")
            except Exception:
                pass

    print("\n\n=== EXPLORACIÓN FASE 2 COMPLETADA ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(explore())
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
