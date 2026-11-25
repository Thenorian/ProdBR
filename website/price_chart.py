"""
Gráfico de preço do produto, no estilo de bolsa de valores: uma linha com os últimos
100 preços informados, ao longo do tempo, com a área embaixo e o preço base de venda
como linha de referência tracejada.

Aqui só se calculam as posições (em pixels do SVG). O desenho fica no template
(_price_chart.html) e o mouse em cima (cruz e balão com o valor) no price_chart.js.
"""
from datetime import datetime

CHART_WIDTH = 720
CHART_HEIGHT = 260
MARGIN_LEFT = 72
MARGIN_RIGHT = 16
MARGIN_TOP = 16
MARGIN_BOTTOM = 32
GRID_LINE_COUNT = 4
# Espaço acima e abaixo do maior e do menor preço, para a linha não encostar na borda.
VERTICAL_BREATHING_ROOM = 0.12


def build_price_chart(reports, base_sale_price):
    """
    Recebe os informes do GET /products/{id}/prices (mais antigo primeiro) e devolve
    tudo que o template precisa, ou None se não há preço.

        {
            "points": [{"x": 72.0, "y": 140.5, "price": 12.9, "reported_at": "...", ...}],
            "line_path": "M72.0,140.5 L...",
            "area_path": "M72.0,244 L... Z",
            "grid": [{"y": 16.0, "price": 14.5}, ...],
            "base_line_y": 120.0 ou None,
            "first_date": "...", "last_date": "...",
        }
    """
    if not reports:
        return None

    times = [read_date(report["reported_at"]).timestamp() for report in reports]
    prices = [report["price"] for report in reports]

    lowest_price, highest_price = min(prices), max(prices)
    if base_sale_price is not None:
        lowest_price, highest_price = min(lowest_price, base_sale_price), max(highest_price, base_sale_price)
    price_range = highest_price - lowest_price or highest_price or 1
    bottom_price = max(0, lowest_price - price_range * VERTICAL_BREATHING_ROOM)
    top_price = highest_price + price_range * VERTICAL_BREATHING_ROOM

    first_time, last_time = times[0], times[-1]
    plot_width = CHART_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    plot_height = CHART_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    plot_bottom = MARGIN_TOP + plot_height

    def x_for(time):
        if last_time == first_time:
            return MARGIN_LEFT + plot_width / 2
        return MARGIN_LEFT + (time - first_time) / (last_time - first_time) * plot_width

    def y_for(price):
        return MARGIN_TOP + (top_price - price) / (top_price - bottom_price) * plot_height

    points = [
        {**report, "x": round(x_for(time), 1), "y": round(y_for(report["price"]), 1)}
        for report, time in zip(reports, times)
    ]

    line_path = " ".join(f"{'M' if index == 0 else 'L'}{point['x']},{point['y']}" for index, point in enumerate(points))
    area_path = (
        f"M{points[0]['x']},{plot_bottom} "
        + " ".join(f"L{point['x']},{point['y']}" for point in points)
        + f" L{points[-1]['x']},{plot_bottom} Z"
    )

    grid = []
    for line_number in range(GRID_LINE_COUNT + 1):
        price = bottom_price + (top_price - bottom_price) * line_number / GRID_LINE_COUNT
        grid.append({"y": round(y_for(price), 1), "price": round(price, 2)})

    return {
        "width": CHART_WIDTH,
        "height": CHART_HEIGHT,
        "plot_left": MARGIN_LEFT,
        "plot_right": CHART_WIDTH - MARGIN_RIGHT,
        "plot_top": MARGIN_TOP,
        "plot_bottom": plot_bottom,
        "points": points,
        "line_path": line_path,
        "area_path": area_path,
        "grid": grid,
        "base_line_y": round(y_for(base_sale_price), 1) if base_sale_price is not None else None,
        "first_date": reports[0]["reported_at"],
        "last_date": reports[-1]["reported_at"],
    }


def read_date(text):
    """ "2026-11-24 18:13:53" -> datetime """
    return datetime.strptime(str(text)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
