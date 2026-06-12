"""Смоук-тест USDT-модели: пополнение, покупка, вывод, сводка, графики."""
import os
import config
config.DATA_FILE = os.path.join(os.path.dirname(__file__), "_test_data.json")
import storage
storage.DATA_FILE = config.DATA_FILE
if os.path.exists(config.DATA_FILE):
    os.remove(config.DATA_FILE)

import portfolio
import charts

# 1) пополнили 1000 USDT по 95 ₽
portfolio.add_deposit(1000, 95.0)
# 2) купили BTC на 100 USDT
portfolio.market_buy("BTC", 100)

s = portfolio.summary()
print(f"USDT cash:        {s['usdt_cash']:.2f}  (ожидаем ~900)")
print(f"net deposited:    {s['net_deposited_usdt']:.2f} USDT")
print(f"invested_rub:     {s['invested_rub']:.2f} (ожидаем 95000)")
print(f"avg deposit rate: {s['avg_deposit_rate']:.2f}")
print(f"total value:      {s['total_value_usdt']:.2f} USDT / {s['value_rub']:.2f} ₽")
print(f"rate now (CBR):   {s['rate_now']:.2f}")
print(f"profit USDT:      {s['profit_usdt']:.2f} ({s['profit_usdt_pct']:+.1f}%)")
print(f"profit RUB:       {s['profit_rub']:.2f} ({s['profit_rub_pct']:+.1f}%)")
print(f"  asset gain rub: {s['asset_gain_rub']:.2f}")
print(f"  fx gain rub:    {s['fx_gain_rub']:.2f}")

# проверка инвариантов
assert abs(s['usdt_cash'] - 900) < 1.0, "cash должен быть ~900"
assert abs(s['invested_rub'] - 95000) < 1e-6, "invested_rub = 1000*95"
assert abs(s['profit_rub'] - (s['asset_gain_rub'] + s['fx_gain_rub'])) < 1e-6, "decomp"
assert abs(s['value_rub'] - s['total_value_usdt'] * s['rate_now']) < 1e-6, "value_rub"
print("OK инварианты сходятся")

for p in s["positions"]:
    print(f"  pos {p.ticker}: {p.qty:.6g} по ${p.avg_price_usdt:.2f}, тек ${p.price_now:.2f}, {p.profit_pct:+.1f}%")

# 3) вывод 200 USDT
portfolio.add_withdraw(200)
s2 = portfolio.summary()
print(f"после вывода 200: cash={s2['usdt_cash']:.2f} (ожидаем ~700), invested_rub={s2['invested_rub']:.2f} (ожидаем ~76000)")
assert abs(s2['usdt_cash'] - 700) < 1.0
assert abs(s2['invested_rub'] - 76000) < 1.0, "200*95 выведено из базы"

# 4) графики
print("pie bytes:", len(charts.composition_pie(portfolio.pie_slices(s2))))
print("line bytes:", len(charts.growth_line()))
print("ALL OK")

os.remove(config.DATA_FILE)
