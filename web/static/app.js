/* valora · lógica de la página. Sin framework: fetch, DOM y unas animaciones. */
(() => {
  "use strict";

  const $ = (sel, raiz = document) => raiz.querySelector(sel);
  const $$ = (sel, raiz = document) => Array.from(raiz.querySelectorAll(sel));
  const pesos = (n) => "$ " + Math.round(n).toLocaleString("es-CO");
  const pesosCortos = (n) => n >= 1e9 ? (n / 1e9).toLocaleString("es-CO", { maximumFractionDigits: 2 }) + " mil M"
    : n >= 1e6 ? (n / 1e6).toLocaleString("es-CO", { maximumFractionDigits: 1 }) + " M"
    : Math.round(n / 1e3).toLocaleString("es-CO") + " mil";

  // ── tema ────────────────────────────────────────────────────────────────
  const raiz = document.documentElement;
  const temaGuardado = (() => { try { return localStorage.getItem("valora-tema"); } catch { return null; } })();
  if (temaGuardado === "oscuro" || (!temaGuardado && matchMedia("(prefers-color-scheme: dark)").matches)) raiz.dataset.tema = "oscuro";
  $("#tema").addEventListener("click", () => {
    const oscuro = raiz.dataset.tema === "oscuro";
    if (oscuro) delete raiz.dataset.tema; else raiz.dataset.tema = "oscuro";
    try { localStorage.setItem("valora-tema", oscuro ? "claro" : "oscuro"); } catch {}
  });

  // ── conteo animado ──────────────────────────────────────────────────────
  function contar(el, hasta, decimales = 0, duracion = 1100) {
    const desde = parseFloat(el.dataset.actual || "0");
    const inicio = performance.now();
    const paso = (t) => {
      const p = Math.min(1, (t - inicio) / duracion);
      const suave = 1 - Math.pow(1 - p, 3);
      const valor = desde + (hasta - desde) * suave;
      el.textContent = valor.toLocaleString("es-CO", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
      if (p < 1) requestAnimationFrame(paso); else el.dataset.actual = String(hasta);
    };
    requestAnimationFrame(paso);
  }
  $$("[data-cuenta]", $("#portada")).forEach((el) => contar(el, parseFloat(el.dataset.cuenta), parseInt(el.dataset.decimales || "0"), 1600));

  // ── formulario ──────────────────────────────────────────────────────────
  const form = $("#formulario");
  const selCiudad = $("#ciudad");
  const inpSector = $("#sector");
  const lista = $("#sugerencias");
  let estrato = 4;
  const comodidades = new Set();
  let sectorElegido = null;

  fetch("/api/ciudades").then((r) => r.json()).then((ciudades) => {
    selCiudad.innerHTML = ciudades.map((c) => `<option value="${c.ciudad}">${c.ciudad} · ${c.anuncios.toLocaleString("es-CO")}</option>`).join("");
  });

  $$("#estrato button").forEach((b) => b.addEventListener("click", () => {
    $$("#estrato button").forEach((x) => x.classList.remove("activa"));
    b.classList.add("activa"); estrato = parseInt(b.dataset.valor);
  }));
  $$("#comodidades button").forEach((b) => b.addEventListener("click", () => {
    b.classList.toggle("activa");
    if (b.classList.contains("activa")) comodidades.add(b.dataset.valor); else comodidades.delete(b.dataset.valor);
  }));
  $$("[data-mas],[data-menos]").forEach((b) => b.addEventListener("click", () => {
    const campo = $("#" + (b.dataset.mas || b.dataset.menos));
    const v = parseInt(campo.value || "0") + (b.dataset.mas ? 1 : -1);
    campo.value = Math.max(parseInt(campo.min), Math.min(parseInt(campo.max), v));
  }));

  // autocompletar sector
  let temporizador, seleccion = -1, sugerencias = [];
  function pintarSugerencias() {
    if (!sugerencias.length) { lista.hidden = true; return; }
    lista.innerHTML = sugerencias.map((s, i) => `<li role="option" data-i="${i}" ${i === seleccion ? 'aria-selected="true"' : ""}>
      <span>${s.sector}</span><small>${s.anuncios} anuncios${s.estrato ? " · estrato " + s.estrato : ""}</small></li>`).join("");
    lista.hidden = false;
  }
  function elegir(i) {
    const s = sugerencias[i]; if (!s) return;
    inpSector.value = s.sector; sectorElegido = s; lista.hidden = true;
    $("#sector-ayuda").textContent = `${s.anuncios} anuncios geolocalizados en ${s.sector}` + (s.estrato ? `, estrato típico ${s.estrato}.` : ".");
  }
  inpSector.addEventListener("input", () => {
    sectorElegido = null; clearTimeout(temporizador);
    temporizador = setTimeout(async () => {
      const q = inpSector.value.trim();
      const r = await fetch(`/api/sectores?ciudad=${encodeURIComponent(selCiudad.value)}&q=${encodeURIComponent(q)}`);
      sugerencias = await r.json(); seleccion = -1; pintarSugerencias();
    }, 160);
  });
  inpSector.addEventListener("focus", () => inpSector.dispatchEvent(new Event("input")));
  inpSector.addEventListener("keydown", (e) => {
    if (lista.hidden) return;
    if (e.key === "ArrowDown") { seleccion = Math.min(sugerencias.length - 1, seleccion + 1); pintarSugerencias(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { seleccion = Math.max(0, seleccion - 1); pintarSugerencias(); e.preventDefault(); }
    else if (e.key === "Enter" && seleccion >= 0) { elegir(seleccion); e.preventDefault(); }
    else if (e.key === "Escape") lista.hidden = true;
  });
  lista.addEventListener("mousedown", (e) => { const li = e.target.closest("li"); if (li) { elegir(parseInt(li.dataset.i)); e.preventDefault(); } });
  document.addEventListener("click", (e) => { if (!e.target.closest(".campo--auto")) lista.hidden = true; });
  selCiudad.addEventListener("change", () => { inpSector.value = ""; sectorElegido = null; $("#sector-ayuda").textContent = "Se resuelve contra los sectores que tienen anuncios geolocalizados."; });

  // ── envío ───────────────────────────────────────────────────────────────
  const boton = $("#valuar"), error = $("#error");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const datos = new FormData(form);
    const entero = (k) => { const v = datos.get(k); return v === "" || v === null ? null : parseInt(v); };
    const cuerpo = {
      ciudad: datos.get("ciudad"), sector: (datos.get("sector") || "").trim() || null, tipo: datos.get("tipo"),
      area_m2: parseFloat(datos.get("area_m2")), habitaciones: entero("habitaciones"), banos: entero("banos"),
      parqueaderos: entero("parqueaderos"), estrato, antiguedad: datos.get("antiguedad") || null,
      piso: entero("piso"), administracion: entero("administracion"), comodidades: Array.from(comodidades),
    };
    if (!(cuerpo.area_m2 > 15)) { mostrarError("Necesito el área construida en metros cuadrados."); return; }
    error.hidden = true; boton.classList.add("espera"); boton.disabled = true;
    $("#portada").hidden = true; $("#resultado").hidden = true; $("#esqueleto").hidden = false;
    try {
      const r = await fetch("/api/valuar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(typeof d.detail === "string" ? d.detail : "No pude valuar con esos datos."); }
      const datosRespuesta = await r.json();
      pintarResultado(datosRespuesta, cuerpo);
    } catch (err) {
      mostrarError(err.message || "Algo falló al hablar con el modelo.");
      $("#esqueleto").hidden = true; $("#portada").hidden = false;
    } finally { boton.classList.remove("espera"); boton.disabled = false; }
  });
  function mostrarError(msg) { error.textContent = msg; error.hidden = false; }

  // ── resultado ───────────────────────────────────────────────────────────
  let respuesta = null, entradaActual = null, opActiva = "venta";
  function pintarResultado(d, entrada) {
    respuesta = d; entradaActual = entrada;
    const a = d.avaluo, ctx = a.contexto;
    $("#esqueleto").hidden = true; $("#resultado").hidden = false;
    $("#resultado").style.animation = "none"; void $("#resultado").offsetWidth; $("#resultado").style.animation = "";

    const tipo = { apartaestudio: "Apartaestudio", apartamento: "Apartamento", casa: "Casa" }[entrada.tipo];
    $("#res-kicker").textContent = "Avalúo";
    $("#res-titulo").textContent = `${tipo} de ${entrada.area_m2} m² en ${ctx.sector || "sector sin especificar"}, ${ctx.ciudad}`;
    $("#res-contexto").textContent = ctx.sector_conocido
      ? `Estrato ${ctx.estrato_usado} (${ctx.origen_estrato}) · ${ctx.n_comparables_sector} anuncios geolocalizados en el sector · a ${ctx.distancia_centro_km} km del centro.`
      : `Sector no visto por el modelo: la coordenada cae en el ${ctx.origen_coordenada} y el estrato es ${ctx.estrato_usado} (${ctx.origen_estrato}). Tomá el rango con más cautela.`;

    for (const op of ["venta", "arriendo"]) {
      const r = a[op];
      contar($("#" + op + "-cifra"), r.estimado);
      $("#" + op + "-m2").textContent = pesos(r.precio_m2);
      $("#" + op + "-bajo").textContent = pesosCortos(r.rango[0]);
      $("#" + op + "-alto").textContent = pesosCortos(r.rango[1]);
      const marca = $("#" + op + "-marca");
      const pos = (r.estimado - r.rango[0]) / Math.max(1, r.rango[1] - r.rango[0]);
      marca.style.left = "50%";
      requestAnimationFrame(() => requestAnimationFrame(() => { marca.style.left = (8 + pos * 84) + "%"; }));
    }
    $("#rentabilidad").innerHTML = `Si se comprara al estimado y se arrendara al canon estimado, la rentabilidad bruta anual sería de <b>${a["rentabilidad_bruta_anual_%"].toLocaleString("es-CO")} %</b>: doce cánones sobre el precio de venta, antes de administración, impuestos y vacancia.`;

    $$(".conmutador button").forEach((b) => { b.onclick = () => { opActiva = b.dataset.op; $$(".conmutador button").forEach((x) => x.classList.toggle("activa", x === b)); pintarZona(); }; });
    pintarZona();
    pintarMapa();
    $("#pie-origen").textContent = `Coordenada resuelta por ${ctx.origen_coordenada}; estrato por ${ctx.origen_estrato}. Zona de comparación: ${d.zona.radio_km ? d.zona.radio_km + " km alrededor" : "el sector completo"}.`;
    $("#resultado").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function pintarZona() {
    const z = respuesta.zona[opActiva], a = respuesta.avaluo[opActiva];
    $(".zona").dataset.op = opActiva;
    const lectura = $("#zona-lectura");
    if (!z.n_zona) { lectura.textContent = "No hay anuncios de este tipo publicados alrededor para comparar."; $("#histograma").innerHTML = ""; $("#histograma-ejes").innerHTML = ""; pintarComparables(z); return; }
    const etiqueta = opActiva === "venta" ? "venta" : "arriendo";
    lectura.innerHTML = `Hay <b>${z.n_zona}</b> anuncios de ${etiqueta} de este tipo en la zona, con una mediana de <b>${pesos(z.mediana_m2)}</b> por m² (la mitad entre ${pesosCortos(z.p25_m2)} y ${pesosCortos(z.p75_m2)}). Tu avalúo, a <b>${pesos(a.precio_m2)}</b> por m², queda por encima del <b>${z.percentil_avaluo} %</b> de ellos${z.n_parecidos ? `; ${z.n_parecidos} tienen un área parecida y su mediana de precio es ${pesos(z.mediana_precio_parecidos)}.` : "."}`;
    const h = z.histograma_m2, cont = $("#histograma");
    if (!h) { cont.innerHTML = ""; $("#histograma-ejes").innerHTML = ""; pintarComparables(z); return; }
    const max = Math.max(...h.conteos);
    cont.innerHTML = h.conteos.map((c, i) => `<span style="height:${Math.max(3, c / max * 100)}%; animation-delay:${i * 45}ms" class="${i === h.barra_avaluo ? "avaluo-aqui" : ""}" title="${c} anuncios entre ${pesosCortos(h.limites[i])} y ${pesosCortos(h.limites[i + 1])} por m²"></span>`).join("");
    $("#histograma-ejes").innerHTML = `<span>${pesosCortos(h.limites[0])} / m²</span><span>mediana ${pesosCortos(z.mediana_m2)}</span><span>${pesosCortos(h.limites[h.limites.length - 1])} / m²</span>`;
    pintarComparables(z);
  }

  function pintarComparables(z) {
    const cont = $("#comparables");
    if (!z.comparables.length) { cont.innerHTML = `<li class="comparables__vacio">No hay anuncios con un área parecida cerca. El avalúo se apoya en el modelo, no en vecinos directos.</li>`; return; }
    cont.innerHTML = z.comparables.map((c, i) => `<li><a class="comparable" href="${c.url}" target="_blank" rel="noopener" style="animation-delay:${i * 60}ms">
      <p class="comparable__precio">${pesos(c.precio)}</p>
      <p class="comparable__m2">${pesos(c.precio_m2)} / m²</p>
      <p class="comparable__datos"><span>${c.area_m2} m²</span>${c.habitaciones != null ? `<span>${c.habitaciones} hab</span>` : ""}${c.banos != null ? `<span>${c.banos} baños</span>` : ""}${c.estrato ? `<span>estrato ${c.estrato}</span>` : ""}${c.antiguedad ? `<span>${c.antiguedad.toLowerCase()}</span>` : ""}</p>
      <p class="comparable__pie"><span>${c.sector || ""}</span><span>${c.distancia_km != null ? "a " + c.distancia_km + " km" : ""}</span></p>
    </a></li>`).join("");
    if (mapa) pintarMarcadores();
  }

  // ── mapa ────────────────────────────────────────────────────────────────
  let mapa = null, capaTiles = null, capaMarcadores = null;
  function pintarTiles() {
    if (capaTiles) capaTiles.remove();
    // Teselas de OpenStreetMap; en modo oscuro se invierten por CSS (ver app.css).
    capaTiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom: 19,
    }).addTo(mapa);
  }
  function pintarMapa() {
    const centro = respuesta.zona.centro;
    if (!mapa) { mapa = L.map("mapa", { scrollWheelZoom: false, zoomControl: true }); pintarTiles(); }
    mapa.setView([centro.lat, centro.lon], 15);
    setTimeout(() => mapa.invalidateSize(), 60);
    pintarMarcadores();
    const ctx = respuesta.avaluo.contexto;
    $("#mapa-nota").textContent = ctx.origen_coordenada === "sector" ? "El punto grande es el centro del sector según los anuncios geolocalizados; los pequeños, los comparables publicados." : ctx.origen_coordenada === "usuario" ? "El punto grande es la coordenada que diste; los pequeños, los comparables publicados." : "Sin sector, el punto grande es el centro de la ciudad: los comparables son orientativos.";
  }
  function pintarMarcadores() {
    if (capaMarcadores) capaMarcadores.remove();
    capaMarcadores = L.layerGroup().addTo(mapa);
    const centro = respuesta.zona.centro;
    L.marker([centro.lat, centro.lon], { icon: L.divIcon({ className: "", html: '<div class="marcador-inmueble"></div>', iconSize: [18, 18], iconAnchor: [9, 9] }), zIndexOffset: 1000 }).addTo(capaMarcadores);
    for (const c of respuesta.zona[opActiva].comparables) {
      if (c.lat == null) continue;
      L.marker([c.lat, c.lon], { icon: L.divIcon({ className: "", html: `<div class="marcador-comparable ${opActiva}"></div>`, iconSize: [11, 11], iconAnchor: [5, 5] }) })
        .bindPopup(`<b>${pesos(c.precio)}</b><br>${c.area_m2} m² · ${pesos(c.precio_m2)}/m²${c.estrato ? " · estrato " + c.estrato : ""}<br><a href="${c.url}" target="_blank" rel="noopener">ver anuncio</a>`)
        .addTo(capaMarcadores);
    }
  }
})();
