const API = "http://127.0.0.1:5000";
let state = null;

async function newGame() {
  const rows = parseInt(document.getElementById("rows").value);
  const cols = parseInt(document.getElementById("cols").value);
  const res = await fetch(`${API}/new_game`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rows, cols })
  });
  state = await res.json();
  state.safe_cells = state.safe_cells || [];
  state.revealed_pits = [];
  state.revealed_wumpus = null;
  clearBanner();
  document.getElementById("log").innerHTML = "";
  renderGrid();
  updatePercepts(state.percepts);
  updateMetrics(state.inference_steps, state.visited.length, state.safe_cells.length);
  addLog("Game started. Agent at (0,0).", "good");
  updateKB(state.inference_steps);
}

async function moveAgent(r, c) {
  if (!state || !state.alive || state.won) return;
  const res = await fetch(`${API}/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: state.session_id, target: [r, c] })
  });
  const data = await res.json();
  if (data.error) { addLog(data.error, "warn"); return; }
  if (data.blocked) {
    addLog(data.message, "warn");
    updateMetrics(data.inference_steps, state.visited ? state.visited.length : 0, state.safe_cells ? state.safe_cells.length : 0);
    updateKB(data.inference_steps);
    return;
  }
  state.agent_pos = data.agent_pos;
  if (data.safe_cells) state.safe_cells = data.safe_cells;
  if (data.visited) state.visited = data.visited;
  if (!data.alive) {
    if (data.pits) state.revealed_pits = data.pits;
    if (data.wumpus) state.revealed_wumpus = data.wumpus;
    state.alive = false;
    renderGrid();
    updateMetrics(data.inference_steps, state.visited.length, state.safe_cells.length);
    addLog(data.message, "bad");
    showBanner(data.message, "lose");
    updateKB(data.inference_steps);
    return;
  }
  if (data.won) {
    state.won = true;
    state.safe_neighbors = data.safe_neighbors || [];
    renderGrid();
    updatePercepts(data.percepts);
    updateMetrics(data.inference_steps, state.visited.length, state.safe_cells.length);
    addLog("Found the gold! You win! 🏆", "good");
    showBanner("🏆 Found the gold! You win!", "win");
    updateKB(data.inference_steps);
    return;
  }
  state.safe_neighbors = data.safe_neighbors || [];
  renderGrid();
  updatePercepts(data.percepts);
  updateMetrics(data.inference_steps, state.visited.length, state.safe_cells.length);
  addLog(data.message || `Moved to (${r},${c})`, "good");
  updateKB(data.inference_steps);
}

function renderGrid() {
  if (!state) return;
  const grid = document.getElementById("grid");
  const { rows, cols, agent_pos, visited, safe_cells, safe_neighbors } = state;
  grid.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
  grid.innerHTML = "";

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const cell = document.createElement("div");
      cell.className = "cell";

      const isAgent = agent_pos[0] === r && agent_pos[1] === c;
      const isVisited = visited.some(v => v[0] === r && v[1] === c);
      const isSafe = safe_cells.some(s => s[0] === r && s[1] === c);
      const isRevealedPit = state.revealed_pits && state.revealed_pits.some(p => p[0] === r && p[1] === c);
      const isRevealedWumpus = state.revealed_wumpus && state.revealed_wumpus[0] === r && state.revealed_wumpus[1] === c;
      const isClickable = state.alive && !state.won
        && safe_neighbors
        && safe_neighbors.some(n => n[0] === r && n[1] === c)
        && !isAgent;

      if (isRevealedPit || isRevealedWumpus) {
        cell.classList.add("danger");
        cell.innerHTML = `<span class="icon">${isRevealedPit ? "⚫" : "🐛"}</span><span class="label">${isRevealedPit ? "Pit" : "Wumpus"}</span>`;
      } else if (isAgent) {
  cell.classList.add("visited");
  cell.style.background = "#c9bcd8";
  cell.style.borderColor = "#9a86b8";
  cell.innerHTML = `<span class="icon">💃🏻</span>`;
} else if (isVisited) {
        cell.classList.add("visited");
        cell.innerHTML = `<span class="icon"></span>`;
      } else if (isSafe) {
        cell.classList.add("safe");
        cell.innerHTML = `<span class="icon">👍🏻</span>`;
      } else {
        cell.classList.add("unknown");
        cell.innerHTML = `<span class="icon">-</span>`;
      }

      if (isClickable) {
        cell.classList.add("clickable");
        cell.addEventListener("click", () => moveAgent(r, c));
      }

      grid.appendChild(cell);
    }
  }
}

function updatePercepts(percepts) {
  const box = document.getElementById("percepts");
  if (!percepts) { box.innerHTML = "—"; return; }
  let html = "";
  if (percepts.breeze) html += `<span class="percept-tag breeze">💨 Breeze</span> `;
  if (percepts.stench) html += `<span class="percept-tag stench">💀 Stench</span> `;
  if (!percepts.breeze && !percepts.stench) html = `<span class="percept-tag none">✨ All Clear</span>`;
  box.innerHTML = html;
}

function updateMetrics(steps, visited, safe) {
  document.getElementById("steps").textContent = steps;
  document.getElementById("visited-count").textContent = visited;
  document.getElementById("safe-count").textContent = safe;
}

function updateKB(steps) {
  document.getElementById("kb-info").textContent =
    `Resolution ran ${steps} inference step(s) this turn. KB maintains NOT_PIT, NOT_WUMPUS, BREEZE_IMPLIES, and STENCH_IMPLIES clauses in CNF form. Contradiction search proves cell safety before each move.`;
}

function addLog(msg, type = "") {
  const log = document.getElementById("log");
  const entry = document.createElement("div");
  entry.className = `log-entry ${type}`;
  entry.textContent = msg;
  log.prepend(entry);
}

function showBanner(msg, type) {
  let banner = document.getElementById("status-banner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "status-banner";
    document.querySelector(".grid-wrap").prepend(banner);
  }
  banner.className = `status-banner ${type}`;
  banner.textContent = msg;
}

function clearBanner() {
  const banner = document.getElementById("status-banner");
  if (banner) banner.remove();
}
