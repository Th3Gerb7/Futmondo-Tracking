import sys
import unicodedata
from src import futmondo_api
from src.supabase_client import get_client

MY_USER_ID = "610386f21a3e3f2c97060c03"


def _normalize(name):
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def diagnose():
    print("=== Diagnóstico: Team ID matching vs Name matching ===\n")

    db = get_client()

    print("[1] Login...")
    token, userid = futmondo_api.login()
    print("    OK\n")

    print("[2] Obteniendo equipos de la API...")
    teams = futmondo_api.get_teams(token, userid)
    print(f"    Total equipos: {len(teams)}")

    teamid_to_userid = {}
    userid_to_name = {}
    for t in teams:
        uid = t.get("userid", "")
        tid = t.get("_id", "")
        tname = t.get("teamname", "")
        uname = t.get("name", "")
        if tid and uid:
            teamid_to_userid[tid] = uid
        if uid:
            userid_to_name[uid] = uname
        print(f"    team_id={tid[:16]}.. userid={uid[:16]}.. teamname='{tname}' username='{uname}'")

    users = db.table("LeagueUsers").select("IDUser, NameInGame").execute().data or []
    name_lookup = {_normalize(u["NameInGame"]): u["IDUser"] for u in users if u.get("NameInGame")}

    print(f"\n[3] Obteniendo pressroom...")
    news = futmondo_api.get_pressroom(token, userid)
    print(f"    Total transacciones: {len(news)}\n")

    print("[4] Comparar matching por nombre vs por team_id:")
    name_only_purchases = {}
    name_only_sales = {}
    teamid_purchases = {}
    teamid_sales = {}
    rescued = []

    for item in news:
        buyer_obj = item.get("_buyer", {})
        seller_obj = item.get("_seller", {})
        buyer_name = buyer_obj.get("name", "")
        seller_name = seller_obj.get("name", "")
        buyer_tid = buyer_obj.get("_id", "")
        seller_tid = seller_obj.get("_id", "")
        price = item.get("price", 0)
        player = item.get("_player", {}).get("name", "?")

        buyer_by_name = name_lookup.get(_normalize(buyer_name))
        buyer_by_tid = teamid_to_userid.get(buyer_tid)
        seller_by_name = name_lookup.get(_normalize(seller_name))
        seller_by_tid = teamid_to_userid.get(seller_tid)

        buyer_uid = buyer_by_name or buyer_by_tid
        seller_uid = seller_by_name or seller_by_tid

        if buyer_by_name:
            name_only_purchases[buyer_by_name] = name_only_purchases.get(buyer_by_name, 0) - price
        if seller_by_name:
            name_only_sales[seller_by_name] = name_only_sales.get(seller_by_name, 0) + price

        if buyer_uid:
            teamid_purchases[buyer_uid] = teamid_purchases.get(buyer_uid, 0) - price
        if seller_uid:
            teamid_sales[seller_uid] = teamid_sales.get(seller_uid, 0) + price

        if (buyer_by_tid and not buyer_by_name) or (seller_by_tid and not seller_by_name):
            rescued.append({
                "player": player,
                "price": price,
                "buyer_name": buyer_name,
                "buyer_by_name": buyer_by_name,
                "buyer_by_tid": buyer_by_tid,
                "seller_name": seller_name,
                "seller_by_name": seller_by_name,
                "seller_by_tid": seller_by_tid,
                "date": item.get("created", "?")[:10],
            })

    money = db.table("MoneyEvents").select("IDUser, Amount").execute().data or []
    money_by_user = {}
    for m in money:
        uid = m.get("IDUser")
        if uid:
            money_by_user[uid] = money_by_user.get(uid, 0) + float(m["Amount"])

    print(f"\n{'Usuario':30s} | {'Balance(nombre)':>18s} | {'Balance(teamid)':>18s} | {'Diferencia':>12s}")
    print("-" * 95)

    all_uids = set(list(name_only_purchases.keys()) + list(name_only_sales.keys()) +
                    list(teamid_purchases.keys()) + list(teamid_sales.keys()))

    for uid in sorted(all_uids):
        name = userid_to_name.get(uid, uid[:16])
        bal_name = 200_000_000 + name_only_purchases.get(uid, 0) + name_only_sales.get(uid, 0) + money_by_user.get(uid, 0)
        bal_tid = 200_000_000 + teamid_purchases.get(uid, 0) + teamid_sales.get(uid, 0) + money_by_user.get(uid, 0)
        diff = bal_tid - bal_name
        marker = " <<<" if diff != 0 else ""
        print(f"{name:30s} | {bal_name:>18,.0f} | {bal_tid:>18,.0f} | {diff:>12,.0f}{marker}")

    if rescued:
        print(f"\n[5] Transacciones RESCATADAS por team_id ({len(rescued)} total):")
        total_rescued = 0
        for r in rescued:
            print(f"    {r['date']} | {r['player']:25s} | {r['price']:>12,} | "
                  f"buyer='{r['buyer_name']}' name_match={r['buyer_by_name'] is not None} tid_match={r['buyer_by_tid'] is not None} | "
                  f"seller='{r['seller_name']}' name_match={r['seller_by_name'] is not None} tid_match={r['seller_by_tid'] is not None}")
            total_rescued += r['price']
        print(f"\n    TOTAL valor rescatado: {total_rescued:,.0f}")
    else:
        print("\n[5] No hay transacciones rescatadas — name matching cubre todas")

    print(f"\n[6] Balance German Fdez (userid={MY_USER_ID}):")
    bal_name = 200_000_000 + name_only_purchases.get(MY_USER_ID, 0) + name_only_sales.get(MY_USER_ID, 0) + money_by_user.get(MY_USER_ID, 0)
    bal_tid = 200_000_000 + teamid_purchases.get(MY_USER_ID, 0) + teamid_sales.get(MY_USER_ID, 0) + money_by_user.get(MY_USER_ID, 0)
    print(f"    Solo nombre:   {bal_name:>15,.0f}")
    print(f"    Con team_id:   {bal_tid:>15,.0f}")
    print(f"    Diferencia:    {bal_tid - bal_name:>15,.0f}")

    print("\n=== Fin diagnóstico teamid ===")


if __name__ == "__main__":
    try:
        diagnose()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
