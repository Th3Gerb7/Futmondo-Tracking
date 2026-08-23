import sys
from src.supabase_client import get_client


def diagnose():
    db = get_client()

    print("=== Desglose Balance por Usuario ===\n")

    users = db.table("LeagueUsers").select("IDUser, UserName, NameInGame").execute().data or []
    uid_name = {u["IDUser"]: u["UserName"] for u in users}

    print(f"[1] Usuarios: {len(users)}")
    for u in users:
        print(f"    {u['IDUser']} | {u['UserName']} | {u.get('NameInGame', '')}")

    txs = db.table("PressRoom").select("*").execute().data or []
    print(f"\n[2] Transacciones totales: {len(txs)}")

    money = db.table("MoneyEvents").select("*").execute().data or []
    print(f"[3] MoneyEvents totales: {len(money)}")

    print(f"\n[4] Desglose por usuario:")
    print(f"{'Usuario':35s} | {'Compras':>15s} | {'Ventas':>15s} | {'MoneyEv':>15s} | {'Balance':>15s} | {'#Compras':>8s} | {'#Ventas':>8s} | {'#Money':>6s}")
    print("-" * 140)

    for u in sorted(users, key=lambda x: x["UserName"]):
        uid = u["IDUser"]
        name = u["UserName"]

        purchases = sum(float(t["PurchaseAmount"]) for t in txs if t.get("IDPurchaseUser") == uid)
        sales = sum(float(t["SalesAmount"]) for t in txs if t.get("IDSalesUser") == uid)
        money_total = sum(float(m["Amount"]) for m in money if m.get("IDUser") == uid)

        n_purchases = sum(1 for t in txs if t.get("IDPurchaseUser") == uid)
        n_sales = sum(1 for t in txs if t.get("IDSalesUser") == uid)
        n_money = sum(1 for m in money if m.get("IDUser") == uid)

        balance = 200_000_000 + purchases + sales + money_total

        print(f"{name:35s} | {purchases:>15,.0f} | {sales:>15,.0f} | {money_total:>15,.0f} | {balance:>15,.0f} | {n_purchases:>8d} | {n_sales:>8d} | {n_money:>6d}")

    print(f"\n[5] Vista UserDashboard (lo que muestra el HTML):")
    dashboard = db.table("UserDashboard").select("*").execute().data or []
    for d in sorted(dashboard, key=lambda x: x.get("Balance", 0)):
        name = d.get("UserName", "?")
        print(f"    {name:35s} | Balance={d.get('Balance', 0):>15,.0f} | ValorEquipo={d.get('ValorEquipo', 0):>15,.0f} | PujaMaxima={d.get('PujaMaxima', 0):>15,.0f}")

    print(f"\n[6] Transacciones más caras (top 20):")
    sorted_txs = sorted(txs, key=lambda t: abs(float(t.get("PurchaseAmount", 0))), reverse=True)
    for t in sorted_txs[:20]:
        buyer = uid_name.get(t.get("IDPurchaseUser"), "?")
        seller = uid_name.get(t.get("IDSalesUser"), "?")
        print(f"    {t['FootballPlayer']:25s} | Purchase={float(t['PurchaseAmount']):>15,.0f} | Sales={float(t['SalesAmount']):>15,.0f} | Buyer={buyer:20s} | Seller={seller:20s} | Type={t['TransactionType']}")

    print(f"\n[7] MoneyEvents detalle:")
    for m in sorted(money, key=lambda x: x.get("EventDate", "")):
        name = uid_name.get(m.get("IDUser"), "?")
        print(f"    {name:35s} | Amount={float(m['Amount']):>12,.0f} | Date={m.get('EventDate', '?')[:10]} | {m.get('Description', '')[:60]}")

    print("\n=== Fin desglose ===")


if __name__ == "__main__":
    try:
        diagnose()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
