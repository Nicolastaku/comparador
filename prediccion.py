"""
prediccion.py
Predicción simple de precios basada en tendencia lineal.
"""
from datetime import datetime, timedelta
from database import get_conn


def predecir_precio(producto_id, supermercado=None, dias_futuro=7):
    """
    Predice el precio usando regresión lineal simple sobre el histórico.
    Retorna dict: {precio_predicho, tendencia, cambio_pct, confianza}
    """
    conn = get_conn()
    c = conn.cursor()

    sql = """
        SELECT fecha, AVG(precio) AS precio
        FROM precios
        WHERE producto_id = ?
    """
    params = [producto_id]
    if supermercado:
        sql += " AND supermercado = ?"
        params.append(supermercado)
    sql += " GROUP BY fecha ORDER BY fecha ASC LIMIT 60"

    c.execute(sql, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    if len(rows) < 3:
        return {
            "precio_predicho": None,
            "tendencia": "sin datos",
            "cambio_pct": 0,
            "confianza": 0,
            "dias_datos": len(rows),
        }

    # Regresión lineal simple
    # Convertir fechas a días desde el primer registro
    fechas = [datetime.fromisoformat(r["fecha"]).date() for r in rows]
    base = fechas[0]
    x = [(f - base).days for f in fechas]
    y = [r["precio"] for r in rows]
    n = len(x)

    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi ** 2 for xi in x)

    denom = (n * sum_x2 - sum_x ** 2)
    if denom == 0:
        return {
            "precio_predicho": y[-1],
            "tendencia": "estable",
            "cambio_pct": 0,
            "confianza": 30,
            "dias_datos": n,
        }

    m = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_y - m * sum_x) / n

    # Predecir para mañana + dias_futuro
    x_futuro = (fechas[-1] - base).days + dias_futuro
    y_predicho = m * x_futuro + b

    # Calcular cambio porcentual
    precio_actual = y[-1]
    cambio_pct = ((y_predicho - precio_actual) / precio_actual) * 100 if precio_actual else 0

    # Confianza basada en cantidad de datos
    confianza = min(len(rows) * 3, 90)

    # Determinar tendencia
    if cambio_pct < -2:
        tendencia = "bajando"
    elif cambio_pct > 2:
        tendencia = "subiendo"
    else:
        tendencia = "estable"

    return {
        "precio_predicho": round(y_predicho, 0),
        "precio_actual": precio_actual,
        "tendencia": tendencia,
        "cambio_pct": round(cambio_pct, 1),
        "confianza": confianza,
        "dias_datos": n,
        "dias_futuro": dias_futuro,
    }


def get_mejores_ofertas(limite=20):
    """
    Detecta productos que probablemente suban próximamente
    (última oportunidad para comprar barato).
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, nombre FROM productos
        WHERE activo = 1
        LIMIT 200
    """)
    productos = [dict(r) for r in c.fetchall()]
    conn.close()

    oportunidades = []
    for p in productos:
        pred = predecir_precio(p["id"])
        if pred["tendencia"] == "subiendo" and pred["confianza"] >= 30:
            oportunidades.append({
                "producto": p["nombre"],
                "producto_id": p["id"],
                "precio_actual": pred.get("precio_actual"),
                "precio_predicho": pred["precio_predicho"],
                "cambio_pct": pred["cambio_pct"],
            })

    oportunidades.sort(key=lambda x: x["cambio_pct"], reverse=True)
    return oportunidades[:limite]