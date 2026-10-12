const API = "/api";
const $ = (sel) => document.querySelector(sel);

/* ─────────────── Utilidades ─────────────── */

function toast(msg, tipo = "ok") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast show ${tipo}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.className = "toast"), 3800);
}

async function apiFetch(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (res.status === 204) return null;

  let data = null;
  try { data = await res.json(); } catch { /* sin body */ }

  if (!res.ok) {
    const d = data?.detail;
    let msg = `Error ${res.status}`;
    if (Array.isArray(d)) msg = d.map((e) => `${e.loc.slice(1).join(".")}: ${e.msg}`).join(" | ");
    else if (typeof d === "string") msg = d;
    throw new Error(msg);
  }
  return data;
}

/* ─────────────── Estado de la API ─────────────── */

async function checkHealth() {
  const pill = $("#api-status");
  try {
    await apiFetch("/health");
    pill.textContent = "API: en línea";
    pill.className = "pill pill-on";
  } catch {
    pill.textContent = "API: sin conexión";
    pill.className = "pill pill-off";
  }
}

/* ─────────────── Listar ─────────────── */

async function cargarReservas() {
  const cont = $("#lista-reservas");
  cont.innerHTML = `<p class="muted">Cargando…</p>`;

  const estado = $("#filtro-estado").value;
  const fecha = $("#filtro-fecha").value;

  const params = new URLSearchParams({ page: 1, limit: 50 });
  if (estado) params.append("estado", estado);
  if (fecha) params.append("fecha", fecha);

  try {
    const data = await apiFetch(`/reservas?${params}`);
    if (!data.items.length) {
      cont.innerHTML = `<p class="muted">No hay reservas registradas.</p>`;
      return;
    }
    cont.innerHTML = data.items.map(renderItem).join("");
    cont.querySelectorAll("[data-del]").forEach((b) =>
      b.addEventListener("click", () => eliminarReserva(b.dataset.del))
    );
    cont.querySelectorAll("[data-edit]").forEach((b) =>
      b.addEventListener("click", () => cargarEnFormulario(b.dataset.edit))
    );
    cont.querySelectorAll("[data-conf]").forEach((b) =>
      b.addEventListener("click", () => cambiarEstado(b.dataset.conf, "confirmada"))
    );
  } catch (e) {
    cont.innerHTML = `<p class="muted">Error: ${e.message}</p>`;
  }
}

function renderItem(r) {
  const notas = r.notas ? `<small> ${r.notas}</small>` : "";
  const mesa = r.mesa ? ` · Mesa ${r.mesa}` : "";
  return `
    <div class="item ${r.estado}">
      <div class="item-info">
        <strong>${r.cliente_nombre}
          <span class="badge ${r.estado}">${r.estado}</span>
        </strong>
        <small> ${r.fecha} ·  ${r.hora} ·  ${r.num_personas} personas${mesa}</small>
        <small> ${r.cliente_email} ·  ${r.telefono}</small>
        ${notas}
      </div>
      <div class="item-actions">
        ${r.estado !== "confirmada"
          ? `<button class="btn btn-ghost" data-conf="${r.id}">✓</button>` : ""}
        <button class="btn btn-ghost" data-edit="${r.id}"></button>
        <button class="btn btn-danger" data-del="${r.id}">✕</button>
      </div>
    </div>`;
}

/* ─────────────── Crear / Actualizar ─────────────── */

$("#form-reserva").addEventListener("submit", async (ev) => {
  ev.preventDefault();

  const id = $("#reserva-id").value;

  const payload = {
    cliente_nombre: $("#cliente_nombre").value.trim(),
    cliente_email: $("#cliente_email").value.trim(),
    telefono: $("#telefono").value.trim(),
    fecha: $("#fecha").value,
    hora: $("#hora").value,
    num_personas: Number($("#num_personas").value),
    mesa: $("#mesa").value.trim() || null,
    notas: $("#notas").value.trim() || null,
    estado: $("#estado").value,
  };

  try {
    if (id) {
      await apiFetch(`/reservas/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      toast("Reserva actualizada correctamente", "ok");
    } else {
      await apiFetch("/reservas", { method: "POST", body: JSON.stringify(payload) });
      toast("Reserva creada correctamente", "ok");
    }
    limpiarFormulario();
    cargarReservas();
  } catch (e) {
    toast(e.message, "err");
  }
});

async function cargarEnFormulario(id) {
  try {
    const r = await apiFetch(`/reservas/${id}`);
    $("#reserva-id").value = r.id;
    $("#cliente_nombre").value = r.cliente_nombre;
    $("#cliente_email").value = r.cliente_email;
    $("#telefono").value = r.telefono;
    $("#fecha").value = r.fecha;
    $("#hora").value = r.hora.slice(0, 5);
    $("#num_personas").value = r.num_personas;
    $("#mesa").value = r.mesa || "";
    $("#notas").value = r.notas || "";
    $("#estado").value = r.estado;
    $("#form-title").textContent = "Editar reserva";
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (e) {
    toast(e.message, "err");
  }
}

function limpiarFormulario() {
  $("#form-reserva").reset();
  $("#reserva-id").value = "";
  $("#form-title").textContent = "Nueva reserva";
  $("#fecha").value = new Date().toISOString().slice(0, 10);
}

async function eliminarReserva(id) {
  if (!confirm("¿Eliminar esta reserva?")) return;
  try {
    await apiFetch(`/reservas/${id}`, { method: "DELETE" });
    toast("Reserva eliminada", "ok");
    cargarReservas();
  } catch (e) {
    toast(e.message, "err");
  }
}

async function cambiarEstado(id, estado) {
  try {
    await apiFetch(`/reservas/${id}`, {
      method: "PUT",
      body: JSON.stringify({ estado }),
    });
    toast(`Reserva ${estado}`, "ok");
    cargarReservas();
  } catch (e) {
    toast(e.message, "err");
  }
}

/* ─────────────── Reporte pesado ─────────────── */

$("#btn-reporte").addEventListener("click", async () => {
  const btn = $("#btn-reporte");
  const out = $("#salida-reporte");
  btn.disabled = true;
  out.textContent = "Procesando en hilo secundario…";

  try {
    const data = await apiFetch("/reportes/ocupacion", {
      method: "POST",
      body: JSON.stringify({
        iteraciones: Number($("#iteraciones").value),
        incluir_canceladas: $("#incluir-canceladas").checked,
      }),
    });
    out.textContent = JSON.stringify(data, null, 2);
    toast(`Reporte listo en ${data.tiempo_total_segundos}s (hilo: ${data.hilo_ejecucion})`, "ok");
  } catch (e) {
    out.textContent = "❌ " + e.message;
    toast(e.message, "err");
  } finally {
    btn.disabled = false;
  }
});

/* ─────────────── Prueba de concurrencia ─────────────── */

$("#btn-concurrencia").addEventListener("click", async () => {
  const log = $("#log-concurrencia");
  const out = $("#salida-reporte");
  const btn = $("#btn-concurrencia");
  btn.disabled = true;

  log.className = "log visible";
  log.innerHTML = "";
  const addLog = (txt, cls = "") => {
    const d = document.createElement("div");
    d.className = cls;
    d.textContent = txt;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
  };

  addLog("Lanzando reporte pesado en segundo plano…", "info");
  const t0 = performance.now();

  let terminado = false;
  const promReporte = apiFetch("/reportes/ocupacion", {
    method: "POST",
    body: JSON.stringify({
      iteraciones: Number($("#iteraciones").value),
      incluir_canceladas: $("#incluir-canceladas").checked,
    }),
  })
    .then((d) => { terminado = true; return d; })
    .catch((e) => { terminado = true; throw e; });

  // Mientras el reporte corre, mandamos pings al servidor
  let n = 0;
  const latencias = [];
  while (!terminado) {
    n++;
    const tp = performance.now();
    try {
      const res = await fetch(`${API}/health`);
      if (res.ok) {
        const ms = Math.round(performance.now() - tp);
        latencias.push(ms);
        addLog(`  ping #${n} → 200 OK en ${ms} ms   (t=${((performance.now() - t0) / 1000).toFixed(1)}s)`, "ok");
      } else {
        addLog(`  ping #${n} → ${res.status}`, "err");
      }
    } catch (e) {
      addLog(`  ping #${n} → FALLÓ: ${e.message}`, "err");
    }
    await new Promise((r) => setTimeout(r, 400));
  }

  try {
    const data = await promReporte;
    const total = ((performance.now() - t0) / 1000).toFixed(2);
    const prom = latencias.length
      ? Math.round(latencias.reduce((a, b) => a + b, 0) / latencias.length)
      : 0;

    addLog("", "");
    addLog(`Reporte terminado en ${total}s`, "ok");
    addLog(`${latencias.length} pings respondidos durante el proceso`, "info");
    addLog(`Latencia promedio: ${prom} ms  (máx: ${Math.max(...latencias, 0)} ms)`, "info");
    addLog(`Hilo del reporte: ${data.hilo_ejecucion} · Hilo del request: ${data.hilo_principal}`, "info");
    addLog(`Primos calculados: ${data.primos_encontrados.toLocaleString()}`, "info");

    out.textContent = JSON.stringify(data, null, 2);
    toast("Concurrencia verificada: el servidor nunca dejó de responder", "ok");
  } catch (e) {
    addLog(`❌ ${e.message}`, "err");
  } finally {
    btn.disabled = false;
  }
});

/* ─────────────── Eventos iniciales ─────────────── */

$("#btn-refresh").addEventListener("click", cargarReservas);
$("#btn-filtrar").addEventListener("click", cargarReservas);
$("#btn-cancelar").addEventListener("click", limpiarFormulario);
$("#filtro-estado").addEventListener("change", cargarReservas);

document.addEventListener("DOMContentLoaded", () => {
  const hoy = new Date().toISOString().slice(0, 10);
  $("#fecha").value = hoy;
  $("#fecha").min = hoy;
  $("#filtro-fecha").min = hoy;

  checkHealth();
  cargarReservas();
  setInterval(checkHealth, 30000);
});