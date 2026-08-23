import sys
from collections import Counter
from src import futmondo_api


def diagnose():
    print("=== Diagnóstico de News (styp) ===\n")

    print("[1] Login...")
    token, userid = futmondo_api.login()
    print("    OK\n")

    print("[2] Descargando TODAS las news...")
    news = futmondo_api.get_news(token, userid)
    print(f"    Total news items: {len(news)}\n")

    styp_counter = Counter()
    styp_examples: dict[str, list] = {}

    for item in news:
        styp = item.get("styp", "NO_STYP")
        styp_counter[styp] += 1

        if styp not in styp_examples or len(styp_examples[styp]) < 3:
            data = item.get("data", {})
            styp_examples.setdefault(styp, []).append({
                "_id": item.get("_id", "?"),
                "txt": item.get("txt", "")[:120],
                "data_keys": list(data.keys()) if isinstance(data, dict) else str(type(data)),
                "data_money": data.get("money") if isinstance(data, dict) else None,
                "data_name": data.get("name", "") if isinstance(data, dict) else None,
                "created": item.get("created", "?"),
            })

    print("[3] Distribución por styp:")
    for styp, count in styp_counter.most_common():
        print(f"    {styp:30s} → {count:5d} items")

    print(f"\n[4] Ejemplos por styp:")
    for styp, examples in sorted(styp_examples.items()):
        print(f"\n  --- {styp} ({styp_counter[styp]} items) ---")
        for ex in examples:
            print(f"    id={ex['_id']}")
            print(f"    txt={ex['txt']}")
            print(f"    data_keys={ex['data_keys']}")
            if ex['data_money'] is not None:
                print(f"    data.money={ex['data_money']}")
            if ex['data_name']:
                print(f"    data.name={ex['data_name']}")
            print(f"    created={ex['created']}")
            print()

    money_styps = []
    for styp, examples in styp_examples.items():
        has_money = any(ex.get("data_money") is not None for ex in examples)
        if has_money:
            money_styps.append(styp)

    print(f"\n[5] styp con campo 'money' en data: {money_styps}")
    print(f"    (Actualmente solo se sincroniza: 'customize')")

    if len(money_styps) > 1 or (money_styps and "customize" not in money_styps):
        print("\n    *** HAY TIPOS DE MONEY EVENTS QUE NO SE ESTÁN SINCRONIZANDO ***")
        missing = [s for s in money_styps if s != "customize"]
        for s in missing:
            total_money = 0
            count = 0
            for item in news:
                if item.get("styp") == s:
                    data = item.get("data", {})
                    if isinstance(data, dict) and data.get("money") is not None:
                        total_money += data.get("money", 0)
                        count += 1
            print(f"    {s}: {count} items con money, total = {total_money:,.0f}")
    else:
        print("\n    Solo 'customize' tiene money — no hay tipos faltantes.")

    print("\n[6] Análisis completo del endpoint pressroom vs news:")
    print("    Pressroom (transacciones): captura compras/ventas")
    print("    News (locker): captura repartos de dinero")

    all_keys_in_news = set()
    for item in news:
        all_keys_in_news.update(item.keys())
    print(f"\n    Claves presentes en news: {sorted(all_keys_in_news)}")

    print("\n=== Fin diagnóstico ===")


if __name__ == "__main__":
    try:
        diagnose()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
