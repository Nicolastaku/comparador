"""
scraper.py
Scraper con Playwright + auto-descubrimiento de productos.
"""
import re
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from database import (
    init_db, get_productos_activos, guardar_precio, log,
    agregar_producto_si_no_existe, get_todos_nombres_productos,
)

DELAY = 1.5
MAX_DESCUBIERTOS_POR_BUSQUEDA = 8  # tope por término de búsqueda


# ============================================================
#  VTEX + auto-descubrimiento
# ============================================================
def buscar_vtex_playwright(page, base_url, termino, super_nombre,
                            descubrir=True, nombres_existentes=None):
    api_url = (
        f"{base_url}/api/catalog_system/pub/products/search"
        f"?ft={termino}&_from=0&_to=9"
    )

    try:
        if not getattr(page, "_visited", False):
            try:
                page.goto(base_url, wait_until="domcontentloaded", timeout=25000)
            except Exception:
                pass
            page._visited = True

        response = page.request.get(api_url, timeout=15000)

        if response.status not in (200, 206):
            print(f"    ⚠️  [{super_nombre}] HTTP {response.status}")
            return None

        data = response.json()
        if not isinstance(data, list) or not data:
            return None

        # ====== AUTO-DESCUBRIMIENTO ======
        if descubrir and nombres_existentes is not None:
            agregados = 0
            for prod in data:
                if agregados >= MAX_DESCUBIERTOS_POR_BUSQUEDA:
                    break
                nombre_prod = (prod.get("productName") or "").strip()
                if not nombre_prod or nombre_prod in nombres_existentes:
                    continue

                categoria = "General"
                cats = prod.get("categories") or []
                if cats:
                    partes = cats[0].strip("/").split("/")
                    if partes and partes[0]:
                        categoria = partes[0]

                resultado = agregar_producto_si_no_existe(
                    nombre_prod, categoria, nombre_prod.lower()
                )
                if resultado:
                    nombres_existentes.add(nombre_prod)
                    agregados += 1

        # ====== PRECIO ======
        for prod in data:
            for item in prod.get("items", []):
                for seller in item.get("sellers", []):
                    offer = seller.get("commertialOffer", {})
                    precio = offer.get("Price")
                    stock = offer.get("AvailableQuantity", 0)
                    if precio and precio > 0:
                        return {
                            "precio": float(precio),
                            "disponible": 1 if stock > 0 else 0,
                            "url": prod.get("link", base_url),
                            "nombre_match": prod.get("productName", ""),
                        }
        return None

    except PWTimeout:
        print(f"    ⏱️  [{super_nombre}] Timeout")
        return None
    except Exception as e:
        print(f"    ❌ [{super_nombre}] {type(e).__name__}: {str(e)[:70]}")
        return None


# ============================================================
#  D1
# ============================================================
def buscar_d1_playwright(page, termino):
    urls_a_probar = [
        f"https://domicilios.d1.com.co/buscar?q={termino}",
        f"https://www.d1.com.co/buscar?q={termino}",
    ]

    for url in urls_a_probar:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            try:
                page.wait_for_selector(
                    "[class*='product'], [class*='Product'], [class*='price']",
                    timeout=6000,
                )
            except PWTimeout:
                continue

            elementos = page.query_selector_all("[class*='price'], [class*='Price']")
            for el in elementos:
                try:
                    texto = el.inner_text().strip()
                except Exception:
                    continue
                numeros = re.sub(r"[^\d]", "", texto)
                if numeros and len(numeros) >= 3:
                    precio = float(numeros)
                    if 500 <= precio <= 500000:
                        return {
                            "precio": precio,
                            "disponible": 1,
                            "url": url,
                            "nombre_match": termino,
                        }
            return None

        except PWTimeout:
            print(f"    ⏱️  [D1] Timeout")
            continue
        except Exception as e:
            print(f"    ❌ [D1] {type(e).__name__}: {str(e)[:70]}")
            continue

    return None


# ============================================================
#  Supermercados
# ============================================================
SUPERMERCADOS = {
    "Olímpica":  {"tipo": "vtex", "base": "https://www.olimpica.com"},
    "Éxito":     {"tipo": "vtex", "base": "https://www.exito.com"},
    "Carulla":   {"tipo": "vtex", "base": "https://www.carulla.com"},
    "Jumbo":     {"tipo": "vtex", "base": "https://www.jumbo.com.co"},
    "Metro":     {"tipo": "vtex", "base": "https://www.metro.co"},
    "Alkosto":   {"tipo": "vtex", "base": "https://www.alkosto.com"},
    "Makro":     {"tipo": "vtex", "base": "https://www.makro.co"},
    "Surtimax":  {"tipo": "vtex", "base": "https://www.surtimax.com.co"},
    "D1":        {"tipo": "d1"},
}


# ============================================================
#  Principal
# ============================================================
def actualizar_todo(descubrir=True):
    init_db()
    productos = get_productos_activos()

    nombres_existentes = get_todos_nombres_productos() if descubrir else set()
    nombres_antes = len(nombres_existentes)

    print(f"\n{'='*60}")
    print(f"🔄 Playwright Scraper")
    print(f"📦 Productos en catálogo: {len(productos)}")
    print(f"🔍 Auto-descubrimiento: {'ACTIVADO' if descubrir else 'desactivado'}")
    print(f"🏪 Supermercados: {', '.join(SUPERMERCADOS.keys())}")
    print(f"{'='*60}\n")

    resumen = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            locale="es-CO",
            timezone_id="America/Bogota",
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        for super_nombre, cfg in SUPERMERCADOS.items():
            print(f"\n🏪 {super_nombre}")
            actualizados = 0
            errores = 0

            page = context.new_page()

            for pid, nombre, termino in productos:
                try:
                    if cfg["tipo"] == "vtex":
                        res = buscar_vtex_playwright(
                            page, cfg["base"], termino, super_nombre,
                            descubrir=descubrir,
                            nombres_existentes=nombres_existentes,
                        )
                    elif cfg["tipo"] == "d1":
                        res = buscar_d1_playwright(page, termino)
                    else:
                        res = None

                    if res:
                        guardar_precio(
                            pid, super_nombre,
                            res["precio"],
                            res.get("disponible", 1),
                            res.get("url"),
                        )
                        actualizados += 1
                        print(f"  ✅ {nombre}: ${res['precio']:,.0f}")
                    else:
                        print(f"  ⚠️  {nombre}: sin datos")

                    time.sleep(DELAY)

                except Exception as e:
                    errores += 1
                    print(f"  ❌ {nombre}: {str(e)[:70]}")

            page.close()
            exito = errores < len(productos) / 2
            log(super_nombre, exito, actualizados,
                f"{actualizados} ok, {errores} err")
            resumen[super_nombre] = {
                "actualizados": actualizados,
                "total": len(productos),
            }

        browser.close()

    # Resumen
    print(f"\n{'='*60}")
    print("📊 RESUMEN FINAL")
    print(f"{'='*60}")
    for s, stats in resumen.items():
        pct = (stats["actualizados"] / stats["total"] * 100) if stats["total"] else 0
        emoji = "✅" if stats["actualizados"] > 0 else "❌"
        print(f"  {emoji} {s}: {stats['actualizados']}/{stats['total']} ({pct:.0f}%)")

    nombres_despues = get_todos_nombres_productos()
    nuevos = len(nombres_despues) - nombres_antes
    print(f"\n  🔍 Productos descubiertos esta corrida: {nuevos}")
    print(f"  📚 Total productos en catálogo: {len(nombres_despues)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    actualizar_todo(descubrir=True)