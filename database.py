"""
database.py
Base de datos SQLite + auto-descubrimiento de productos.
"""
import sqlite3

DB = "supermercados.db"


def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

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

    c.execute("CREATE INDEX IF NOT EXISTS idx_precios_producto ON precios(producto_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_precios_fecha ON precios(fecha)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos(nombre)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(categoria)")

    # ============================================================
    # CANASTA BÁSICA (Fontibón) — ~50 productos
    # ============================================================
    productos_base = [
        # ---- LÁCTEOS ----
        ("Leche Alquería 1L",              "Lácteos", "leche alqueria"),
        ("Leche Colanta 1L",               "Lácteos", "leche colanta"),
        ("Leche Alpina 1L",                "Lácteos", "leche alpina"),
        ("Yogurt Alpina 1L",               "Lácteos", "yogurt alpina"),
        ("Queso Campesino 250g",           "Lácteos", "queso campesino"),
        ("Mantequilla Colanta 125g",       "Lácteos", "mantequilla colanta"),

        # ---- GRANOS ----
        ("Arroz Diana 500g",               "Granos", "arroz diana"),
        ("Arroz Roa 500g",                 "Granos", "arroz roa"),
        ("Frijol Cargamanto 500g",         "Granos", "frijol cargamanto"),
        ("Lenteja 500g",                   "Granos", "lenteja"),
        ("Garbanzo 500g",                  "Granos", "garbanzo"),

        # ---- ACEITES ----
        ("Aceite Girasol 1L",              "Aceites", "aceite girasol"),
        ("Aceite Premier 1L",              "Aceites", "aceite premier"),
        ("Aceite Oliva 500ml",             "Aceites", "aceite oliva"),

        # ---- HUEVOS ----
        ("Huevos AA x30",                  "Huevos", "huevos aa"),
        ("Huevos AA x12",                  "Huevos", "huevos docena"),

        # ---- PANADERÍA ----
        ("Pan tajado Bimbo",               "Panadería", "pan tajado bimbo"),
        ("Pan tajado Integral",            "Panadería", "pan tajado integral"),

        # ---- CAFÉ ----
        ("Café Águila Roja 500g",          "Café", "cafe aguila roja"),
        ("Café Sello Rojo 500g",           "Café", "cafe sello rojo"),
        ("Café Juan Valdez 500g",          "Café", "cafe juan valdez"),

        # ---- ENDULZANTES ----
        ("Azúcar Manuelita 1kg",           "Endulzantes", "azucar manuelita"),
        ("Panela 500g",                    "Endulzantes", "panela"),

        # ---- PASTAS ----
        ("Pasta Doria 500g",               "Pastas", "pasta doria"),
        ("Pasta Comarrico 500g",           "Pastas", "pasta comarrico"),

        # ---- ENLATADOS ----
        ("Atún Van Camps 170g",            "Enlatados", "atun van camps"),
        ("Atún Isabel 170g",               "Enlatados", "atun isabel"),
        ("Sardinas 425g",                  "Enlatados", "sardinas"),

        # ---- ASEO PERSONAL ----
        ("Jabón Rey x3",                   "Aseo personal", "jabon rey"),
        ("Jabón Protex",                   "Aseo personal", "jabon protex"),
        ("Papel higiénico Familia 4",      "Aseo personal", "papel higienico familia"),
        ("Papel higiénico Scott 4",        "Aseo personal", "papel higienico scott"),
        ("Crema dental Colgate",           "Aseo personal", "crema dental colgate"),
        ("Shampoo Sedal",                  "Aseo personal", "shampoo sedal"),

        # ---- ASEO HOGAR ----
        ("Detergente Fab 1kg",             "Aseo hogar", "detergente fab"),
        ("Detergente Ariel 1kg",           "Aseo hogar", "detergente ariel"),
        ("Jabón Rey en polvo 900g",        "Aseo hogar", "jabon rey polvo"),
        ("Limpiador Fabuloso 1L",          "Aseo hogar", "fabuloso"),
        ("Blanqueador Clorox 1L",          "Aseo hogar", "clorox"),

        # ---- BEBIDAS ----
        ("Gaseosa Coca-Cola 1.5L",         "Bebidas", "coca cola 1.5"),
        ("Gaseosa Pepsi 1.5L",             "Bebidas", "pepsi 1.5"),
        ("Agua Cristal 1.5L",              "Bebidas", "agua cristal"),
        ("Jugo Hit 1L",                    "Bebidas", "jugo hit"),
        ("Malta Pony 330ml",               "Bebidas", "malta pony"),

        # ---- SNACKS ----
        ("Papas Margarita",                "Snacks", "papas margarita"),
        ("Chocorramo",                     "Snacks", "chocorramo"),
        ("Galletas Festival",              "Snacks", "galletas festival"),

        # ---- CARNES ----
        ("Pechuga de pollo 1kg",           "Carnes", "pechuga pollo"),
        ("Carne molida 500g",              "Carnes", "carne molida"),
        ("Chorizo x5",                     "Carnes", "chorizo"),

        # ---- VERDURAS/FRUTAS ----
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

    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada")


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
    c.execute("""
        SELECT id, nombre, termino_busqueda
        FROM productos
        WHERE activo = 1
    """)
    rows = c.fetchall()
    conn.close()
    return [(r["id"], r["nombre"], r["termino_busqueda"]) for r in rows]


def get_todos_nombres_productos():
    """Set de nombres para chequeo rápido de duplicados."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT nombre FROM productos")
    rows = c.fetchall()
    conn.close()
    return {r["nombre"] for r in rows}


def agregar_producto_si_no_existe(nombre, categoria="General", termino=None):
    """
    Agrega un producto descubierto automáticamente.
    Filtra nombres basura (combos, packs grandes, etc.).
    """
    if not nombre:
        return None

    nombre = nombre.strip()
    if len(nombre) < 5 or len(nombre) > 90:
        return None

    # Filtros anti-basura
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


def get_todos_los_productos_con_precios(categoria=None, limite=200):
    """Productos con su último precio por súper. Para la home."""
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

    sql += " ORDER BY p.categoria, p.nombre, pr.precio ASC"
    sql += " LIMIT ?"
    params.append(limite)

    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_categorias():
    """Categorías con conteo de productos."""
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


def get_historial(producto_nombre, supermercado=None, dias=30):
    conn = get_conn()
    c = conn.cursor()
    sql = """
        SELECT pr.supermercado, pr.precio, pr.fecha
        FROM precios pr
        JOIN productos p ON p.id = pr.producto_id
        WHERE LOWER(p.nombre) LIKE ?
          AND pr.fecha >= date('now', ?)
    """
    params = [f"%{producto_nombre.lower()}%", f"-{dias} days"]
    if supermercado:
        sql += " AND pr.supermercado = ?"
        params.append(supermercado)
    sql += " ORDER BY pr.fecha ASC"

    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]