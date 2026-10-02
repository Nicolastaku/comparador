// Maneja el botón "Actualizar" y el panel de progreso en vivo.

const btnActualizar = document.getElementById("btn-actualizar");
const panelProgreso = document.getElementById("panel-progreso");
const panelLog = document.getElementById("panel-log");
const panelEstado = document.getElementById("panel-estado");
const btnCerrarPanel = document.getElementById("btn-cerrar-panel");

let eventSource = null;

function agregarLinea(texto) {
    const linea = document.createElement("div");
    linea.className = "log-linea";
    // Colorear según el contenido
    if (texto.startsWith("✅")) linea.classList.add("log-ok");
    else if (texto.startsWith("❌")) linea.classList.add("log-err");
    else if (texto.startsWith("⚠️")) linea.classList.add("log-warn");
    else if (texto.startsWith("🏪")) linea.classList.add("log-super");
    else if (texto.startsWith("📊")) linea.classList.add("log-info");
    linea.textContent = texto;
    panelLog.appendChild(linea);
    panelLog.scrollTop = panelLog.scrollHeight;
}

function mostrarPanel() {
    panelProgreso.classList.remove("oculto");
}

function ocultarPanel() {
    panelProgreso.classList.add("oculto");
}

btnCerrarPanel.addEventListener("click", () => {
    ocultarPanel();
});

// Verificar al cargar si ya hay una actualización corriendo
async function verificarEstadoInicial() {
    try {
        const res = await fetch("/api/actualizar/estado");
        const data = await res.json();
        if (data.corriendo) {
            mostrarPanel();
            panelLog.innerHTML = "";
            data.progreso.forEach(agregarLinea);
            panelEstado.textContent = "⏳ En curso...";
            conectarStream();
            btnActualizar.disabled = true;
            btnActualizar.classList.add("cargando");
        }
    } catch (e) {
        console.error("Error verificando estado:", e);
    }
}

function conectarStream() {
    if (eventSource) return;

    eventSource = new EventSource("/api/actualizar/stream");

    eventSource.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);

            if (data.fin) {
                panelEstado.textContent = "✅ Actualización completa";
                btnActualizar.disabled = false;
                btnActualizar.classList.remove("cargando");
                eventSource.close();
                eventSource = null;
                // Recargar la página después de 3 seg para mostrar datos nuevos
                setTimeout(() => {
                    location.reload();
                }, 3000);
                return;
            }

            if (data.linea) {
                agregarLinea(data.linea);
            }
        } catch (err) {
            console.error("Error parseando mensaje:", err);
        }
    };

    eventSource.onerror = () => {
        // Si el server cierra o falla, cerramos
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
    };
}

btnActualizar.addEventListener("click", async () => {
    if (btnActualizar.disabled) return;

    const confirmar = confirm(
        "¿Actualizar los precios ahora?\n\n" +
        "Esto va a tardar entre 5 y 15 minutos porque recorre todos los supermercados."
    );
    if (!confirmar) return;

    mostrarPanel();
    panelLog.innerHTML = "";
    panelEstado.textContent = "⏳ Iniciando...";
    btnActualizar.disabled = true;
    btnActualizar.classList.add("cargando");

    try {
        const res = await fetch("/api/actualizar", { method: "POST" });
        const data = await res.json();

        if (!data.ok) {
            agregarLinea("⚠️ " + data.mensaje);
            panelEstado.textContent = "⚠️ " + data.mensaje;
            btnActualizar.disabled = false;
            btnActualizar.classList.remove("cargando");
            return;
        }

        panelEstado.textContent = "⏳ En curso...";
        conectarStream();

    } catch (e) {
        agregarLinea("❌ Error: " + e.message);
        panelEstado.textContent = "❌ Error de conexión";
        btnActualizar.disabled = false;
        btnActualizar.classList.remove("cargando");
    }
});

// Auto-verificar al cargar
document.addEventListener("DOMContentLoaded", verificarEstadoInicial);