"""
alertas.py
Verifica alertas y dispara notificaciones cuando baja el precio.
Se ejecuta después de cada scraping.
"""
from database import (
    get_conn, get_alertas, guardar_alerta_disparada, get_producto_por_id
)
from notificador import (
    enviar_telegram, enviar_email,
    formatear_alerta_telegram, formatear_alerta_email
)


def verificar_alertas(enviar=True):
    """
    Recorre las alertas activas y verifica si el precio bajó
    más del umbral. Envía notificaciones si enviar=True.
    """
    alertas = get_alertas()
    if not alertas:
        print("  ℹ️  No hay alertas configuradas")
        return []

    disparadas = []
    print(f"  🔔 Verificando {len(alertas)} alertas...")

    conn = get_conn()
    c = conn.cursor()

    for alerta in alertas:
        pid = alerta["producto_id"]
        umbral = alerta["umbral_pct"]

        # Traer los últimos 2 precios distintos por supermercado
        c.execute("""
            SELECT supermercado, fecha, AVG(precio) AS precio
            FROM precios
            WHERE producto_id = ?
              AND fecha IN (
                  SELECT DISTINCT fecha FROM precios
                  WHERE producto_id = ?
                  ORDER BY fecha DESC LIMIT 2
              )
            GROUP BY supermercado, fecha
            ORDER BY supermercado, fecha DESC
        """, (pid, pid))

        rows = [dict(r) for r in c.fetchall()]

        # Agrupar por supermercado: {super: [precio_ahora, precio_antes]}
        por_super = {}
        for r in rows:
            s = r["supermercado"]
            if s not in por_super:
                por_super[s] = []
            por_super[s].append(r["precio"])

        for super_nombre, precios in por_super.items():
            if len(precios) < 2:
                continue

            precio_ahora = precios[0]  # Más reciente
            precio_antes = precios[1]  # Anterior

            if precio_antes <= 0:
                continue

            cambio_pct = ((precio_ahora - precio_antes) / precio_antes) * 100

            # Bajó más del umbral
            if cambio_pct <= -abs(umbral):
                guardar_alerta_disparada(
                    pid, super_nombre,
                    precio_antes, precio_ahora,
                    abs(cambio_pct)
                )
                disparadas.append({
                    "producto": alerta["nombre"],
                    "supermercado": super_nombre,
                    "precio_antes": precio_antes,
                    "precio_ahora": precio_ahora,
                    "ahorro_pct": abs(cambio_pct),
                    "url": f"https://www.{super_nombre.lower()}.com",
                })

    conn.close()

    # Enviar notificaciones
    if enviar and disparadas:
        print(f"  📤 Enviando {len(disparadas)} notificaciones...")

        # Telegram: una por una
        for d in disparadas:
            enviar_telegram(formatear_alerta_telegram(d))

        # Email: todas juntas
        enviar_email(
            f"🛒 {len(disparadas)} bajadas de precio detectadas",
            formatear_alerta_email(disparadas)
        )

    return disparadas


if __name__ == "__main__":
    verificar_alertas()