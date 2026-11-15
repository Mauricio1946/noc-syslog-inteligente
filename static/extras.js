// Pestañas adicionales (Corte 3). Usa las utilidades de index.html (h, api, table, fmt, msg, canOps...).
const COL_ALR = {"Crítica": "#7b0000", "Alta": "#d32f2f", "Media": "#ef6c00", "Baja": "#607d8b"};

async function vAlr() {
  await loadDevs();
  const lista = h("div", {className: "scroll"});

  async function cargar() {
    const al = await api("/api/alerts/");
    lista.replaceChildren(table(
      ["#", "Última vez (Bogotá)", "Tipo", "Severidad", "IP origen", "Equipo", "Detalle", "Veces", "Estado", "Aviso", ""],
      al.map(a => h("tr", {},
        h("td", {}, a.id),
        h("td", {}, fmt(a.last_seen)),
        h("td", {}, a.kind),
        h("td", {}, h("span", {className: "sev", style: "background:" + (COL_ALR[a.severity] || "#607d8b")}, a.severity)),
        h("td", {}, a.source_ip),
        h("td", {className: a.device_id ? "" : "bad"}, a.device_id ? devName(a.device_id) : "DESCONOCIDO"),
        h("td", {}, a.detail || ""),
        h("td", {}, "x" + a.count),
        h("td", {}, a.status + (a.acknowledged_by ? " (" + a.acknowledged_by + ")" : "")),
        h("td", {}, a.notified || ""),
        h("td", {}, (canOps() && a.status === "ABIERTA")
          ? h("button", {className: "act", textContent: "Reconocer", onclick: async () => {
              try { await jsend("/api/alerts/" + a.id + "/ack", "POST", {}); await cargar(); } catch (e) { msg(e); }
            }})
          : "")
      ))));
  }

  main.replaceChildren(
    h("div", {className: "box"}, h("b", {}, "Alertas de seguridad "),
      h("button", {className: "act", textContent: "Actualizar", onclick: () => cargar().catch(msg)}), h("br"),
      h("small", {className: "hint"},
        "Generadas por las reglas del módulo de defensa (los logs se tratan como datos no confiables). " +
        "Aviso: TELEGRAM = enviado; SIMULADA = sin Telegram configurado; ERROR = no se pudo enviar.")),
    lista);
  await cargar();
}

window.EXTRA_VIEWS = {alr: ["Alertas", vAlr]};