(function () {
  const fmt = (n) => {
    const sign = n < 0 ? "-" : "";
    return sign + "$" + Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  let winChart;
  let balanceChart;
  let selectedAgentId = null;

  function tagClass(tag) {
    return "tag-" + (tag || "info");
  }

  function render(data) {
    document.getElementById("balance").textContent = fmt(data.balance);
    document.getElementById("started-at").textContent = `started at ${fmt(data.starting_balance)}`;
    document.getElementById("subscription").textContent = fmt(data.subscription);
    document.getElementById("subscription-hint").textContent = `paid • next in ${data.subscription_days} days`;
    const pnlEl = document.getElementById("pnl");
    pnlEl.textContent = (data.pnl >= 0 ? "+" : "") + fmt(data.pnl);
    pnlEl.className = "value " + (data.pnl >= 0 ? "positive" : "negative");
    document.getElementById("pnl-pct").textContent = `${data.pnl_pct >= 0 ? "+" : ""}${data.pnl_pct}% on starting stack`;
    document.getElementById("task-count").textContent = data.task_count.toLocaleString();
    document.getElementById("fees").textContent = `fees ${fmt(data.total_fees)}`;
    document.getElementById("wins").textContent = `${data.win_rate.wins} wins`;
    document.getElementById("losses").textContent = `${data.win_rate.losses} losses`;
    document.getElementById("closed").textContent = `${data.win_rate.closed} closed`;
    document.getElementById("win-rate").textContent = `${data.win_rate.rate}%`;
    document.getElementById("session-timer").textContent = `${data.session_timer} / 22H`;
    document.getElementById("daily-pct").textContent = `${data.daily_target_pct}%`;
    document.getElementById("daily-bar").style.width = `${data.daily_progress_pct}%`;

    const pill = document.getElementById("live-pill");
    const liveText = document.getElementById("live-text");
    if (data.kill_switch) {
      pill.classList.add("off");
      liveText.textContent = "HALTED";
    } else {
      pill.classList.remove("off");
      liveText.textContent = data.paper_mode ? "PAPER" : "LIVE";
    }
    document.getElementById("mode-label").textContent = data.paper_mode ? "PAPER TRADING MODE" : "TRADING MODE";

    const tokenWrap = document.getElementById("token-statuses");
    tokenWrap.innerHTML = (data.token_statuses || []).map((t) => {
      const dotColor = t.is_positive ? "var(--green)" : "var(--red)";
      return `<div class="token-row"><span class="sym"><span class="status-dot" style="background:${dotColor}"></span>$${t.symbol}</span><span class="detail">${t.detail || t.state}</span></div>`;
    }).join("");

    const log = document.getElementById("activity-log");
    log.innerHTML = (data.activity || []).map((a) => {
      const time = new Date(a.created_at).toLocaleTimeString();
      return `<div class="log-line"><span class="${tagClass(a.tag)}">[${String(a.tag).toUpperCase()}]</span> ${time} ${a.message}</div>`;
    }).join("");

    const agentsRow = document.getElementById("agents-row");
    agentsRow.innerHTML = (data.agents || []).map((a) => {
      const running = a.status === "running";
      return `<div class="glass agent-card ${running ? "running" : ""}" data-agent-id="${a.id}" style="--accent:${a.color}">
        <div class="pill" style="background:${a.color}22;color:${a.color}">${running ? "RUN" : "STOP"}</div>
        <div class="mini-bot"></div>
        <div class="name">${a.name}</div>
      </div>`;
    }).join("");

    agentsRow.querySelectorAll(".agent-card").forEach((card) => {
      card.addEventListener("click", async () => {
        const id = card.dataset.agentId;
        const isRunning = card.classList.contains("running");
        const url = isRunning ? `/api/agents/${id}/stop/` : `/api/agents/${id}/start/`;
        await fetch(url, { method: "POST" });
        poll();
      });
    });

    document.getElementById("positions-body").innerHTML = (data.open_positions || []).map((p) => {
      const live = data.live_prices[p.symbol];
      return `<tr><td>$${p.symbol}</td><td>${p.agent__name}</td><td>${Number(p.entry_price).toFixed(6)}</td><td>${fmt(p.cost_basis_usd)}</td><td>${live ? live.toFixed(6) : "—"}</td></tr>`;
    }).join("") || `<tr><td colspan="5" class="muted">No open positions</td></tr>`;

    document.getElementById("executions-body").innerHTML = (data.recent_executions || []).map((e) =>
      `<tr><td>$${e.order__symbol}</td><td>${Number(e.quantity).toFixed(2)}</td><td>${Number(e.fill_price).toFixed(6)}</td><td>${fmt(e.fee_usd)}</td></tr>`
    ).join("") || `<tr><td colspan="4" class="muted">No executions yet</td></tr>`;

    document.getElementById("trades-body").innerHTML = (data.recent_trades || []).map((t) =>
      `<tr><td>$${t.symbol}</td><td class="${t.is_win ? "positive" : "negative"}">${fmt(t.pnl_usd)}</td><td>${t.is_win ? "WIN" : "LOSS"}</td></tr>`
    ).join("") || `<tr><td colspan="3" class="muted">No closed trades</td></tr>`;

    renderWinChart(data.win_rate);
    renderBalanceChart(data.chart, data.balance);
  }

  function renderWinChart(wr) {
    const ctx = document.getElementById("win-chart");
    const wins = wr.wins || 0;
    const losses = wr.losses || 0;
    const data = wins + losses > 0 ? [wins, losses] : [1, 0];
    if (winChart) winChart.destroy();
    winChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Wins", "Losses"],
        datasets: [{ data, backgroundColor: ["#3dff9a", "#ff4d8d"], borderWidth: 0 }],
      },
      options: {
        cutout: "72%",
        plugins: { legend: { display: false } },
        animation: false,
      },
    });
  }

  function renderBalanceChart(points, current) {
    const ctx = document.getElementById("balance-chart");
    const labels = points.map((p) => new Date(p.t).toLocaleTimeString());
    const values = points.map((p) => p.v);
    if (balanceChart) balanceChart.destroy();
    balanceChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "Equity",
          data: values,
          borderColor: "#4da3ff",
          backgroundColor: "rgba(77,163,255,0.12)",
          fill: true,
          tension: 0.35,
          pointRadius: 0,
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#8b93a7", maxTicksLimit: 6 }, grid: { color: "rgba(255,255,255,0.04)" } },
          y: { ticks: { color: "#8b93a7" }, grid: { color: "rgba(255,255,255,0.04)" } },
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
    await fetch("/api/kill-switch/", { method: "POST", body: "{}" });
    poll();
  });

  render(window.__INITIAL__ || {});
  setInterval(poll, 4000);
})();
