"""
app.py
Servidor web Flask con vista en tarjetas.
"""
from flask import Flask, render_template, request, jsonify

from database import (
    init_db, buscar_productos, get_sugerencias,
    get_ultima_actualizacion, get_historial,
    get_todos_los_productos_con_precios,
    get_supermercados_activos,
    get_categorias,
    get_total_productos,
)

app = Flask(__name__)


def _agrupar(resultados_raw):
    """Agrupa lista plana por producto."""
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


@app.route("/")
def index():
    categoria = request.args.get("categoria", "").strip() or None
    todos = get_todos_los_productos_con_precios(categoria=categoria, limite=1000)
    grupos = _agrupar(todos)

    ahorro_total = sum(g["ahorro"] for g in grupos)
    supers = get_supermercados_activos()
    categorias = get_categorias()
    total_catalogo = get_total_productos()

    return render_template(
        "index.html",
        grupos=grupos,
        ultima=get_ultima_actualizacion(),
        total_productos=len(grupos),
        total_catalogo=total_catalogo,
        ahorro_total=ahorro_total,
        supermercados=supers,
        categorias=categorias,
        categoria_actual=categoria,
    )


@app.route("/buscar")
def buscar():
    q = request.args.get("q", "").strip()

    if not q:
        return render_template(
            "resultados.html",
            grupos=[],
            query=q,
            ultima=get_ultima_actualizacion(),
        )

    resultados_raw = buscar_productos(q)
    grupos = _agrupar(resultados_raw)

    return render_template(
        "resultados.html",
        grupos=grupos,
        query=q,
        ultima=get_ultima_actualizacion(),
    )


@app.route("/historial/<path:nombre>")
def historial(nombre):
    datos = get_historial(nombre, dias=30)
    return jsonify(datos)


@app.route("/api/buscar")
def api_buscar():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Falta parámetro 'q'"}), 400
    return jsonify(buscar_productos(q))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5300)