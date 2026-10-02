// Manejo de "agregar a lista" y "crear alerta" desde las tarjetas.
// Como los botones no tienen el ID del producto directamente,
// buscamos por nombre al backend.

document.addEventListener("click", async (e) => {
    // Agregar a lista
    if (e.target.classList.contains("btn-lista")) {
        const nombre = e.target.dataset.producto;
        const res = await fetch("/api/lista/agregar-por-nombre", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nombre })
        });
        if (res.ok) {
            e.target.textContent = "✓";
            e.target.style.color = "#155724";
            setTimeout(() => {
                e.target.textContent = "➕";
                e.target.style.color = "";
            }, 1200);
        }
    }

    // Crear alerta
    if (e.target.classList.contains("btn-alerta")) {
        const nombre = e.target.dataset.producto;
        const res = await fetch("/api/alertas/crear-por-nombre", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nombre, umbral_pct: 10 })
        });
        if (res.ok) {
            e.target.textContent = "🔔✓";
            setTimeout(() => { e.target.textContent = "🔔"; }, 1200);
        }
    }
});