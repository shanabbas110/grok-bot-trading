(function () {
  const fmt = (n) => {
    const sign = n < 0 ? "-" : "";
    return sign + "$" + Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  let balanceChart;
  let lastBalanceLabel = "";

  function tagClass(tag) {
    return "tag-" + (tag || "info");
  }

  function dotClasses(token) {
    const state = (token.state || "").toLowerCase();
    const detail = (token.detail || "").toUpperCase();
    if (token.is_positive || state === "approved" || state === "trading") return ["on", "on", "on"];
    if (state === "checking" || detail.includes("CHECK")) return ["on", "mid", "off"];
    if (detail.includes("LOCK")) return ["on", "bad", "off"];
    return ["on", "on", "bad"];
  }

  function detailClass(token) {
    const detail = (token.detail || "").toUpperCase();
    if (token.is_positive) return "ok";
    if ((token.state || "") === "checking" || detail.includes("CHECK")) return "wait";
    return "";
  }

  function render(data) {
    document.getElementById("balance").textContent = fmt(data.balance);
    document.getElementById("started-at").textContent = `started at ${fmt(data.starting_balance)}`;
    document.getElementById("subscription").textContent = fmt(data.subscription);
    document.getElementById("subscription-hint").textContent = `paid • next in ${data.subscription_days} days`;

    const pnlEl = document.getElementById("pnl");
    pnlEl.textContent = (data.pnl >= 0 ? "+" : "") + fmt(data.pnl);
    pnlEl.className = "value " + (data.pnl >= 0 ? "positive" : "negative");
    document.getElementById("pnl-card").classList.toggle("negative-pnl", data.pnl < 0);
    document.getElementById("pnl-pct").textContent = `${data.pnl_pct >= 0 ? "+" : ""}${data.pnl_pct}% on starting stack`;

    document.getElementById("task-count").textContent = Number(data.task_count || 0).toLocaleString();
    document.getElementById("fees").textContent = `fees ${fmt(data.total_fees)}`;
    document.getElementById("wins").textContent = `${data.win_rate.wins} wins`;
    document.getElementById("losses").textContent = `${data.win_rate.losses} losses`;
    document.getElementById("closed").textContent = `${data.win_rate.closed} closed`;
    document.getElementById("win-rate").textContent = `${data.win_rate.rate}%`;
    document.getElementById("win-ring").style.setProperty("--pct", data.win_rate.rate || 0);
    document.getElementById("session-timer").textContent = `${data.session_timer} / 22H`;
    document.getElementById("daily-pct").textContent = `${data.daily_target_pct}%`;
    document.getElementById("daily-bar").style.width = `${data.daily_progress_pct}%`;
    document.getElementById("resolved-count").textContent = `${Number(data.win_rate.closed || 0).toLocaleString()} RESOLVED`;

    const pill = document.getElementById("live-pill");
    const liveText = document.getElementById("live-text");
    const killBtn = document.getElementById("kill-switch-btn");
    if (data.kill_switch) {
      pill.classList.add("off");
      liveText.textContent = "HALTED";
      killBtn.classList.add("is-on");
    } else {
      pill.classList.remove("off");
      liveText.textContent = data.paper_mode ? "PAPER" : "LIVE";
      killBtn.classList.remove("is-on");
    }

    const statuses = (data.token_statuses || []).slice(0, 4).reverse();
    document.getElementById("token-statuses").innerHTML = statuses.map((t) => {
      const dots = dotClasses(t).map((c) => `<i class="${c}"></i>`).join("");
      return `<div class="token-row">
        <span class="sym">$${t.symbol}</span>
        <span class="dots">${dots}</span>
        <span class="detail ${detailClass(t)}">${t.detail || t.state}</span>
      </div>`;
    }).join("");

    const lines = (data.activity || []).slice().reverse();
    const log = document.getElementById("activity-log");
    log.innerHTML = lines.map((a) => {
      const tag = String(a.tag || "info").toUpperCase();
      return `<div class="log-line"><span class="tag ${tagClass(a.tag)}">[${tag}]</span>${a.message}</div>`;
    }).join("");
    log.scrollTop = log.scrollHeight;

    const agentsRow = document.getElementById("agents-row");
    agentsRow.innerHTML = (data.agents || []).map((a) => {
      const running = a.status === "running";
      return `<div class="agent-card ${running ? "running" : ""}" data-agent-id="${a.id}" data-running="${running ? "1" : "0"}" style="--accent:${a.color}" role="button" tabindex="0" aria-pressed="${running}">
        <span class="accent"></span>
        <div class="face" aria-hidden="true"><span></span><span></span></div>
        <div class="name">${a.name}</div>
      </div>`;
    }).join("");

    agentsRow.querySelectorAll(".agent-card").forEach((card) => {
      const toggle = async () => {
        const id = card.dataset.agentId;
        const url = card.dataset.running === "1" ? `/api/agents/${id}/stop/` : `/api/agents/${id}/start/`;
        await fetch(url, { method: "POST" });
        poll();
      };
      card.addEventListener("click", toggle);
      card.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          toggle();
        }
      });
    });

    document.getElementById("positions-body").innerHTML = (data.open_positions || []).map((p) => {
      const live = data.live_prices[p.symbol];
      return `<tr><td>$${p.symbol}</td><td>${p.agent__name}</td><td>${Number(p.entry_price).toFixed(6)}</td><td>${fmt(p.cost_basis_usd)}</td><td>${live ? Number(live).toFixed(6) : "—"}</td></tr>`;
    }).join("") || `<tr><td colspan="5" class="hint">No open positions</td></tr>`;

    document.getElementById("executions-body").innerHTML = (data.recent_executions || []).map((e) =>
      `<tr><td>$${e.order__symbol}</td><td>${Number(e.quantity).toFixed(2)}</td><td>${Number(e.fill_price).toFixed(6)}</td><td>${fmt(e.fee_usd)}</td></tr>`
    ).join("") || `<tr><td colspan="4" class="hint">No executions yet</td></tr>`;

    document.getElementById("trades-body").innerHTML = (data.recent_trades || []).map((t) =>
      `<tr><td>$${t.symbol}</td><td class="${t.is_win ? "positive" : "negative"}">${fmt(Number(t.pnl_usd))}</td><td>${t.is_win ? "WIN" : "LOSS"}</td></tr>`
    ).join("") || `<tr><td colspan="3" class="hint">No closed trades</td></tr>`;

    lastBalanceLabel = fmt(data.balance);
    renderBalanceChart(data.chart || [], data.balance);
  }

  function renderBalanceChart(points, current) {
    const canvas = document.getElementById("balance-chart");
    const labels = points.map((p) => p.t);
    const values = points.map((p) => Number(p.v));
    const ctx = canvas.getContext("2d");
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.parentElement.clientHeight || 260);
    gradient.addColorStop(0, "rgba(94, 220, 255, 0.55)");
    gradient.addColorStop(0.45, "rgba(70, 150, 255, 0.16)");
    gradient.addColorStop(1, "rgba(70, 150, 255, 0)");

    const min = values.length ? Math.min(...values) : 0;
    const max = values.length ? Math.max(...values) : 1;
    const pad = Math.max((max - min) * 0.18, 1);

    if (balanceChart) balanceChart.destroy();
    balanceChart = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [{
          data: values,
          borderColor: "#7ee7ff",
          backgroundColor: gradient,
          fill: true,
          tension: 0.42,
          borderWidth: 2.5,
          pointRadius: 0,
          pointHoverRadius: 0,
        }],
      },
      plugins: [{
        id: "glowEndpoint",
        beforeDatasetDraw(chart) {
          chart.ctx.save();
          chart.ctx.shadowColor = "rgba(110, 220, 255, 0.85)";
          chart.ctx.shadowBlur = 16;
        },
        afterDatasetDraw(chart) {
          chart.ctx.restore();
          const meta = chart.getDatasetMeta(0);
          const pt = meta.data[meta.data.length - 1];
          if (!pt) return;
          const c = chart.ctx;
          c.save();
          c.shadowColor = "rgba(126, 231, 255, 0.95)";
          c.shadowBlur = 18;
          c.fillStyle = "#f4feff";
          c.beginPath();
          c.arc(pt.x, pt.y, 5.5, 0, Math.PI * 2);
          c.fill();
          c.shadowBlur = 0;
          c.strokeStyle = "rgba(126, 231, 255, 0.9)";
          c.lineWidth = 6;
          c.globalAlpha = 0.25;
          c.beginPath();
          c.arc(pt.x, pt.y, 11, 0, Math.PI * 2);
          c.stroke();
          c.globalAlpha = 1;
          const label = lastBalanceLabel || fmt(current);
          c.font = "700 13px Outfit, sans-serif";
          c.fillStyle = "#3dff9a";
          c.textAlign = "center";
          c.fillText(label, Math.max(48, pt.x - 8), Math.max(16, pt.y - 16));
          c.restore();
        },
      }],
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: {
          x: { display: false },
          y: {
            min: Math.max(0, min - pad * 0.2),
            max: max + pad,
            ticks: {
              color: "#7e879c",
              font: { family: "IBM Plex Mono", size: 10 },
              maxTicksLimit: 4,
              callback: (v) => "$" + Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 }),
            },
            grid: { display: false },
            border: { display: false },
          },
        },
        animation: false,
      },
    });
  }

  async function poll() {
    try {
      const res = await fetch("/api/dashboard/");
      const data = await res.json();
      render(data);
    } catch (e) {
      console.error(e);
    }
  }

  document.getElementById("kill-switch-btn").addEventListener("click", async () => {
    await fetch("/api/kill-switch/", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    poll();
  });

  render(window.__INITIAL__ || {});
  setInterval(poll, 4000);
})();
