"""Explore Futmondo API for market/offer endpoints and bid data.

Probes various likely API paths for market operations and examines
existing news/pressroom data for offer/bid information.
"""

import sys
import json
from src.futmondo_api import login, get_teams, get_news, _post
from src.config import CHAMPIONSHIP_ID


def explore():
    token, userid = login()
    print(f"[OK] Login: userid={userid}\n")

    teams = get_teams(token, userid)
    my_team = next((t for t in teams if t.get("userid") == userid), None)
    my_team_id = my_team["_id"] if my_team else None
    print(f"[OK] Mi equipo: {my_team.get('teamname')} (team_id={my_team_id})")
    print(f"     Claves del team object: {sorted(my_team.keys()) if my_team else 'N/A'}")
    print(f"     Team completo:\n{json.dumps(my_team, indent=2, ensure_ascii=False)}\n")

    # =========================================================
    # 1. Examine news for offer/bid related subtypes
    # =========================================================
    print("=" * 80)
    print("1. ANÁLISIS DE NEWS — buscar subtipos de ofertas/pujas")
    print("=" * 80)

    all_news = get_news(token, userid)
    subtypes: dict[str, int] = {}
    for n in all_news:
        styp = n.get("styp", n.get("type", "unknown"))
        subtypes[styp] = subtypes.get(styp, 0) + 1

    print(f"\nTotal news: {len(all_news)}")
    print(f"Subtipos encontrados:")
    for styp, count in sorted(subtypes.items(), key=lambda x: -x[1]):
        print(f"  {styp:30s} → {count}")

    # Show a sample of each subtype
    shown = set()
    for n in all_news:
        styp = n.get("styp", n.get("type", "unknown"))
        if styp not in shown:
            shown.add(styp)
            print(f"\n--- Ejemplo de '{styp}' ---")
            print(json.dumps(n, indent=2, ensure_ascii=False)[:1500])

    # =========================================================
    # 2. Look for offer/bid keywords in news text
    # =========================================================
    print("\n" + "=" * 80)
    print("2. NEWS con palabras clave de ofertas/pujas")
    print("=" * 80)

    keywords = ["oferta", "offer", "bid", "puja", "rechaz", "reject", "accept", "acept", "negoci"]
    for n in all_news:
        txt = (n.get("txt", "") or "").lower()
        desc = json.dumps(n.get("data", {}), ensure_ascii=False).lower()
        combined = txt + " " + desc
        matches = [kw for kw in keywords if kw in combined]
        if matches:
            print(f"\n  Matches: {matches}")
            print(f"  {json.dumps(n, indent=2, ensure_ascii=False)[:800]}")

    # =========================================================
    # 3. Probe market/offer endpoints
    # =========================================================
    print("\n" + "=" * 80)
    print("3. PROBING ENDPOINTS DE MERCADO")
    print("=" * 80)

    probe_paths = [
        # Market endpoints
        "/1/market/list",
        "/2/market/list",
        "/1/market/offers",
        "/2/market/offers",
        "/1/market/bids",
        "/1/locker/market",
        "/2/locker/market",
        "/1/locker/offers",
        "/2/locker/offers",
        "/1/locker/bids",
        # Transfer endpoints
        "/1/transfer/list",
        "/2/transfer/list",
        "/1/transfer/offers",
        # Userteam market
        "/1/userteam/market",
        "/2/userteam/market",
        "/1/userteam/offers",
        "/1/userteam/negotiations",
        # Championship market
        "/1/championship/market",
        "/2/championship/market",
        "/1/championship/offers",
        "/2/championship/offers",
        "/1/championship/transfers",
        # Negotiation
        "/1/negotiation/list",
        "/2/negotiation/list",
        "/1/negotiations",
        # Sell/buy
        "/1/market/sell",
        "/1/market/buy",
        "/1/player/offers",
    ]

    for path in probe_paths:
        try:
            queries_to_try = [
                {"championshipId": CHAMPIONSHIP_ID},
                {"championshipId": CHAMPIONSHIP_ID, "userteamId": my_team_id},
            ]
            for q in queries_to_try:
                try:
                    answer = _post(path, token, userid, q)
                    print(f"\n  [HIT!] {path} (query: {list(q.keys())})")
                    answer_str = json.dumps(answer, indent=2, ensure_ascii=False)
                    print(f"    Keys: {sorted(answer.keys()) if isinstance(answer, dict) else type(answer)}")
                    print(f"    Response: {answer_str[:2000]}")
                    break
                except Exception:
                    continue
        except Exception as e:
            pass  # silently skip failed probes

    # =========================================================
    # 4. Check pressroom items for offer/negotiation data
    # =========================================================
    print("\n" + "=" * 80)
    print("4. PRESSROOM — estructura completa del primer item")
    print("=" * 80)

    answer = _post("/1/locker/pressroom", token, userid, {
        "championshipId": CHAMPIONSHIP_ID,
        "from": "",
    })
    pr_news = answer.get("news", [])
    if pr_news:
        print(f"\nPrimer item completo (TODAS las claves):")
        print(json.dumps(pr_news[0], indent=2, ensure_ascii=False))
        print(f"\nClaves del primer item: {sorted(pr_news[0].keys())}")

        # Check if any item has offer/negotiation related fields
        all_keys = set()
        for item in pr_news:
            all_keys.update(item.keys())
        print(f"\nTODAS las claves únicas en pressroom: {sorted(all_keys)}")

    # =========================================================
    # 5. Explore answer structure from /2/championship/teams more deeply
    # =========================================================
    print("\n" + "=" * 80)
    print("5. TEAMS — buscar campos de mercado/ofertas")
    print("=" * 80)

    if my_team:
        market_keys = [k for k in my_team.keys() if any(
            w in k.lower() for w in ["offer", "market", "sell", "buy", "bid", "negot", "trade", "transfer"]
        )]
        print(f"Claves de mercado en team object: {market_keys or 'ninguna'}")

    print("\n\n=== EXPLORACIÓN COMPLETADA ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(explore())
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
