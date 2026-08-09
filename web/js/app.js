const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

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

function renderTrades(list, mountId) {
  const el = document.getElementById(mountId);
  if (!el) return;
  if (!list || !list.length) {
    el.innerHTML = `<p class="muted">Nenhuma operação nesta sessão ainda.</p>`;
    return;
  }
  el.innerHTML = list
    .map((t) => {
      const dir = (t.direction || "").toUpperCase();
      const tag = dir === "CALL" ? "call" : "put";
      const resClass = t.status === "WIN" ? "win" : t.status === "LOSS" ? "loss" : "";
      const resVal = money(t.resultado || 0);
      return `
        <div class="trade">
          <span class="tag ${tag}">${dir || "—"}</span>
          <div class="trade-main">
            <strong>${t.asset || "—"}</strong>
            <small>${t.time || ""} · ${t.strategy || ""}</small>
          </div>
          <div class="trade-result ${resClass}">${t.status || ""} ${resVal}</div>
        </div>`;
    })
    .join("");
}

function renderConfLayer(id, layer) {
  const el = document.getElementById(id);
  if (!el || !layer) return;
  const ok = !!layer.ok;
  const dir = (layer.direction || "").toUpperCase();
  el.className = `conf-item ${ok ? "ok" : "bad"} ${dir === "CALL" ? "call-dir" : dir === "PUT" ? "put-dir" : ""}`;
  el.querySelector(".conf-mark").textContent = ok ? "✓" : "○";
  el.querySelector("strong").textContent = layer.label || id.replace("conf-", "");
  el.querySelector("small").textContent = ok
    ? `${dir} · TF ${layer.tf}s`
    : `Sem tendência · TF ${layer.tf || "—"}s`;
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

async function refresh() {
  try {
    const res = await fetch("/api/status", { credentials: "same-origin" });
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }
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

    $("#cfg-strategy").textContent = data.strategy || "—";
    $("#cfg-asset").textContent = data.asset || "—";
    $("#cfg-account").textContent = data.account || "—";
    $("#cfg-tf").textContent = data.timeframe ? `${data.timeframe}s` : "—";

    const sw = Number(data.stop_win || 0);
    const sl = Number(data.stop_loss || 0);
    $("#cfg-stop-win").textContent = money(sw, data.currency || "R$");
    $("#cfg-stop-loss").textContent = money(sl, data.currency || "R$");

    const inWin = $("#input-stop-win");
    const inLoss = $("#input-stop-loss");
    if (inWin && document.activeElement !== inWin) inWin.value = sw || "";
    if (inLoss && document.activeElement !== inLoss) inLoss.value = sl || "";

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
    const res = await fetch(on ? "/api/bot/start" : "/api/bot/stop", {
      method: "POST",
      credentials: "same-origin",
    });
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }
    const data = await res.json();
    if (!data.ok) {
      e.target.checked = !on;
      alert(data.message || "Não foi possível alterar o bot");
    }
    setTimeout(refresh, 800);
  } catch {
    e.target.checked = !on;
    alert("Erro ao falar com a API");
  }
});

const saveBtn = $("#save-stops");
if (saveBtn) {
  saveBtn.addEventListener("click", async () => {
    const stop_win = Number($("#input-stop-win").value);
    const stop_loss = Number($("#input-stop-loss").value);
    const msg = $("#settings-msg");

    if (!stop_win || !stop_loss || stop_win <= 0 || stop_loss <= 0) {
      msg.textContent = "Informe valores válidos (> 0).";
      return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = "Salvando...";
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stop_win, stop_loss }),
      });
      const data = await res.json();
      if (!res.ok) {
        msg.textContent = data.detail || "Erro ao salvar";
      } else {
        msg.textContent = "Stops salvos com sucesso.";
        refresh();
      }
    } catch {
      msg.textContent = "Falha de conexão";
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = "Salvar stops";
    }
  });
}

async function logout() {
  await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
  window.location.href = "/login";
}

const logoutBtn = $("#logout-btn");
if (logoutBtn) logoutBtn.addEventListener("click", logout);
const logoutMobile = $("#logout-btn-mobile");
if (logoutMobile) logoutMobile.addEventListener("click", logout);

refresh();
setInterval(refresh, 3000);
