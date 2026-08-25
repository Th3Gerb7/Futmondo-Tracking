"""Cross-reference ALL users' SquadPlayers against PressRoom purchases
to detect missing transactions across the entire league."""

import sys
import unicodedata
from src.supabase_client import get_client


def _normalize(name: str | None) -> str:
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def diagnose():
    db = get_client()

    print("=== Diagnóstico COMPLETO: Transacciones faltantes para TODOS los usuarios ===\n")

    users = db.table("LeagueUsers").select("IDUser, UserName, NameInGame").execute().data or []
    print(f"[1] Usuarios en la liga: {len(users)}\n")

    all_squad = db.table("SquadPlayers").select("*").execute().data or []
    print(f"[2] Total jugadores en plantillas: {len(all_squad)}")

    all_purchases = db.table("PressRoom").select(
        "IDTransaction, FootballPlayer, IDPurchaseUser, PurchaseAmount, TransactionDate"
    ).not_.is_("IDPurchaseUser", "null").execute().data or []
    print(f"[3] Total compras en PressRoom: {len(all_purchases)}")

    all_sales = db.table("PressRoom").select(
        "IDTransaction, FootballPlayer, IDSalesUser, SalesAmount"
    ).not_.is_("IDSalesUser", "null").execute().data or []
    print(f"[4] Total ventas en PressRoom: {len(all_sales)}\n")

    purchases_by_user: dict[str, dict[str, list]] = {}
    for tx in all_purchases:
        uid = tx.get("IDPurchaseUser", "")
        if not uid:
            continue
        pname = _normalize(tx.get("FootballPlayer"))
        purchases_by_user.setdefault(uid, {}).setdefault(pname, []).append(tx)

    sales_by_user: dict[str, set[str]] = {}
    for tx in all_sales:
        uid = tx.get("IDSalesUser", "")
        if not uid:
            continue
        pname = _normalize(tx.get("FootballPlayer"))
        sales_by_user.setdefault(uid, set()).add(pname)

    squad_by_user: dict[str, list] = {}
    for p in all_squad:
        uid = p.get("IDUser", "")
        if uid:
            squad_by_user.setdefault(uid, []).append(p)

    print("=" * 100)
    total_missing = 0
    total_missing_amount = 0
    users_with_missing = []

    for user in sorted(users, key=lambda u: u.get("UserName", "")):
        uid = user["IDUser"]
        uname = user.get("UserName", "?")
        game_name = user.get("NameInGame", "?")

        squad = squad_by_user.get(uid, [])
        user_purchases = purchases_by_user.get(uid, {})
        user_sales = sales_by_user.get(uid, set())

        purchased_names = set(user_purchases.keys())

        missing = []
        for p in squad:
            pname = _normalize(p.get("PlayerName"))
            if pname and pname not in purchased_names:
                missing.append(p)

        total_purchase_amount = sum(
            tx.get("PurchaseAmount", 0) or 0
            for txs in user_purchases.values()
            for tx in txs
        )
        num_purchases = sum(len(txs) for txs in user_purchases.values())

        print(f"\n--- {uname} ({game_name}) [{uid}] ---")
        print(f"  Plantilla: {len(squad)} jugadores | Compras registradas: {num_purchases} | Total: {total_purchase_amount:,.0f}")

        if missing:
            missing_amount = sum(p.get("BuyPrice", 0) or 0 for p in missing)
            total_missing += len(missing)
            total_missing_amount += missing_amount
            users_with_missing.append((uname, len(missing), missing_amount))

            print(f"  *** FALTAN {len(missing)} compras (total: {missing_amount:,.0f}) ***")
            for p in sorted(missing, key=lambda x: -(x.get("BuyPrice") or 0)):
                name = p.get("PlayerName", "?")
                buy = p.get("BuyPrice", 0) or 0
                val = p.get("CurrentValue", 0) or 0
                sold = _normalize(name) in user_sales
                print(f"    {name:25s}  BuyPrice: {buy:>14,.0f}  CV: {val:>14,.0f}  {'(vendido y recomprado?)' if sold else ''}")
        else:
            print(f"  OK - todos los jugadores tienen compra registrada")

        sold_not_in_squad = user_sales - {_normalize(p.get("PlayerName")) for p in squad}
        bought_and_gone = purchased_names - {_normalize(p.get("PlayerName")) for p in squad}
        if bought_and_gone:
            print(f"  Comprados ya no en plantilla: {len(bought_and_gone)}")

    print(f"\n{'=' * 100}")
    print(f"\n=== RESUMEN ===")
    print(f"Total jugadores faltantes en PressRoom: {total_missing}")
    print(f"Importe total faltante: {total_missing_amount:,.0f}")

    if users_with_missing:
        print(f"\nUsuarios afectados:")
        for uname, count, amount in users_with_missing:
            print(f"  {uname:25s}  {count} compra(s) faltante(s)  importe: {amount:,.0f}")
    else:
        print("\nNingún usuario tiene compras faltantes.")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(diagnose())
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
