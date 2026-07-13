// Cricket Sentiment Dashboard — Chart.js frontend
const CLASS_COLORS = {
  positive: "#22c55e",
  neutral: "#f59e0b",
  negative: "#ef4444",
};

const state = {
  selectedPlayerId: null,
  activeTab: "overview",
  filters: {
    overview: { positive: true, neutral: true, negative: true },
    chatbot: { positive: true, neutral: true, negative: true },
  },
  // Raw data cached so filters can re-render without re-fetching.
  rankingsData: null, // { overall, rankings }
  playerData: null, // { trend, events, distribution, name }
  chatbotData: null, // { results }
  charts: {
    trend: null,
    doughnut: null,
    chatbotTrend: null,
    chatbotDoughnut: null,
  },
};

function classifyScore(score) {
  if (score > 0.15) return "positive";
  if (score < -0.15) return "negative";
  return "neutral";
}

function psiClass(psi) {
  const cls = classifyScore(psi);
  return cls === "positive" ? "psi-pos" : cls === "negative" ? "psi-neg" : "psi-neu";
}

function distBar(pos, neu, neg) {
  const total = pos + neu + neg || 1;
  const p = (pos / total) * 100;
  const n = (neu / total) * 100;
  const x = (neg / total) * 100;
  return `<span class="dist-bar">
    <span class="p" style="width:${p}%"></span>
    <span class="n" style="width:${n}%"></span>
    <span class="x" style="width:${x}%"></span>
  </span>`;
}

// ---------- Rankings + Player Detail ----------

async function loadRankings() {
  const res = await fetch("/api/rankings");
  state.rankingsData = await res.json();
  renderRankings();

  if (state.selectedPlayerId === null && state.rankingsData.rankings.length > 0) {
    const first = state.rankingsData.rankings[0];
    selectPlayer(first.player_id, first.name);
  }
}

function renderRankings() {
  const data = state.rankingsData;
  if (!data) return;
  const filters = state.filters.overview;

  const visible = data.rankings.filter((r) => filters[classifyScore(r.psi)]);

  // Header stats — recompute from visible rows so the cross-filter drives them.
  const totMentions = visible.reduce((s, r) => s + r.mentions, 0);
  const totPos = visible.reduce((s, r) => s + r.positive, 0);
  const totNeu = visible.reduce((s, r) => s + r.neutral, 0);
  const totNeg = visible.reduce((s, r) => s + r.negative, 0);

  document.getElementById("stat-mentions").textContent = totMentions;
  document.getElementById("stat-players").textContent = visible.length;
  document.getElementById("stat-pos").textContent = filters.positive ? totPos : "–";
  document.getElementById("stat-neu").textContent = filters.neutral ? totNeu : "–";
  document.getElementById("stat-neg").textContent = filters.negative ? totNeg : "–";

  // Dim disabled stat cards for a clearer visual link to the chips.
  document.querySelector("#overall-stats .stat.pos").classList.toggle("dim", !filters.positive);
  document.querySelector("#overall-stats .stat.neu").classList.toggle("dim", !filters.neutral);
  document.querySelector("#overall-stats .stat.neg").classList.toggle("dim", !filters.negative);

  const tbody = document.querySelector("#ranking-table tbody");
  tbody.innerHTML = "";
  if (!visible.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="hint" style="text-align:center;padding:20px;">No players match the current filter.</td></tr>';
    return;
  }
  visible.forEach((row, i) => {
    const tr = document.createElement("tr");
    tr.dataset.playerId = row.player_id;
    if (row.player_id === state.selectedPlayerId) tr.classList.add("selected");
    // Re-rank within the visible set so the # column stays contiguous.
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><strong>${row.name}</strong></td>
      <td>${row.team ?? ""}</td>
      <td>${row.role ?? ""}</td>
      <td class="psi-cell ${psiClass(row.psi)}">${row.psi.toFixed(3)}</td>
      <td>${row.mentions}</td>
      <td>${distBar(
        filters.positive ? row.positive : 0,
        filters.neutral ? row.neutral : 0,
        filters.negative ? row.negative : 0,
      )}</td>
    `;
    tr.addEventListener("click", () => selectPlayer(row.player_id, row.name));
    tbody.appendChild(tr);
  });
}

async function selectPlayer(pid, name) {
  state.selectedPlayerId = pid;
  document.querySelectorAll("#ranking-table tbody tr").forEach((tr) => {
    tr.classList.toggle("selected", Number(tr.dataset.playerId) === pid);
  });
  document.getElementById("detail-title").textContent = `Player Detail — ${name}`;

  const res = await fetch(`/api/player/${pid}/trends?bucket=60`);
  const data = await res.json();
  state.playerData = { ...data, name };
  renderPlayerCharts();
  renderEvents(data.events);
}

function renderPlayerCharts() {
  if (!state.playerData) return;
  renderTrend(state.playerData.trend, state.playerData.events);
  renderDoughnut(state.playerData.distribution);
}

function renderTrend(trend, events) {
  const ctx = document.getElementById("trend-chart");
  const filters = state.filters.overview;

  // Classify each point and hide (null) those whose class is filtered off.
  // Chart.js draws gaps at null values.
  const points = trend.map((p) => {
    const cls = classifyScore(p.score);
    return { x: p.t, y: filters[cls] ? p.score : null, cls };
  });

  const eventPoints = events.map((e) => ({
    x: e.occurred_at,
    y: 0,
    label: `${e.event_type}: ${e.description}`,
  }));

  // Colored overlays per class — only render classes that are toggled on.
  const overlays = ["positive", "neutral", "negative"]
    .filter((cls) => filters[cls])
    .map((cls) => ({
      label: `${cls[0].toUpperCase()}${cls.slice(1)} points`,
      type: "scatter",
      data: trend
        .filter((p) => classifyScore(p.score) === cls)
        .map((p) => ({ x: p.t, y: p.score })),
      backgroundColor: CLASS_COLORS[cls],
      borderColor: CLASS_COLORS[cls],
      pointRadius: 4,
      pointHoverRadius: 6,
    }));

  if (state.charts.trend) state.charts.trend.destroy();
  state.charts.trend = new Chart(ctx, {
    type: "line",
    data: {
      datasets: [
        {
          label: "Sentiment Score",
          data: points,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56, 189, 248, 0.15)",
          fill: true,
          tension: 0.35,
          pointRadius: 0,
          spanGaps: false,
        },
        ...overlays,
        {
          label: "Match Events",
          data: eventPoints,
          type: "scatter",
          borderColor: "#f59e0b",
          backgroundColor: "#f59e0b",
          pointStyle: "triangle",
          pointRadius: 9,
          showLine: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: "time",
          time: { unit: "hour", tooltipFormat: "MMM d, HH:mm" },
          ticks: { color: "#94a3b8" },
          grid: { color: "rgba(148, 163, 184, 0.1)" },
        },
        y: {
          min: -1,
          max: 1,
          ticks: { color: "#94a3b8" },
          grid: { color: "rgba(148, 163, 184, 0.1)" },
          title: { display: true, text: "Sentiment (-1 to +1)", color: "#94a3b8" },
        },
      },
      plugins: {
        legend: { labels: { color: "#e2e8f0" } },
        tooltip: {
          callbacks: {
            label: (c) => {
              if (c.dataset.label === "Match Events") return c.raw.label;
              return `PSI: ${c.parsed.y.toFixed(3)}`;
            },
          },
        },
      },
    },
  });
}

function renderDoughnut(dist) {
  const ctx = document.getElementById("doughnut-chart");
  const filters = state.filters.overview;

  const entries = [
    ["positive", "Positive", dist.positive],
    ["neutral", "Neutral", dist.neutral],
    ["negative", "Negative", dist.negative],
  ].filter(([cls]) => filters[cls]);

  if (state.charts.doughnut) state.charts.doughnut.destroy();
  state.charts.doughnut = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: entries.map(([, label]) => label),
      datasets: [{
        data: entries.map(([, , v]) => v),
        backgroundColor: entries.map(([cls]) => CLASS_COLORS[cls]),
        borderColor: "#1e293b",
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#e2e8f0" } },
      },
    },
  });
}

function renderEvents(events) {
  const ul = document.getElementById("event-list");
  if (!events.length) {
    ul.innerHTML = '<li class="empty">No match events for this player.</li>';
    return;
  }
  ul.innerHTML = events
    .map((e) => {
      const when = new Date(e.occurred_at).toLocaleString();
      return `<li>
        <div><span class="etype">${e.event_type}</span> ${e.description}</div>
        <div class="hint">${when}</div>
      </li>`;
    })
    .join("");
}

// ---------- Chatbot Tab ----------

async function analyzeCommentary() {
  const text = document.getElementById("analyze-text").value.trim();
  const out = document.getElementById("analyze-result");
  if (!text) {
    out.innerHTML = '<div class="hint">Enter some commentary first.</div>';
    return;
  }
  out.innerHTML = '<div class="hint">Scoring…</div>';
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const data = await res.json();
  if (data.error) {
    out.innerHTML = `<div class="hint">Error: ${data.error}</div>`;
    return;
  }
  state.chatbotData = { results: data.results };
  renderAnalyzeResults();
  renderChatbotCharts();
}

function renderAnalyzeResults() {
  const out = document.getElementById("analyze-result");
  if (!state.chatbotData || !state.chatbotData.results.length) {
    out.innerHTML = '<div class="hint">No results yet.</div>';
    return;
  }
  const filters = state.filters.chatbot;
  const visible = state.chatbotData.results.filter((r) => filters[r.label]);
  if (!visible.length) {
    out.innerHTML = '<div class="hint">All classes filtered out.</div>';
    return;
  }
  out.innerHTML = visible
    .map((r) => `
      <div class="result-item">
        <span class="badge ${r.label}">${r.label.toUpperCase()}</span>
        <strong>${r.player ?? "(no player detected)"}</strong>
        — score ${r.score.toFixed(3)}
      </div>`)
    .join("");
}

function renderChatbotCharts() {
  renderChatbotTrend();
  renderChatbotDoughnut();
}

function renderChatbotTrend() {
  const ctx = document.getElementById("chatbot-trend-chart");
  const filters = state.filters.chatbot;
  const results = state.chatbotData?.results ?? [];

  const datasets = ["positive", "neutral", "negative"]
    .filter((cls) => filters[cls])
    .map((cls) => ({
      label: cls[0].toUpperCase() + cls.slice(1),
      data: results
        .map((r, i) => ({ x: i + 1, y: r.score, cls: r.label }))
        .filter((p) => p.cls === cls),
      backgroundColor: CLASS_COLORS[cls],
      borderColor: CLASS_COLORS[cls],
      pointRadius: 6,
      pointHoverRadius: 8,
      showLine: false,
    }));

  if (state.charts.chatbotTrend) state.charts.chatbotTrend.destroy();
  state.charts.chatbotTrend = new Chart(ctx, {
    type: "scatter",
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: "linear",
          ticks: { color: "#94a3b8", stepSize: 1 },
          grid: { color: "rgba(148, 163, 184, 0.1)" },
          title: { display: true, text: "Sentence #", color: "#94a3b8" },
        },
        y: {
          min: -1,
          max: 1,
          ticks: { color: "#94a3b8" },
          grid: { color: "rgba(148, 163, 184, 0.1)" },
          title: { display: true, text: "Score (-1 to +1)", color: "#94a3b8" },
        },
      },
      plugins: {
        legend: { labels: { color: "#e2e8f0" } },
        tooltip: {
          callbacks: {
            label: (c) => {
              const r = results[c.raw.x - 1];
              const who = r?.player ?? "(no player)";
              return `${who}: ${c.parsed.y.toFixed(3)}`;
            },
          },
        },
      },
    },
  });
}

function renderChatbotDoughnut() {
  const ctx = document.getElementById("chatbot-doughnut-chart");
  const filters = state.filters.chatbot;
  const results = state.chatbotData?.results ?? [];

  const counts = { positive: 0, neutral: 0, negative: 0 };
  results.forEach((r) => { counts[r.label] = (counts[r.label] ?? 0) + 1; });

  const entries = [
    ["positive", "Positive"],
    ["neutral", "Neutral"],
    ["negative", "Negative"],
  ].filter(([cls]) => filters[cls]);

  if (state.charts.chatbotDoughnut) state.charts.chatbotDoughnut.destroy();
  state.charts.chatbotDoughnut = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: entries.map(([, label]) => label),
      datasets: [{
        data: entries.map(([cls]) => counts[cls]),
        backgroundColor: entries.map(([cls]) => CLASS_COLORS[cls]),
        borderColor: "#1e293b",
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#e2e8f0" } },
      },
    },
  });
}

// ---------- Tabs & Filters ----------

function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tab);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.dataset.panel === tab);
  });
  // Nudge Chart.js to recalc size when its canvas becomes visible.
  Object.values(state.charts).forEach((c) => c && c.resize());
}

function toggleFilter(scope, cls) {
  state.filters[scope][cls] = !state.filters[scope][cls];
  const bar = document.querySelector(`.filter-bar[data-scope="${scope}"]`);
  bar.querySelector(`.chip[data-filter="${cls}"]`).classList.toggle("active", state.filters[scope][cls]);

  if (scope === "overview") {
    renderRankings();
    renderPlayerCharts();
  } else {
    renderAnalyzeResults();
    renderChatbotCharts();
  }
}

function wireTabs() {
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.addEventListener("click", () => switchTab(b.dataset.tab));
  });
}

function wireFilters() {
  document.querySelectorAll(".filter-bar").forEach((bar) => {
    const scope = bar.dataset.scope;
    bar.querySelectorAll(".chip").forEach((chip) => {
      chip.addEventListener("click", () => toggleFilter(scope, chip.dataset.filter));
    });
  });
}

// ---------- Bootstrap ----------

document.getElementById("refresh-btn").addEventListener("click", loadRankings);
document.getElementById("analyze-btn").addEventListener("click", analyzeCommentary);

wireTabs();
wireFilters();
loadRankings();
setInterval(loadRankings, 30000);
