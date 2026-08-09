const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const FALLBACK_ASSETS = [
  "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC",
  "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC", "USDCHF-OTC",
  "USDCAD-OTC", "NZDUSD-OTC",
  "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
];

let assetsCache = [...FALLBACK_ASSETS];
let assetsLoadedOnce = false;

function money(v, currency = "R$") {
  const n = Number(v || 0);
  return `${currency} ${n.toFixed(2).replace(".", ",")}`;
}

function setTab(name) {
  $$(".tab").forEach((el) => el.classList.remove("active"));
  $$(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.tab === name));
  $$(".bn-item").forEach((el) => el.classList.toggle("active", el.dataset.tab === name));
  const tab = document.getElementById(`tab-${name}`);
  if (tab) tab.classList.add("active");
}

$$(".nav-item").forEach((el) => el.addEventListener("click", () => setTab(el.dataset.tab)));
$$(".bn-item").forEach((el) => el.addEventListener("click", () => setTab(el.dataset.tab)));

function fillAssetSelect(assets, selected, forceRebuild = false) {
  const sel = $("#input-asset");
  if (!sel) return;

  if (assets && assets.length) assetsCache = assets.slice();
  const current = selected || sel.value || assetsCache[0] || "EURUSD-OTC";

  if (assetsLoadedOnce && !forceRebuild && sel.options.length > 0) {
    const exists = [...sel.options].some((o) => o.value === current);
    if (!exists) {
      const opt = document.createElement("option");
      opt.value = current;
      opt.textContent = current;
      sel.insertBefore(opt, sel.firstChild);
    }
    if (document.activeElement !== sel) sel.value = current;
    return;
  }

  const list = assetsCache.length ? assetsCache : FALLBACK_ASSETS;
  sel.innerHTML = list.map((a) => `<option value="${a}">${a}</option>`).join("");
  if (![...sel.options].some((o) => o.value === current)) {
    const opt = document.createElement("option");
    opt.value = current;
    opt.textContent = current;
    sel.insertBefore(opt, sel.firstChild);
  }
  sel.value = current;
  assetsLoadedOnce = true;
}

function setIfIdle(id, value) {
  const el = $(id);
  if (!el) return;
  if (document.activeElement === el) return;
  if (el.type === "checkbox") el.checked = !!value;
  else el.value = value ?? "";
}

function renderTrades(list, mountId) {
  const el = document.getElementById(mountId);
  if (!el) return;
  if (!list || !list.length) {
    el.innerHTML = `<p class="muted">Nenhuma operação nesta sessão ainda.</p>`;
    return;
  }
  el.innerHTML = list.map((t) => {
    const dir = (t.direction || "").toUpperCase();
    const tag = dir === "CALL" ? "call" : "put";
    const resClass = t.status === "WIN" ? "win" : t.status === "LOSS" ? "loss" : "";
    return `<div class="trade">
      <span class="tag ${tag}">${dir || "—"}</span>
      <div class="trade-main"><strong>${t.asset || "—"}</strong><small>${t.time || ""} · ${t.strategy || ""}</small></div>
      <div class="trade-result ${resClass}">${t.status || ""} ${money(t.resultado || 0)}</div>
    </div>`;
  }).join("");
}

function renderConfLayer(id, layer) {
  const el = document.getElementById(id);
  if (!el || !layer) return;
  const ok = !!layer.ok;
  const dir = (layer.direction || "").toUpperCase();
  el.className = `conf-item ${ok ? "ok" : "bad"} ${dir === "CALL" ? "call-dir" : dir === "PUT" ? "put-dir" : ""}`;
  el.querySelector(".conf-mark").textContent = ok ? "✓" : "○";
  el.querySelector("strong").textContent = layer.label || id;
  el.querySelector("small").textContent = ok ? `${dir} · TF ${layer.tf}s` : `Sem tendência · TF ${layer.tf || "—"}s`;
}

function renderConfluence(conf) {
  if (!conf) {
    ["conf-nano", "conf-micro", "conf-macro"].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.className = "conf-item bad";
      el.querySelector(".conf-mark").textContent = "○";
      el.querySelector("small").textContent = "Aguardando...";
    });
    if ($("#conf-summary")) $("#conf-summary").textContent = "Ligue o robô para ver a confluência.";
    return;
  }
  renderConfLayer("conf-nano", conf.nano);
  renderConfLayer("conf-micro", conf.micro);
  renderConfLayer("conf-macro", conf.macro);
  const summary = $("#conf-summary");
  if (!summary) return;
  if (conf.aligned && conf.direction) {
    summary.textContent = `✓ Alinhado em ${conf.direction} — pronto para entrada`;
    summary.style.color = "#047857";
  } else {
    summary.textContent = "Aguardando as 3 tendências na mesma direção...";
    summary.style.color = "";
  }
}

function fillSettingsForm(data) {
  fillAssetSelect(null, data.asset, false);
  const acc = (data.account || "PRACTICE").toUpperCase();
  setIfIdle("#input-account", acc === "REAL" ? "REAL" : "PRACTICE");
  setIfIdle("#input-valor", data.valor_entrada);
  setIfIdle("#input-expiracao", data.expiracao);
  setIfIdle("#input-timeframe", data.timeframe);
  setIfIdle("#input-stop-win", data.stop_win);
  setIfIdle("#input-stop-loss", data.stop_loss);
  setIfIdle("#input-min-velas", data.min_velas);
  setIfIdle("#input-ema-fast", data.ema_rapida);
  setIfIdle("#input-ema-slow", data.ema_lenta);
  setIfIdle("#input-micro", data.micro_mult);
  setIfIdle("#input-macro", data.macro_mult);
  setIfIdle("#input-ema-filter", data.usar_filtro_ema);
  setIfIdle("#input-confluencia", data.exigir_confluencia);
  setIfIdle("#input-martingale", data.usar_martingale);
  setIfIdle("#input-mg-levels", data.niveis_martingale);
  setIfIdle("#input-mg-factor", data.fator_martingale);
  setIfIdle("#input-soros", data.usar_soros);
  setIfIdle("#input-soros-levels", data.niveis_soros);
}

async function refresh() {
  try {
    const res = await fetch("/api/status", { credentials: "same-origin" });
    if (res.status === 401) { window.location.href = "/login"; return; }
    const data = await res.json();

    $("#greeting").textContent = data.user_name ? `Olá, ${data.user_name}` : "Olá";
    $("#balance").textContent = money(data.balance, data.currency || "R$");
    $("#account-badge").textContent = data.account === "REAL" ? "REAL" : "DEMO";

    const running = !!data.bot_running;
    const connected = !!data.connected;
    $("#bot-toggle").checked = running;
    $("#bot-title").textContent = running ? "Robô Ativo" : "Robô Offline";
    $("#bot-sub").textContent = `Estratégia ${data.strategy || "—"}`;
    $("#bot-asset").textContent = data.asset || "—";

    $("#profit").textContent = money(data.lucro_dia, data.currency || "R$");
    $("#profit").className = data.lucro_dia >= 0 ? "pos" : "neg";
    $("#winrate").textContent = `${data.win_rate || 0}%`;
    $("#cfg-stop-win").textContent = money(data.stop_win || 0, data.currency || "R$");
    $("#cfg-stop-loss").textContent = money(data.stop_loss || 0, data.currency || "R$");
    if ($("#server-time")) $("#server-time").textContent = data.server_time || "—";

    $("#conn-pill").textContent = connected ? "• Conectado" : "• Offline";
    $("#conn-pill").classList.toggle("on", connected);
    $("#status-dot").classList.toggle("on", connected);

    const signal = data.last_signal;
    const box = $("#signal-box");
    if (signal && signal.direction && signal.active !== false) {
      box.className = `signal-box ${signal.direction.toLowerCase()}`;
      $("#signal-dir").textContent = signal.direction;
      $("#signal-meta").textContent = `${signal.asset || ""} · ${signal.time || ""} · ${signal.reason || ""}`;
    } else {
      box.className = "signal-box idle";
      $("#signal-dir").textContent = "—";
      $("#signal-meta").textContent = "Aguardando mercado";
    }
    $("#live-msg").textContent = data.last_message || "Monitorando...";
    renderConfluence(data.confluence);
    fillSettingsForm(data);

    const trades = data.trades || [];
    if ($("#history-count")) $("#history-count").textContent = `${trades.length} ops`;
    renderTrades(trades.slice(0, 8), "trades-home");
    renderTrades(trades, "trades-history");
  } catch (e) {
    $("#live-msg").textContent = "Sem conexão com a API";
  }
}

$("#bot-toggle").addEventListener("change", async (e) => {
  const on = e.target.checked;
  try {
    const res = await fetch(on ? "/api/bot/start" : "/api/bot/stop", { method: "POST", credentials: "same-origin" });
    if (res.status === 401) { window.location.href = "/login"; return; }
    const data = await res.json();
    if (!data.ok) { e.target.checked = !on; alert(data.message || "Falha"); }
    setTimeout(refresh, 800);
  } catch { e.target.checked = !on; alert("Erro ao falar com a API"); }
});

const saveBtn = $("#save-settings");
if (saveBtn) {
  saveBtn.addEventListener("click", async () => {
    const payload = {
      account: $("#input-account").value,
      asset: $("#input-asset").value,
      valor_entrada: Number($("#input-valor").value),
      expiracao: Number($("#input-expiracao").value),
      timeframe: Number($("#input-timeframe").value),
      stop_win: Number($("#input-stop-win").value),
      stop_loss: Number($("#input-stop-loss").value),
      min_velas: Number($("#input-min-velas").value),
      ema_rapida: Number($("#input-ema-fast").value),
      ema_lenta: Number($("#input-ema-slow").value),
      micro_mult: Number($("#input-micro").value),
      macro_mult: Number($("#input-macro").value),
      usar_filtro_ema: $("#input-ema-filter").checked,
      exigir_confluencia: $("#input-confluencia").checked,
      usar_martingale: $("#input-martingale").checked,
      niveis_martingale: Number($("#input-mg-levels").value),
      fator_martingale: Number($("#input-mg-factor").value),
      usar_soros: $("#input-soros").checked,
      niveis_soros: Number($("#input-soros-levels").value),
    };

    const msg = $("#settings-msg");
    saveBtn.disabled = true;
    saveBtn.textContent = "Salvando...";
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) msg.textContent = data.detail || data.message || "Erro ao salvar";
      else { msg.textContent = data.message || "Configurações salvas."; refresh(); }
    } catch { msg.textContent = "Falha de conexão"; }
    finally { saveBtn.disabled = false; saveBtn.textContent = "Salvar configurações"; }
  });
}

const fetchBtn = $("#btn-fetch-assets");
if (fetchBtn) {
  fetchBtn.addEventListener("click", async () => {
    const msg = $("#assets-msg");
    fetchBtn.disabled = true;
    fetchBtn.textContent = "Buscando...";
    msg.textContent = "";
    try {
      const res = await fetch("/api/assets", { credentials: "same-origin" });
      const data = await res.json();
      const list = data.assets && data.assets.length ? data.assets : FALLBACK_ASSETS;
      fillAssetSelect(list, $("#input-asset").value, true);
      if (data.source === "live") {
        const otc = data.otc_count ?? list.filter((a) => a.includes("-OTC")).length;
        const normal = data.normal_count ?? (list.length - otc);
        msg.textContent = `${data.count} abertos · OTC: ${otc} · Normal: ${normal}`;
      } else {
        msg.textContent = `Lista padrão (${list.length}). ${data.warning || ""}`;
      }
    } catch {
      fillAssetSelect(FALLBACK_ASSETS, $("#input-asset").value, true);
      msg.textContent = "Falha na busca. Usando lista padrão.";
    } finally {
      fetchBtn.disabled = false;
      fetchBtn.textContent = "Buscar ativos abertos";
    }
  });
}

async function logout() {
  await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
  window.location.href = "/login";
}
$("#logout-btn")?.addEventListener("click", logout);
$("#logout-btn-mobile")?.addEventListener("click", logout);

fillAssetSelect(FALLBACK_ASSETS, "EURUSD-OTC", true);
refresh();
setInterval(refresh, 3000);
