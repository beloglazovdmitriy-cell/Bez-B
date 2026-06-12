"""Генерация графиков для портфеля (PNG в память)."""
import io
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # без GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import storage

# единый стиль "Без Б" — прозрачный фон (без «чёрного окна»)
plt.rcParams.update({
    "figure.facecolor": "none",
    "axes.facecolor": "none",
    "savefig.facecolor": "none",
    "savefig.transparent": True,
    "axes.edgecolor": "#8a8f99",
    "axes.labelcolor": "#d1d4dc",
    "text.color": "#d1d4dc",
    "xtick.color": "#787b86",
    "ytick.color": "#787b86",
    "font.size": 11,
})

_ACCENT = "#26a69a"
_RED = "#ef5350"


def composition_pie(slices) -> bytes:
    """Кольцевая диаграмма состава портфеля. `slices` — список (label, value) в USDT.

    Даже на пустом портфеле рисуем настоящую (серую, нулевую) диаграмму,
    а не чёрное окно."""
    fig, ax = plt.subplots(figsize=(7, 5))
    slices = [(l, v) for l, v in (slices or []) if v > 0]
    labels = [l for l, _ in slices]
    values = [v for _, v in slices]
    total = sum(values)

    if not values or total <= 0:
        # настоящая «нулевая» бублик-диаграмма с подписью в центре
        ax.pie([1], colors=["#2a2e39"], startangle=90,
               wedgeprops={"width": 0.38, "edgecolor": "#0e1117"})
        ax.text(0, 0, "0 $\nпортфель пуст", ha="center", va="center",
                color="#787b86", fontsize=12, fontweight="bold")
        ax.set_title("Состав портфеля «Без Б»", color="#d1d4dc", fontweight="bold")
        return _render(fig)

    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct="%1.1f%%",
        startangle=90, pctdistance=0.78, labeldistance=1.08,
        wedgeprops={"width": 0.42, "edgecolor": "#0e1117"},
        textprops={"color": "#d1d4dc"},
    )
    # наименования активов — крупнее и жирнее, чтобы хорошо читались
    for tx in texts:
        tx.set_color("#ffffff")
        tx.set_fontsize(15)
        tx.set_fontweight("bold")
    for at in autotexts:
        at.set_color("#d1d4dc")
        at.set_fontsize(11)
        at.set_fontweight("bold")
    ax.text(0, 0, f"${total:,.0f}", ha="center", va="center",
            color="#d1d4dc", fontsize=14, fontweight="bold")
    ax.set_title("Состав портфеля «Без Б»", color="#d1d4dc", fontweight="bold")
    return _render(fig)


def growth_line() -> bytes:
    """Линия стоимости портфеля во времени против вложенной суммы (в рублях).

    Всегда рисуем оформленный график с осями и сеткой — даже когда снимков
    мало (тогда показываем нулевую/плоскую линию с подсказкой)."""
    from datetime import timedelta
    data = storage.load()
    history = data["history"]
    fig, ax = plt.subplots(figsize=(8, 4.5))

    if len(history) < 2:
        # настоящий пустой график с осями, нулевой линией и подсказкой
        if history:
            base = datetime.fromtimestamp(history[-1]["ts"])
            y0 = history[-1]["value_rub"]
        else:
            base, y0 = datetime.now(), 0.0
        xs = [base - timedelta(days=6), base]
        ax.plot(xs, [y0, y0], color=_ACCENT, linewidth=2,
                marker="o", label="Стоимость портфеля, ₽")
        ax.set_ylim(min(0, y0) - 1, max(1.0, y0 * 1.2))
        ax.text(0.5, 0.5, "Данные накапливаются\nпосле ежедневных снимков",
                transform=ax.transAxes, ha="center", va="center", color="#787b86")
        ax.set_title("Рост портфеля «Без Б»", color="#d1d4dc", fontweight="bold")
        ax.legend(facecolor="#0e1117", edgecolor="#2a2e39", labelcolor="#d1d4dc")
        ax.grid(True, color="#2a2e39", linewidth=0.5)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        fig.autofmt_xdate()
        return _render(fig)

    xs = [datetime.fromtimestamp(h["ts"]) for h in history]
    value = [h["value_rub"] for h in history]
    invested = [h["invested_rub"] for h in history]

    ax.plot(xs, value, color=_ACCENT, linewidth=2, label="Стоимость портфеля, ₽")
    ax.plot(xs, invested, color="#787b86", linewidth=1.5,
            linestyle="--", label="Вложено, ₽")
    ax.fill_between(xs, invested, value,
                    where=[v >= i for v, i in zip(value, invested)],
                    color=_ACCENT, alpha=0.15)
    ax.fill_between(xs, invested, value,
                    where=[v < i for v, i in zip(value, invested)],
                    color=_RED, alpha=0.15)

    ax.set_title("Рост портфеля «Без Б»", color="#d1d4dc", fontweight="bold")
    ax.legend(facecolor="#0e1117", edgecolor="#2a2e39", labelcolor="#d1d4dc")
    ax.grid(True, color="#2a2e39", linewidth=0.5)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    fig.autofmt_xdate()
    return _render(fig)


def benchmark_bar(results) -> bytes:
    """Горизонтальные столбики: рублёвая доходность каждого бенчмарка.
    Портфель «Без Б» выделен акцентным цветом."""
    rows = [r for r in results if r.get("ret_rub_pct") is not None]
    fig, ax = plt.subplots(figsize=(8, 0.6 * max(len(rows), 1) + 1.4))
    if not rows:
        ax.text(0.5, 0.5, "Недостаточно данных", ha="center", va="center")
        ax.axis("off")
        return _render(fig)

    rows = list(reversed(rows))          # лучший сверху
    names = [r["name"] for r in rows]
    vals = [r["ret_rub_pct"] for r in rows]
    colors = []
    for r in rows:
        if r.get("is_me"):
            colors.append(_ACCENT)
        elif r["ret_rub_pct"] >= 0:
            colors.append("#4a8f87")
        else:
            colors.append(_RED)

    bars = ax.barh(names, vals, color=colors, edgecolor="#0e1117")
    for r, v in zip(bars, vals):
        ax.text(v + (0.5 if v >= 0 else -0.5), r.get_y() + r.get_height() / 2,
                f"{v:+.1f}%", va="center", ha="left" if v >= 0 else "right",
                color="#d1d4dc", fontsize=10, fontweight="bold")
    ax.axvline(0, color="#787b86", linewidth=0.8)
    ax.set_title("Без Б против рынка — доходность в ₽", color="#d1d4dc", fontweight="bold")
    ax.grid(True, axis="x", color="#2a2e39", linewidth=0.5)
    ax.tick_params(labelsize=11)
    mx = max(abs(min(vals)), abs(max(vals)), 1)
    ax.set_xlim(min(0, min(vals)) - mx * 0.18, max(0, max(vals)) + mx * 0.22)
    return _render(fig)


def result_card(s, channel_name="@BezBlogfin") -> bytes:
    """Брендированная карточка результата для шеринга (4:5).

    Показывает доходность в ₽ и $, баланс, мини-график и ссылку на канал."""
    import storage
    from datetime import datetime

    fig = plt.figure(figsize=(8, 10))
    fig.patch.set_facecolor("#0e1117")

    def _col(v):
        return _ACCENT if v > 0 else (_RED if v < 0 else "#787b86")

    # шапка
    fig.text(0.5, 0.91, "БЕЗ Б", ha="center", va="center", color="#ffffff",
             fontsize=46, fontweight="bold")
    fig.text(0.5, 0.872, "Публичный портфель · инвестиции без буллшита",
             ha="center", color="#787b86", fontsize=15)
    fig.add_artist(plt.Line2D([0.1, 0.9], [0.85, 0.85], color="#2a2e39", linewidth=1))

    # доходность — две колонки
    fig.text(0.5, 0.805, "ДОХОДНОСТЬ", ha="center", color="#787b86",
             fontsize=15, fontweight="bold")
    rub_p, usd_p = s["profit_rub_pct"], s["profit_usdt_pct"]
    fig.text(0.28, 0.735, f"{rub_p:+.1f}%", ha="center", color=_col(rub_p),
             fontsize=50, fontweight="bold")
    fig.text(0.28, 0.69, "в рублях", ha="center", color="#d1d4dc", fontsize=16)
    fig.text(0.72, 0.735, f"{usd_p:+.1f}%", ha="center", color=_col(usd_p),
             fontsize=50, fontweight="bold")
    fig.text(0.72, 0.69, "в долларах", ha="center", color="#d1d4dc", fontsize=16)

    # баланс и реализованный доход
    fig.text(0.5, 0.62, f"Баланс: {s['total_value_usdt']:,.0f} $  ·  {s['value_rub']:,.0f} ₽"
             .replace(",", " "), ha="center", color="#d1d4dc", fontsize=18)
    if abs(s.get("realized_rub", 0)) > 1e-6:
        rz = s["realized_rub"]
        fig.text(0.5, 0.58, f"Реализовано за всё время: {rz:+,.0f} ₽".replace(",", " "),
                 ha="center", color=_col(rz), fontsize=15)

    # мини-график роста
    history = storage.load().get("history", [])
    ax = fig.add_axes([0.1, 0.27, 0.8, 0.25])
    ax.set_facecolor("#0e1117")
    pts = [h["value_rub"] for h in history]
    if len(pts) >= 2:
        xs = list(range(len(pts)))
        ax.plot(xs, pts, color=_ACCENT, linewidth=3)
        ax.fill_between(xs, min(pts), pts, color=_ACCENT, alpha=0.12)
        ax.margins(x=0.02, y=0.15)
    else:
        ax.text(0.5, 0.5, "график появится с накоплением истории",
                transform=ax.transAxes, ha="center", va="center", color="#787b86", fontsize=13)
    ax.set_title("Динамика портфеля, ₽", color="#787b86", fontsize=14)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])

    # подвал
    fig.add_artist(plt.Line2D([0.1, 0.9], [0.16, 0.16], color="#2a2e39", linewidth=1))
    fig.text(0.1, 0.115, datetime.now().strftime("%d.%m.%Y"),
             ha="left", color="#787b86", fontsize=15)
    fig.text(0.9, 0.115, channel_name, ha="right", color=_ACCENT,
             fontsize=18, fontweight="bold")
    fig.text(0.5, 0.055, "Слежу за портфелём в реальном времени. Все сделки — открыто.",
             ha="center", color="#787b86", fontsize=13)
    fig.text(0.5, 0.03, "Не является индивидуальной инвестиционной рекомендацией.",
             ha="center", color="#4a4e59", fontsize=11)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=135, facecolor="#0e1117")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def index_line() -> bytes:
    """График индекса Без Б в пунктах (старт 100)."""
    data = storage.load()
    pts = [(datetime.fromtimestamp(h["ts"]), h["index"])
           for h in data["history"] if "index" in h]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.axhline(100, color="#787b86", linewidth=1, linestyle="--")
    if len(pts) >= 2:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        up = ys[-1] >= 100
        col = _ACCENT if up else _RED
        ax.plot(xs, ys, color=col, linewidth=2.5, marker="o")
        ax.fill_between(xs, 100, ys, color=col, alpha=0.12)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        fig.autofmt_xdate()
    else:
        ax.set_ylim(95, 105)
        ax.text(0.5, 0.5, "Индекс наполняется снимками\n(старт — 100 пунктов)",
                transform=ax.transAxes, ha="center", va="center", color="#787b86")
    ax.set_title("Индекс Без Б, пунктов", color="#d1d4dc", fontweight="bold")
    ax.grid(True, color="#2a2e39", linewidth=0.5)
    return _render(fig)


def _render(fig) -> bytes:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=130, transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf.read()
