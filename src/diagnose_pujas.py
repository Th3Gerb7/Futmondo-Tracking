import sys
from src.supabase_client import get_client


def diagnose():
    print("=== Análisis de Pujas Máximas y Margen de Maniobra ===\n")

    db = get_client()

    dashboard = db.table("UserDashboard").select("*").execute().data or []
    squads = db.table("SquadPlayers").select(
        "IDUser, PlayerName, Position, CurrentValue, BuyPrice, RealTeam"
    ).execute().data or []

    squad_by_user: dict[str, list[dict]] = {}
    for p in squads:
        uid = p.get("IDUser")
        if uid:
            squad_by_user.setdefault(uid, []).append(p)

    sorted_dash = sorted(dashboard, key=lambda u: u.get("PujaMaxima", 0), reverse=True)

    print(f"{'#':>2} {'Usuario':30s} | {'Balance':>14s} | {'ValorEquipo':>14s} | {'PujaMaxima':>14s} | {'Jugadores':>4s}")
    print("-" * 100)

    for i, u in enumerate(sorted_dash, 1):
        name = u.get("NameInGame") or u.get("UserName") or u["IDUser"][:16]
        balance = u.get("Balance", 0)
        valor = u.get("ValorEquipo", 0)
        puja = u.get("PujaMaxima", 0)
        n_players = len(squad_by_user.get(u["IDUser"], []))
        print(f"{i:>2} {name:30s} | {balance:>14,.0f} | {valor:>14,.0f} | {puja:>14,.0f} | {n_players:>4d}")

    print("\n" + "=" * 100)
    print("DETALLE POR USUARIO: Jugadores vendibles y su impacto en puja")
    print("=" * 100)
    print("\nFórmula: PujaMaxima = Balance + 50% * ValorEquipo")
    print("Si vendes un jugador a precio X:")
    print("  - Balance sube X")
    print("  - ValorEquipo baja CurrentValue")
    print("  - Nueva Puja = (Balance + X) + 50% * (ValorEquipo - CurrentValue)")
    print("  - Ganancia neta en puja = X - 50% * CurrentValue")
    print("  (si vendes al mercado por su CurrentValue, ganas +50% de CurrentValue en puja)\n")

    for u in sorted_dash:
        uid = u["IDUser"]
        name = u.get("NameInGame") or u.get("UserName") or uid[:16]
        balance = u.get("Balance", 0)
        valor = u.get("ValorEquipo", 0)
        puja = u.get("PujaMaxima", 0)
        players = squad_by_user.get(uid, [])

        print(f"\n{'─' * 80}")
        print(f"  {name}")
        print(f"  Balance: {balance:>14,.0f}  |  ValorEquipo: {valor:>14,.0f}  |  PujaMaxima: {puja:>14,.0f}")
        print(f"  Jugadores: {len(players)}")

        if not players:
            print("  (sin datos de plantilla)")
            continue

        players_sorted = sorted(players, key=lambda p: p.get("CurrentValue", 0), reverse=True)

        print(f"\n  {'Jugador':28s} {'Pos':>3s} {'Equipo':>12s} | {'ValorActual':>14s} {'PrecioCompra':>14s} {'Plusvalia':>12s} | {'PujaTrasSoltar':>14s} {'GananciaPuja':>12s}")
        print(f"  {'-' * 130}")

        for p in players_sorted:
            pname = p.get("PlayerName", "?")[:28]
            pos = (p.get("Position") or "?")[:3]
            team = (p.get("RealTeam") or "?")[:12]
            cv = p.get("CurrentValue", 0)
            bp = p.get("BuyPrice", 0)
            plusvalia = cv - bp

            new_balance = balance + cv
            new_valor = valor - cv
            new_puja = new_balance + new_valor * 0.5
            gain_puja = new_puja - puja

            print(f"  {pname:28s} {pos:>3s} {team:>12s} | {cv:>14,.0f} {bp:>14,.0f} {plusvalia:>+12,.0f} | {new_puja:>14,.0f} {gain_puja:>+12,.0f}")

        if len(players) >= 2:
            top2 = players_sorted[:2]
            total_cv = sum(p.get("CurrentValue", 0) for p in top2)
            new_balance2 = balance + total_cv
            new_valor2 = valor - total_cv
            new_puja2 = new_balance2 + new_valor2 * 0.5
            gain2 = new_puja2 - puja
            names2 = " + ".join(p.get("PlayerName", "?")[:15] for p in top2)
            print(f"\n  >>> Si vende los 2 más caros ({names2}):")
            print(f"      PujaMaxima pasaría a {new_puja2:,.0f} ({gain2:+,.0f})")

        if len(players) >= 3:
            top3 = players_sorted[:3]
            total_cv = sum(p.get("CurrentValue", 0) for p in top3)
            new_balance3 = balance + total_cv
            new_valor3 = valor - total_cv
            new_puja3 = new_balance3 + new_valor3 * 0.5
            gain3 = new_puja3 - puja
            names3 = " + ".join(p.get("PlayerName", "?")[:12] for p in top3)
            print(f"  >>> Si vende los 3 más caros ({names3}):")
            print(f"      PujaMaxima pasaría a {new_puja3:,.0f} ({gain3:+,.0f})")

    print("\n\n=== RANKING DE PUJA MÁXIMA TEÓRICA (si venden todo) ===\n")
    print(f"{'#':>2} {'Usuario':30s} | {'PujaActual':>14s} | {'PujaVenderTodo':>14s}")
    print("-" * 70)

    teoricas = []
    for u in sorted_dash:
        uid = u["IDUser"]
        name = u.get("NameInGame") or u.get("UserName") or uid[:16]
        balance = u.get("Balance", 0)
        valor = u.get("ValorEquipo", 0)
        puja = u.get("PujaMaxima", 0)
        puja_total = balance + valor
        teoricas.append((name, puja, puja_total))

    teoricas.sort(key=lambda x: x[2], reverse=True)
    for i, (name, puja, puja_total) in enumerate(teoricas, 1):
        print(f"{i:>2} {name:30s} | {puja:>14,.0f} | {puja_total:>14,.0f}")

    print("\n=== Fin análisis pujas ===")


if __name__ == "__main__":
    try:
        diagnose()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
