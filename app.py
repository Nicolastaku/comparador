"""
app.py
Servidor web Flask con todas las features + botón Actualizar.
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from datetime import datetime
import os
import threading
import queue
import json

from database import (
    init_db, buscar_productos, get_sugerencias,
    get_ultima_actualizacion, get_historial,
    get_todos_los_productos_con_precios,
    get_supermercados_activos, get_categorias, get_total_productos,
    get_producto_por_id, get_producto_por_nombre,
    get_historial_precio_producto,
    agregar_favorito, quitar_favorito, get_favoritos,
    limpiar_favoritos, calcular_lista_optima,
    crear_alerta, quitar_alerta, get_alertas, get_alertas_disparadas,
    get_canastas, get_canasta_detalle,
    get_estadisticas_globales,
)
from prediccion import predecir_precio, get_mejores_ofertas

app = Flask(__name__)


# ============================================================
# INICIALIZAR DB AL IMPORTAR
# ============================================================
try:
    init_db()
    print("✅ DB inicializada al arrancar app.py")
except Exception as e:
    print(f"⚠️ Error inicializando DB: {e}")


# ============================================================
# ESTADO GLOBAL DEL SCRAPER
# (para saber si está corriendo y mostrar progreso)
# ============================================================
class EstadoScraper:
    def __init__(self):
        self.corriendo = False
        self.progreso = []
        self.suscriptores = []
        self.lock = threading.Lock()
        self.thread = None

    def emitir(self, mensaje):
        """Envía un mensaje a todos los clientes SSE."""
        with self.lock:
            self.progreso.append(mensaje)
            # Solo guardar los últimos 200
            if len(self.progreso) > 200:
                self.progreso = self.progreso[-200:]
            # Notificar a suscriptores
            for q in self.suscriptores:
                try:
                    q.put_nowait(mensaje)
                except Exception:
                    pass

    def suscribir(self):
        q = queue.Queue()
        with self.lock:
            self.suscriptores.append(q)
        return q

    def desuscribir(self, q):
        with self.lock:
            if q in self.suscriptores:
                self.suscriptores.remove(q)


estado = EstadoScraper()


def ejecutar_scraper_background():
    """Corre el scraper en un thread separado, emitiendo progreso."""
    from scraper import actualizar_todo
    import sys

    # Redirigir prints al emisor SSE
    class EmisorStream:
        def write(self, texto):
            texto = texto.rstrip("\n")
            if texto:
                estado.emitir(texto)
        def flush(self):
            pass

    old_stdout = sys.stdout
    sys.stdout = EmisorStream()

    try:
        estado.emitir("▶️ Iniciando actualización...")
        actualizar_todo(descubrir=True, verificar_alertas_al_final=True)
        estado.emitir("✅ ¡Actualización completa!")
    except Exception as e:
        estado.emitir(f"❌ Error: {e}")
    finally:
        sys.stdout = old_stdout
        estado.corriendo = False
        estado.emitir("__FIN__")


# ============================================================
# HELPERS
# ============================================================
def _agrupar(resultados_raw):
    productos_agrupados = {}
    for r in resultados_raw:
        nombre = r["producto"]
        if nombre not in productos_agrupados:
            productos_agrupados[nombre] = {
                "categoria": r.get("categoria", "General"),
                "precios": [],
            }
        ya = any(
            x["supermercado"] == r["supermercado"]
            for x in productos_agrupados[nombre]["precios"]
        )
        if not ya and r["precio"] is not None:
            productos_agrupados[nombre]["precios"].append({
                "supermercado": r["supermercado"],
                "precio": r["precio"],
                "fecha": r["fecha"],
                "disponible": r["disponible"],
                "url": r["url"],
            })

    grupos = []
    for nombre, info in productos_agrupados.items():
        precios = info["precios"]
        if not precios:
            continue
        precios_ordenados = sorted(precios, key=lambda x: x["precio"])
        mejor = precios_ordenados[0]
        peor = precios_ordenados[-1]
        ahorro = peor["precio"] - mejor["precio"]
        ahorro_pct = (ahorro / peor["precio"]) * 100 if peor["precio"] else 0

        grupos.append({
            "nombre": nombre,
            "categoria": info["categoria"],
            "precios": precios_ordenados,
            "mejor": mejor,
            "ahorro": ahorro,
            "ahorro_pct": ahorro_pct,
            "total_supers": len(precios_ordenados),
        })
    grupos.sort(key=lambda g: g["ahorro"], reverse=True)
    return grupos


@app.context_processor
def inject_globals():
    return {
        "ultima": get_ultima_actualizacion(),
    }


# ============================================================
# RUTAS PRINCIPALES
# ============================================================
@app.route("/")
def index():
    categoria = request.args.get("categoria", "").strip() or None
    todos = get_todos_los_productos_con_precios(categoria=categoria, limite=1000)
    grupos = _agrupar(todos)

    ahorro_total = sum(g["ahorro"] for g in grupos)
    return render_template(
        "index.html",
        grupos=grupos,
        total_productos=len(grupos),
        total_catalogo=get_total_productos(),
        ahorro_total=ahorro_total,
        supermercados=get_supermercados_activos(),
        categorias=get_categorias(),
        categoria_actual=categoria,
    )


@app.route("/buscar")
def buscar():
    q = request.args.get("q", "").strip()
    if not q:
        return render_template("resultados.html", grupos=[], query=q)
    grupos = _agrupar(buscar_productos(q))
    return render_template("resultados.html", grupos=grupos, query=q)


# ============================================================
# ACTUALIZAR (SCRAPER MANUAL) + SSE
# ============================================================
@app.route("/api/actualizar", methods=["POST"])
def api_actualizar():
    """Dispara el scraper en background. No bloquea."""
    if estado.corriendo:
        return jsonify({
            "ok": False,
            "mensaje": "Ya hay una actualización en curso"
        }), 409

    estado.corriendo = True
    estado.progreso = []

    thread = threading.Thread(target=ejecutar_scraper_background, daemon=True)
    thread.start()

    return jsonify({"ok": True, "mensaje": "Actualización iniciada"})


@app.route("/api/actualizar/estado")
def api_actualizar_estado():
    """Devuelve si está corriendo y el progreso actual."""
    return jsonify({
        "corriendo": estado.corriendo,
        "progreso": estado.progreso[-50:],
    })


@app.route("/api/actualizar/stream")
def api_actualizar_stream():
    """
    Server-Sent Events: stream en vivo del progreso.
    El navegador se conecta una vez y recibe actualizaciones.
    """
    def event_stream():
        # Enviar historial actual primero
        with estado.lock:
            for msg in estado.progreso[-50:]:
                yield f"data: {json.dumps({'linea': msg})}\n\n"

        q = estado.suscribir()
        try:
            # Heartbeat cada 15 seg para no cerrar la conexión
            import time
            while True:
                try:
                    msg = q.get(timeout=15)
                    if msg == "__FIN__":
                        yield f"data: {json.dumps({'fin': True})}\n\n"
                        break
                    yield f"data: {json.dumps({'linea': msg})}\n\n"
                except queue.Empty:
                    yield f": heartbeat\n\n"
        finally:
            estado.desuscribir(q)

    return Response(event_stream(), mimetype="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    })


# ============================================================
# HISTORIAL + PREDICCIÓN
# ============================================================
@app.route("/historial/<int:producto_id>")
def historial(producto_id):
    producto = get_producto_por_id(producto_id)
    if not producto:
        return redirect(url_for("index"))
    historico = get_historial_precio_producto(producto_id, dias=30)
    prediccion = predecir_precio(producto_id)
    return render_template(
        "historial.html",
        producto=producto,
        historico=historico,
        prediccion=prediccion,
    )


@app.route("/api/historial/<int:producto_id>")
def api_historial(producto_id):
    return jsonify(get_historial_precio_producto(producto_id, dias=30))


# ============================================================
# LISTA DE MERCADO
# ============================================================
@app.route("/lista")
def lista():
    analisis = calcular_lista_optima()
    return render_template("lista.html", analisis=analisis,
                            favoritos=get_favoritos())


@app.route("/api/lista/agregar", methods=["POST"])
def api_lista_agregar():
    data = request.get_json() or {}
    pid = data.get("producto_id")
    cantidad = int(data.get("cantidad", 1))
    if not pid:
        return jsonify({"error": "Falta producto_id"}), 400
    agregar_favorito(pid, cantidad)
    return jsonify({"ok": True, "total": len(get_favoritos())})


@app.route("/api/lista/agregar-por-nombre", methods=["POST"])
def api_lista_agregar_por_nombre():
    data = request.get_json() or {}
    nombre = data.get("nombre", "").strip()
    producto = get_producto_por_nombre(nombre)
    if not producto:
        return jsonify({"error": "Producto no encontrado"}), 404
    agregar_favorito(producto["id"])
    return jsonify({"ok": True})


@app.route("/api/lista/quitar", methods=["POST"])
def api_lista_quitar():
    data = request.get_json() or {}
    pid = data.get("producto_id")
    if not pid:
        return jsonify({"error": "Falta producto_id"}), 400
    quitar_favorito(pid)
    return jsonify({"ok": True, "total": len(get_favoritos())})


@app.route("/api/lista/limpiar", methods=["POST"])
def api_lista_limpiar():
    limpiar_favoritos()
    return jsonify({"ok": True})


@app.route("/api/lista")
def api_lista():
    return jsonify(get_favoritos())


# ============================================================
# ALERTAS
# ============================================================
@app.route("/alertas")
def alertas_page():
    return render_template(
        "alertas.html",
        alertas=get_alertas(),
        disparadas=get_alertas_disparadas(limite=30),
    )


@app.route("/api/alertas/crear", methods=["POST"])
def api_alerta_crear():
    data = request.get_json() or {}
    pid = data.get("producto_id")
    umbral = float(data.get("umbral_pct", 10))
    if not pid:
        return jsonify({"error": "Falta producto_id"}), 400
    crear_alerta(pid, umbral)
    return jsonify({"ok": True})


@app.route("/api/alertas/crear-por-nombre", methods=["POST"])
def api_alerta_crear_por_nombre():
    data = request.get_json() or {}
    nombre = data.get("nombre", "").strip()
    umbral = float(data.get("umbral_pct", 10))
    producto = get_producto_por_nombre(nombre)
    if not producto:
        return jsonify({"error": "Producto no encontrado"}), 404
    crear_alerta(producto["id"], umbral)
    return jsonify({"ok": True})


@app.route("/api/alertas/quitar", methods=["POST"])
def api_alerta_quitar():
    data = request.get_json() or {}
    pid = data.get("producto_id")
    if not pid:
        return jsonify({"error": "Falta producto_id"}), 400
    quitar_alerta(pid)
    return jsonify({"ok": True})


# ============================================================
# TENDENCIAS
# ============================================================
@app.route("/tendencias")
def tendencias():
    stats = get_estadisticas_globales()
    ofertas = get_mejores_ofertas(limite=15)
    return render_template("tendencias.html", stats=stats, ofertas=ofertas)


# ============================================================
# CANASTAS
# ============================================================
@app.route("/canastas")
def canastas():
    return render_template("canastas.html", canastas=get_canastas())


@app.route("/canastas/<int:canasta_id>")
def canasta_detalle(canasta_id):
    canasta = get_canasta_detalle(canasta_id)
    if not canasta:
        return redirect(url_for("canastas"))

    for item in canasta["items"]:
        historico = get_historial(producto_id=item["producto_id"], dias=1)
        precios = {}
        for h in historico:
            s = h["supermercado"]
            if s not in precios or h["precio"] < precios[s]:
                precios[s] = h["precio"]
        item["precios"] = sorted(
            [{"supermercado": s, "precio": p} for s, p in precios.items()],
            key=lambda x: x["precio"]
        )
        item["mejor"] = item["precios"][0] if item["precios"] else None

    return render_template("canastas.html", canasta=canasta, canastas=get_canastas())


# ============================================================
# API GENERAL
# ============================================================
@app.route("/api/buscar")
def api_buscar():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Falta parámetro 'q'"}), 400
    return jsonify(buscar_productos(q))


@app.route("/api/prediccion/<int:producto_id>")
def api_prediccion(producto_id):
    return jsonify(predecir_precio(producto_id))


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.now().isoformat(),
        "scraper_corriendo": estado.corriendo,
    })


# ============================================================
# ARRANQUE LOCAL
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5300))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    app.run(debug=debug, host="0.0.0.0", port=port, threaded=True)