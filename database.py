"""
database.py
Base de datos SQLite + auto-descubrimiento + alertas + favoritos.
Soporta volumen persistente con variable de entorno DB_PATH.
"""
import os
import sqlite3
from datetime import datetime, timedelta

# Ruta de la DB: usa DB_PATH si está definido (para volúmenes),
# si no, usa la carpeta actual
DB = os.getenv("DB_PATH", "supermercados.db")


def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Productos
    c.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            categoria TEXT,
            termino_busqueda TEXT,
            activo INTEGER DEFAULT 1,
            descubierto INTEGER DEFAULT 0
        )
    """)

    # Precios
    c.execute("""
        CREATE TABLE IF NOT EXISTS precios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            supermercado TEXT NOT NULL,
            precio REAL,
            disponible INTEGER DEFAULT 1,
            url TEXT,
            fecha TEXT DEFAULT (date('now')),
            scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos(id),
            UNIQUE(producto_id, supermercado, fecha)
        )
    """)

    # Log
    c.execute("""
        CREATE TABLE IF NOT EXISTS log_scraper (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supermercado TEXT,
            ejecutado_at TEXT DEFAULT CURRENT_TIMESTAMP,
            exito INTEGER,
            productos_actualizados INTEGER,
            mensaje TEXT
        )
    """)

    # Favoritos
    c.execute("""
        CREATE TABLE IF NOT EXISTS favoritos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER DEFAULT 1,
            agregado_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos(id),
            UNIQUE(producto_id)
        )
    """)

    # Alertas
    c.execute("""
        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            umbral_pct REAL DEFAULT 10,
            activa INTEGER DEFAULT 1,
            creada_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos(id),
            UNIQUE(producto_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS alertas_disparadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            supermercado TEXT,
            precio_antes REAL,
            precio_ahora REAL,
            ahorro_pct REAL,
            disparada_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        )
    """)

    # Canastas
    c.execute("""
        CREATE TABLE IF NOT EXISTS canastas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT,
            icono TEXT DEFAULT '🛒'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS canasta_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canasta_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER DEFAULT 1,
            FOREIGN KEY (canasta_id) REFERENCES canastas(id),
            FOREIGN KEY (producto_id) REFERENCES productos(id),
            UNIQUE(canasta_id, producto_id)
        )
    """)

    # Índices
    c.execute("CREATE INDEX IF NOT EXISTS idx_precios_producto ON precios(producto_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_precios_fecha ON precios(fecha)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos(nombre)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(categoria)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_alertas_producto ON alertas(producto_id)")

    # Canasta básica
    productos_base = [
        # LÁCTEOS
        ("Leche Alquería 1L",              "Lácteos", "leche alqueria"),
        ("Leche Colanta 1L",               "Lácteos", "leche colanta"),
        ("Leche Alpina 1L",                "Lácteos", "leche alpina"),
        ("Yogurt Alpina 1L",               "Lácteos", "yogurt alpina"),
        ("Queso Campesino 250g",           "Lácteos", "queso campesino"),
        ("Mantequilla Colanta 125g",       "Lácteos", "mantequilla colanta"),
        # GRANOS
        ("Arroz Diana 500g",               "Granos", "arroz diana"),
        ("Arroz Roa 500g",                 "Granos", "arroz roa"),
        ("Frijol Cargamanto 500g",         "Granos", "frijol cargamanto"),
        ("Lenteja 500g",                   "Granos", "lenteja"),
        ("Garbanzo 500g",                  "Granos", "garbanzo"),
        # ACEITES
        ("Aceite Girasol 1L",              "Aceites", "aceite girasol"),
        ("Aceite Premier 1L",              "Aceites", "aceite premier"),
        ("Aceite Oliva 500ml",             "Aceites", "aceite oliva"),
        # HUEVOS
        ("Huevos AA x30",                  "Huevos", "huevos aa"),
        ("Huevos AA x12",                  "Huevos", "huevos docena"),
        # PANADERÍA
        ("Pan tajado Bimbo",               "Panadería", "pan tajado bimbo"),
        ("Pan tajado Integral",            "Panadería", "pan tajado integral"),
        # CAFÉ
        ("Café Águila Roja 500g",          "Café", "cafe aguila roja"),
        ("Café Sello Rojo 500g",           "Café", "cafe sello rojo"),
        ("Café Juan Valdez 500g",          "Café", "cafe juan valdez"),
        # ENDULZANTES
        ("Azúcar Manuelita 1kg",           "Endulzantes", "azucar manuelita"),
        ("Panela 500g",                    "Endulzantes", "panela"),
        # PASTAS
        ("Pasta Doria 500g",               "Pastas", "pasta doria"),
        ("Pasta Comarrico 500g",           "Pastas", "pasta comarrico"),
        # ENLATADOS
        ("Atún Van Camps 170g",            "Enlatados", "atun van camps"),
        ("Atún Isabel 170g",               "Enlatados", "atun isabel"),
        ("Sardinas 425g",                  "Enlatados", "sardinas"),
        # ASEO PERSONAL
        ("Jabón Rey x3",                   "Aseo personal", "jabon rey"),
        ("Jabón Protex",                   "Aseo personal", "jabon protex"),
        ("Papel higiénico Familia 4",      "Aseo personal", "papel higienico familia"),
        ("Papel higiénico Scott 4",        "Aseo personal", "papel higienico scott"),
        ("Crema dental Colgate",           "Aseo personal", "crema dental colgate"),
        ("Shampoo Sedal",                  "Aseo personal", "shampoo sedal"),
        # ASEO HOGAR
        ("Detergente Fab 1kg",             "Aseo hogar", "detergente fab"),
        ("Detergente Ariel 1kg",           "Aseo hogar", "detergente ariel"),
        ("Jabón Rey en polvo 900g",        "Aseo hogar", "jabon rey polvo"),
        ("Limpiador Fabuloso 1L",          "Aseo hogar", "fabuloso"),
        ("Blanqueador Clorox 1L",          "Aseo hogar", "clorox"),
        # BEBIDAS
        ("Gaseosa Coca-Cola 1.5L",         "Bebidas", "coca cola 1.5"),
        ("Gaseosa Pepsi 1.5L",             "Bebidas", "pepsi 1.5"),
        ("Agua Cristal 1.5L",              "Bebidas", "agua cristal"),
        ("Jugo Hit 1L",                    "Bebidas", "jugo hit"),
        ("Malta Pony 330ml",               "Bebidas", "malta pony"),
        # SNACKS
        ("Papas Margarita",                "Snacks", "papas margarita"),
        ("Chocorramo",                     "Snacks", "chocorramo"),
        ("Galletas Festival",              "Snacks", "galletas festival"),
        # CARNES
        ("Pechuga de pollo 1kg",           "Carnes", "pechuga pollo"),
        ("Carne molida 500g",              "Carnes", "carne molida"),
        ("Chorizo x5",                     "Carnes", "chorizo"),
        # VERDURAS/FRUTAS
        ("Papa criolla 1kg",               "Verduras", "papa criolla"),
        ("Tomate 1kg",                     "Verduras", "tomate"),
        ("Cebolla 1kg",                    "Verduras", "cebolla"),
        ("Plátano 1kg",                    "Frutas", "platano"),
    ]

    for nombre, cat, termino in productos_base:
        c.execute("""
            INSERT OR IGNORE INTO productos
            (nombre, categoria, termino_busqueda, activo, descubierto)
            VALUES (?, ?, ?, 1, 0)
        """, (nombre, cat, termino))

    canastas_base = [
        ("Semanal básica", "Lo esencial para una semana", "🛒"),
        ("Familiar", "Canasta para familia de 4", "👨‍👩‍👧‍👦"),
        ("Aseo del hogar", "Productos de limpieza", "🧹"),
        ("Desayuno", "Para el desayuno diario", "☕"),
    ]
    for nombre, desc, icono in canastas_base:
        c.execute("""
            INSERT OR IGNORE INTO canastas (nombre, descripcion, icono)
            VALUES (?, ?, ?)
        """, (nombre, desc, icono))

    conn.commit()
    conn.close()
    print(f"✅ Base de datos inicializada en: {DB}")


# ============================================================
# PRECIOS
# ============================================================
def guardar_precio(producto_id, supermercado, precio, disponible=1, url=None):
    if precio is None or precio <= 0:
        return
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO precios (producto_id, supermercado, precio, disponible, url, fecha)
        VALUES (?, ?, ?, ?, ?, date('now'))
        ON CONFLICT(producto_id, supermercado, fecha)
        DO UPDATE SET precio=excluded.precio,
                      disponible=excluded.disponible,
                      url=excluded.url,
                      scraped_at=CURRENT_TIMESTAMP
    """, (producto_id, supermercado, precio, disponible, url))
    conn.commit()
    conn.close()


def get_productos_activos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, nombre, termino_busqueda FROM productos WHERE activo = 1")
    rows = c.fetchall()
    conn.close()
    return [(r["id"], r["nombre"], r["termino_busqueda"]) for r in rows]


def get_todos_nombres_productos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT nombre FROM productos")
    rows = c.fetchall()
    conn.close()
    return {r["nombre"] for r in rows}


def agregar_producto_si_no_existe(nombre, categoria="General", termino=None):
    if not nombre:
        return None
    nombre = nombre.strip()
    if len(nombre) < 5 or len(nombre) > 90:
        return None

    basura = ["combo", "pack x", "gratis", "regalo", "sorpresa",
              "kit ", "canasta", "mercado x", "docena x"]
    nombre_low = nombre.lower()
    if any(b in nombre_low for b in basura):
        return None

    if not termino:
        termino = nombre_low

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM productos WHERE nombre = ?", (nombre,))
    row = c.fetchone()
    if row:
        conn.close()
        return row["id"]

    try:
        c.execute("""
            INSERT INTO productos
            (nombre, categoria, termino_busqueda, activo, descubierto)
            VALUES (?, ?, ?, 1, 1)
        """, (nombre, categoria, termino))
        nuevo_id = c.lastrowid
        conn.commit()
        conn.close()
        return nuevo_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def buscar_productos(query):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT
            p.nombre AS producto,
            p.categoria,
            pr.supermercado,
            pr.precio,
            pr.fecha,
            pr.disponible,
            pr.url
        FROM productos p
        JOIN precios pr ON pr.producto_id = p.id
        WHERE LOWER(p.nombre) LIKE ?
          AND pr.fecha = (
              SELECT MAX(fecha) FROM precios
              WHERE producto_id = p.id
                AND supermercado = pr.supermercado
          )
        ORDER BY p.nombre, pr.precio ASC
    """, (f"%{query.lower()}%",))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_todos_los_productos_con_precios(categoria=None, limite=1000):
    conn = get_conn()
    c = conn.cursor()
    sql = """
        SELECT
            p.id AS producto_id,
            p.nombre AS producto,
            p.categoria,
            pr.supermercado,
            pr.precio,
            pr.fecha,
            pr.disponible,
            pr.url
        FROM productos p
        LEFT JOIN precios pr ON pr.producto_id = p.id
            AND pr.fecha = (
                SELECT MAX(fecha) FROM precios
                WHERE producto_id = p.id
                  AND supermercado = pr.supermercado
            )
        WHERE p.activo = 1
    """
    params = []
    if categoria:
        sql += " AND p.categoria = ?"
        params.append(categoria)
    sql += " ORDER BY p.categoria, p.nombre, pr.precio ASC LIMIT ?"
    params.append(limite)
    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_categorias():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT categoria, COUNT(*) as total
        FROM productos
        WHERE activo = 1 AND categoria IS NOT NULL
        GROUP BY categoria
        ORDER BY categoria
    """)
    rows = c.fetchall()
    conn.close()
    return [{"categoria": r["categoria"], "total": r["total"]} for r in rows]


def get_sugerencias(limit=12):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT nombre FROM productos WHERE activo=1 LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [r["nombre"] for r in rows]


def get_ultima_actualizacion():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT MAX(scraped_at) FROM precios")
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def get_supermercados_activos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT supermercado FROM precios ORDER BY supermercado")
    rows = c.fetchall()
    conn.close()
    return [r["supermercado"] for r in rows]


def get_total_productos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM productos WHERE activo = 1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def log(supermercado, exito, num, mensaje=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO log_scraper (supermercado, exito, productos_actualizados, mensaje)
        VALUES (?, ?, ?, ?)
    """, (supermercado, int(exito), num, mensaje[:500]))
    conn.commit()
    conn.close()


# ============================================================
# HISTÓRICO Y PRODUCTOS
# ============================================================
def get_historial(producto_nombre=None, producto_id=None, supermercado=None, dias=30):
    conn = get_conn()
    c = conn.cursor()
    sql = """
        SELECT pr.supermercado, pr.precio, pr.fecha
        FROM precios pr
        JOIN productos p ON p.id = pr.producto_id
        WHERE pr.fecha >= date('now', ?)
    """
    params = [f"-{dias} days"]

    if producto_id:
        sql += " AND pr.producto_id = ?"
        params.append(producto_id)
    elif producto_nombre:
        sql += " AND LOWER(p.nombre) LIKE ?"
        params.append(f"%{producto_nombre.lower()}%")

    if supermercado:
        sql += " AND pr.supermercado = ?"
        params.append(supermercado)
    sql += " ORDER BY pr.fecha ASC"

    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_producto_por_id(producto_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM productos WHERE id = ?", (producto_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_producto_por_nombre(nombre):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM productos WHERE nombre = ?", (nombre,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# ============================================================
# FAVORITOS / LISTA DE MERCADO
# ============================================================
def agregar_favorito(producto_id, cantidad=1):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO favoritos (producto_id, cantidad)
        VALUES (?, ?)
        ON CONFLICT(producto_id)
        DO UPDATE SET cantidad = excluded.cantidad
    """, (producto_id, cantidad))
    conn.commit()
    conn.close()


def quitar_favorito(producto_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM favoritos WHERE producto_id = ?", (producto_id,))
    conn.commit()
    conn.close()


def get_favoritos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT f.id, f.producto_id, f.cantidad,
               p.nombre, p.categoria
        FROM favoritos f
        JOIN productos p ON p.id = f.producto_id
        ORDER BY f.agregado_at DESC
    """)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def limpiar_favoritos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM favoritos")
    conn.commit()
    conn.close()


def calcular_lista_optima():
    favoritos = get_favoritos()
    if not favoritos:
        return None

    conn = get_conn()
    c = conn.cursor()

    detalle = []
    for fav in favoritos:
        c.execute("""
            SELECT supermercado, precio, url
            FROM precios
            WHERE producto_id = ?
              AND fecha = (SELECT MAX(fecha) FROM precios WHERE producto_id = ?)
        """, (fav["producto_id"], fav["producto_id"]))
        precios = [dict(r) for r in c.fetchall()]
        if precios:
            precios.sort(key=lambda x: x["precio"])
            detalle.append({
                "producto": fav["nombre"],
                "cantidad": fav["cantidad"],
                "precios": precios,
                "mejor": precios[0],
            })

    totales = {}
    for item in detalle:
        for p in item["precios"]:
            s = p["supermercado"]
            if s not in totales:
                totales[s] = {"total": 0, "productos": 0, "faltantes": 0}
            totales[s]["total"] += p["precio"] * item["cantidad"]
            totales[s]["productos"] += 1

    total_favoritos = len(favoritos)
    for s in totales:
        totales[s]["faltantes"] = total_favoritos - totales[s]["productos"]

    conn.close()

    ranking = sorted(
        [{"supermercado": s, **v} for s, v in totales.items()],
        key=lambda x: (x["faltantes"], x["total"])
    )

    return {
        "detalle": detalle,
        "ranking": ranking,
        "total_productos": total_favoritos,
        "mejor_super": ranking[0] if ranking else None,
    }


# ============================================================
# ALERTAS
# ============================================================
def crear_alerta(producto_id, umbral_pct=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO alertas (producto_id, umbral_pct, activa)
        VALUES (?, ?, 1)
        ON CONFLICT(producto_id)
        DO UPDATE SET umbral_pct = excluded.umbral_pct, activa = 1
    """, (producto_id, umbral_pct))
    conn.commit()
    conn.close()


def quitar_alerta(producto_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM alertas WHERE producto_id = ?", (producto_id,))
    conn.commit()
    conn.close()


def get_alertas():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT a.id, a.producto_id, a.umbral_pct, a.activa, a.creada_at,
               p.nombre, p.categoria
        FROM alertas a
        JOIN productos p ON p.id = a.producto_id
        WHERE a.activa = 1
        ORDER BY a.creada_at DESC
    """)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_alertas_disparadas(limite=50):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT ad.*, p.nombre AS producto
        FROM alertas_disparadas ad
        JOIN productos p ON p.id = ad.producto_id
        ORDER BY ad.disparada_at DESC
        LIMIT ?
    """, (limite,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def guardar_alerta_disparada(producto_id, supermercado,
                              precio_antes, precio_ahora, ahorro_pct):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO alertas_disparadas
        (producto_id, supermercado, precio_antes, precio_ahora, ahorro_pct)
        VALUES (?, ?, ?, ?, ?)
    """, (producto_id, supermercado, precio_antes, precio_ahora, ahorro_pct))
    conn.commit()
    conn.close()


# ============================================================
# CANASTAS
# ============================================================
def get_canastas():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT c.id, c.nombre, c.descripcion, c.icono,
               COUNT(ci.id) AS total_items
        FROM canastas c
        LEFT JOIN canasta_items ci ON ci.canasta_id = c.id
        GROUP BY c.id
        ORDER BY c.nombre
    """)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_canasta_detalle(canasta_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM canastas WHERE id = ?", (canasta_id,))
    canasta = c.fetchone()
    if not canasta:
        conn.close()
        return None

    c.execute("""
        SELECT ci.cantidad, p.id AS producto_id, p.nombre, p.categoria
        FROM canasta_items ci
        JOIN productos p ON p.id = ci.producto_id
        WHERE ci.canasta_id = ?
    """, (canasta_id,))
    items = [dict(r) for r in c.fetchall()]
    conn.close()

    return {
        "id": canasta["id"],
        "nombre": canasta["nombre"],
        "descripcion": canasta["descripcion"],
        "icono": canasta["icono"],
        "items": items,
    }


# ============================================================
# ESTADÍSTICAS
# ============================================================
def get_estadisticas_globales():
    conn = get_conn()
    c = conn.cursor()

    stats = {}

    c.execute("SELECT COUNT(*) FROM productos WHERE activo = 1")
    stats["total_productos"] = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT supermercado) FROM precios")
    stats["total_supermercados"] = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM precios")
    stats["total_registros"] = c.fetchone()[0]

    c.execute("""
        SELECT p.nombre, pr.supermercado,
               MAX(CASE WHEN pr.fecha = date('now', '-7 days') THEN pr.precio END) AS hace7,
               MAX(pr.precio) AS ultimo
        FROM precios pr
        JOIN productos p ON p.id = pr.producto_id
        WHERE pr.fecha >= date('now', '-7 days')
        GROUP BY p.id, pr.supermercado
        HAVING hace7 IS NOT NULL AND ultimo < hace7
        ORDER BY (hace7 - ultimo) / hace7 DESC
        LIMIT 10
    """)
    stats["mas_bajaron"] = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT p.nombre, pr.supermercado,
               MAX(CASE WHEN pr.fecha = date('now', '-7 days') THEN pr.precio END) AS hace7,
               MAX(pr.precio) AS ultimo
        FROM precios pr
        JOIN productos p ON p.id = pr.producto_id
        WHERE pr.fecha >= date('now', '-7 days')
        GROUP BY p.id, pr.supermercado
        HAVING hace7 IS NOT NULL AND ultimo > hace7
        ORDER BY (ultimo - hace7) / hace7 DESC
        LIMIT 10
    """)
    stats["mas_subieron"] = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT supermercado, AVG(precio) AS promedio, COUNT(*) AS registros
        FROM precios
        WHERE fecha >= date('now', '-1 day')
        GROUP BY supermercado
        HAVING registros >= 3
        ORDER BY promedio ASC
    """)
    stats["ranking_supers"] = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT categoria, COUNT(*) AS total
        FROM productos
        WHERE activo = 1 AND categoria IS NOT NULL
        GROUP BY categoria
        ORDER BY total DESC
    """)
    stats["por_categoria"] = [dict(r) for r in c.fetchall()]

    conn.close()
    return stats


def get_historial_precio_producto(producto_id, dias=30):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT fecha, supermercado, AVG(precio) AS precio
        FROM precios
        WHERE producto_id = ?
          AND fecha >= date('now', ?)
        GROUP BY fecha, supermercado
        ORDER BY fecha ASC
    """, (producto_id, f"-{dias} days"))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    fechas = sorted(set(r["fecha"] for r in rows))
    supers = sorted(set(r["supermercado"] for r in rows))

    series = {s: [] for s in supers}
    for fecha in fechas:
        for s in supers:
            valor = next(
                (r["precio"] for r in rows
                 if r["fecha"] == fecha and r["supermercado"] == s),
                None
            )
            series[s].append(valor)

    return {"fechas": fechas, "series": series}