"""
app.py
Servidor web Flask con todas las features.
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime

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

    # Agregar precios de cada item
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
# API
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
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


if __name__ == "__main__":
    import os
    init_db()
    port = int(os.getenv("PORT", 5300))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    app.run(debug=debug, host="0.0.0.0", port=port)