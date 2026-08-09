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
    el.innerHTML = `<p class="muted">Nenhuma operação ainda.</p>`;
    return;
  }
  el.innerHTML = list
    .slice(0, 12)
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

async function refresh() {
  try {
    const res = await fetch("/api/status");
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

    $("#conn-pill").textContent = connected ? "• Conectado" : "• Offline";
    $("#conn-pill").classList.toggle("on", connected);
    $("#status-dot").classList.toggle("on", connected);

    const signal = data.last_signal;
    const box = $("#signal-box");
    if (signal && signal.direction) {
      box.className = `signal-box ${signal.direction.toLowerCase()}`;
      $("#signal-dir").textContent = signal.direction;
      $("#signal-meta").textContent = `${signal.asset || ""} · ${signal.reason || ""}`;
    } else {
      box.className = "signal-box idle";
      $("#signal-dir").textContent = "—";
      $("#signal-meta").textContent = "Aguardando mercado";
    }
    $("#live-msg").textContent = data.last_message || "—";

    renderTrades(data.trades || [], "trades-home");
    renderTrades(data.trades || [], "trades-history");
  } catch (e) {
    $("#live-msg").textContent = "Sem conexão com a API";
  }
}

$("#bot-toggle").addEventListener("change", async (e) => {
  const on = e.target.checked;
  try {
    const res = await fetch(on ? "/api/bot/start" : "/api/bot/stop", { method: "POST" });
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

refresh();
setInterval(refresh, 3000);
