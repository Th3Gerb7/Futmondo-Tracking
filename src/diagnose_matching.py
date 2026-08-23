import sys
import unicodedata
from collections import Counter
from src import futmondo_api
from src.supabase_client import get_client


def _normalize(name):
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def diagnose():
    print("=== Diagnóstico de Matching (IDs vs Nombres) ===\n")

    db = get_client()

    print("[1] Login...")
    token, userid = futmondo_api.login()
    print("    OK\n")

    print("[2] Obteniendo equipos de la API...")
    teams = futmondo_api.get_teams(token, userid)
    print(f"    Total equipos: {len(teams)}")

    print("\n[3] Datos de equipos (API):")
    team_fields = Counter()
    for t in teams:
        for k in t.keys():
            team_fields[k] += 1
    print(f"    Campos: {dict(team_fields.most_common())}\n")

    teamid_to_userid = {}
    teamname_to_userid = {}
    userid_to_info = {}

    for t in teams:
        uid = t.get("userid", "")
        tid = t.get("_id", t.get("userteamId", t.get("id", "")))
        tname = t.get("teamname", "")
        uname = t.get("name", "")

        print(f"    Team: userid={uid}, team_id={tid}, teamname='{tname}', username='{uname}'")

        if tid:
            teamid_to_userid[tid] = uid
        if tname:
            teamname_to_userid[_normalize(tname)] = uid
        if uid:
            userid_to_info[uid] = {"username": uname, "teamname": tname, "team_id": tid}

    print(f"\n    Mapping team_id → userid: {len(teamid_to_userid)} entries")
    print(f"    Mapping teamname → userid: {len(teamname_to_userid)} entries")

    print("\n[4] LeagueUsers en Supabase:")
    users = db.table("LeagueUsers").select("IDUser, UserName, NameInGame").execute().data or []
    db_name_to_id = {}
    for u in users:
        print(f"    IDUser={u['IDUser']}, UserName='{u.get('UserName', '')}', NameInGame='{u.get('NameInGame', '')}'")
        name = u.get("NameInGame", "")
        if name:
            db_name_to_id[_normalize(name)] = u["IDUser"]

    print(f"\n[5] Descargando pressroom...")
    news = futmondo_api.get_pressroom(token, userid)
    print(f"    Total transacciones: {len(news)}\n")

    print("[6] Verificar matching de compradores/vendedores:")
    unmatched_buyers = []
    unmatched_sellers = []
    id_matched_buyers = 0
    id_matched_sellers = 0
    name_matched_buyers = 0
    name_matched_sellers = 0

    all_buyer_ids = set()
    all_seller_ids = set()

    for item in news:
        buyer = item.get("_buyer", {})
        seller = item.get("_seller", {})

        if buyer:
            bid = buyer.get("_id", "")
            bname = buyer.get("name", "")
            all_buyer_ids.add(bid)

            by_id = teamid_to_userid.get(bid)
            by_name = db_name_to_id.get(_normalize(bname))

            if by_id:
                id_matched_buyers += 1
            if by_name:
                name_matched_buyers += 1
            if not by_name and not by_id:
                unmatched_buyers.append({
                    "tx_id": item.get("_id"),
                    "player": item.get("_player", {}).get("name", "?"),
                    "buyer_id": bid,
                    "buyer_name": bname,
                    "price": item.get("price", 0),
                })

        if seller:
            sid = seller.get("_id", "")
            sname = seller.get("name", "")
            all_seller_ids.add(sid)

            by_id = teamid_to_userid.get(sid)
            by_name = db_name_to_id.get(_normalize(sname))

            if by_id:
                id_matched_sellers += 1
            if by_name:
                name_matched_sellers += 1
            if not by_name and not by_id:
                unmatched_sellers.append({
                    "tx_id": item.get("_id"),
                    "player": item.get("_player", {}).get("name", "?"),
                    "seller_id": sid,
                    "seller_name": sname,
                    "price": item.get("price", 0),
                })

    print(f"    Compradores: {name_matched_buyers} por nombre, {id_matched_buyers} por team_id")
    print(f"    Vendedores:  {name_matched_sellers} por nombre, {id_matched_sellers} por team_id")
    print(f"    Compradores sin match: {len(unmatched_buyers)}")
    print(f"    Vendedores sin match:  {len(unmatched_sellers)}")

    if unmatched_buyers:
        print(f"\n    COMPRADORES SIN MATCH (balance NO contabiliza la compra):")
        total_lost = 0
        for ub in unmatched_buyers[:20]:
            print(f"      {ub['player']:25s} | buyer_id={ub['buyer_id']} | name='{ub['buyer_name']}' | price={ub['price']:>12,}")
            total_lost += ub['price']
        print(f"      TOTAL no contabilizado: {total_lost:,.0f}")

    if unmatched_sellers:
        print(f"\n    VENDEDORES SIN MATCH (balance NO contabiliza la venta):")
        total_lost = 0
        for us in unmatched_sellers[:20]:
            print(f"      {us['player']:25s} | seller_id={us['seller_id']} | name='{us['seller_name']}' | price={us['price']:>12,}")
            total_lost += us['price']
        print(f"      TOTAL no contabilizado: {total_lost:,.0f}")

    print(f"\n[7] IDs únicos en pressroom:")
    print(f"    Buyer IDs únicos: {len(all_buyer_ids)}")
    print(f"    Seller IDs únicos: {len(all_seller_ids)}")
    all_ids = all_buyer_ids | all_seller_ids
    print(f"    Total IDs únicos: {len(all_ids)}")

    print(f"\n[8] Comparar IDs pressroom vs IDs equipos:")
    for pid in sorted(all_ids):
        matched_uid = teamid_to_userid.get(pid, "NO MATCH")
        names_in_pr = set()
        for item in news:
            if item.get("_buyer", {}).get("_id") == pid:
                names_in_pr.add(item["_buyer"]["name"])
            if item.get("_seller", {}).get("_id") == pid:
                names_in_pr.add(item["_seller"]["name"])
        name_match = db_name_to_id.get(_normalize(list(names_in_pr)[0])) if names_in_pr else "N/A"
        print(f"    pressroom_id={pid} → team_api={matched_uid:30s} | name_match={name_match} | names={names_in_pr}")

    print("\n=== Fin diagnóstico matching ===")


if __name__ == "__main__":
    try:
        diagnose()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
