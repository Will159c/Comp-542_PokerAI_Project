const API_BASE = "/classic-poker/api/leduc";

let sessionId = null;
let musicEnabled = true;

function $(sel) {
  return document.querySelector(sel);
}

function play(id) {
  if (id === "audio-bg" && !musicEnabled) return;
  const el = document.getElementById(id);
  if (!el) return;
  el.currentTime = 0;
  el.play().catch(() => {});
}

function playEvent(name) {
  const map = {
    shuffle: "audio-shuffle",
    raise: "audio-bet",
    bet: "audio-bet",
    check: "audio-check",
    call: "audio-bet",
    fold: "audio-check",
    win: "audio-win",
    lose: "audio-lose",
  };
  if (map[name]) play(map[name]);
}

function initMusicToggle() {
  const audio = document.getElementById("audio-bg");
  const btn = document.getElementById("btn-music");
  if (!audio || !btn) return;

  const setOn = (on) => {
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.textContent = on ? "Music on" : "Music off";
  };

  const tryPlay = () =>
    audio
      .play()
      .then(() => setOn(true))
      .catch(() => setOn(false));

  btn.addEventListener("click", () => {
    const isOn = btn.getAttribute("aria-pressed") === "true";
    if (isOn) {
      audio.pause();
      setOn(false);
      return;
    }
    tryPlay();
  });

  tryPlay();
  const unlock = () => {
    if (btn.getAttribute("aria-pressed") === "true") return;
    tryPlay();
    document.removeEventListener("pointerdown", unlock, true);
  };
  document.addEventListener("pointerdown", unlock, true);
}

function renderCard(rank, hidden = false) {
  if (hidden) return '<div class="card back" aria-label="Hidden card"></div>';
  if (!rank) return '<div class="card-slot-empty">—</div>';
  return `<div class="card">${rank}</div>`;
}

function setActions(state) {
  const buttons = document.querySelectorAll("#actions button[data-action]");
  buttons.forEach((btn) => {
    const action = btn.dataset.action;
    const legal = state.human_turn && !state.terminal && state.legal_actions.includes(action);
    btn.disabled = !legal;
  });
}

function syncMusicButton() {
  const btn = $("#btn-music");
  if (!btn) return;
  btn.textContent = musicEnabled ? "Music on" : "Music off";
  btn.setAttribute("aria-pressed", String(musicEnabled));
}

function setMusicEnabled(enabled) {
  musicEnabled = enabled;
  const bg = $("#audio-bg");
  if (bg) {
    if (musicEnabled) {
      bg.play().catch(() => {});
    } else {
      bg.pause();
    }
  }
  syncMusicButton();
}

function setupMusicControls() {
  const btn = $("#btn-music");
  const bg = $("#audio-bg");
  if (!btn || !bg) return;
  bg.volume = 0.4;
  syncMusicButton();
  btn.addEventListener("click", () => {
    setMusicEnabled(!musicEnabled);
  });
}

function applyState(payload) {
  const state = payload.state || payload;
  $("#pot").textContent = String(state.pot_units ?? 0);
  $("#human-card").innerHTML = renderCard(state.human_card, false);
  $("#robot-card").innerHTML = renderCard(state.opponent_card, !state.terminal);
  $("#community-card").innerHTML = renderCard(state.community_card, !state.community_card);

  $("#turn").textContent = state.terminal
    ? "Round complete"
    : state.human_turn
      ? "Current turn: You"
      : "Current turn: Robot";

  $("#message").textContent = state.message || "";

  if (state.model_info && state.model_info.infoset) {
    const probs = (state.model_info.strategy_probs || [])
      .map((p, i) => `${state.model_info.strategy_actions[i]}=${p.toFixed(2)}`)
      .join(" ");
    $("#model").textContent = `Model infoset: ${state.model_info.infoset} | ${probs}`;
  } else {
    $("#model").textContent = "Model infoset: terminal";
  }

  if (state.ai_action && state.ai_action.label) {
    $("#robot-status").textContent = `Robot action: ${state.ai_action.label}`;
  } else {
    $("#robot-status").textContent = state.terminal ? "Waiting for next round." : "Robot is thinking...";
  }

  if (state.terminal) {
    if (state.winner === "human") {
      $("#human-status").textContent = `You won this round (+${state.payoff_human}).`;
    } else if (state.winner === "ai") {
      $("#human-status").textContent = `You lost this round (${state.payoff_human}).`;
    } else {
      $("#human-status").textContent = "Round tied.";
    }
  } else if (state.human_turn) {
    $("#human-status").textContent = "Your move: check/bet or call/fold.";
  } else {
    $("#human-status").textContent = "Wait for robot action.";
  }

  setActions(state);
  if (state.audio_event) playEvent(state.audio_event);
}

async function apiNewGame() {
  play("audio-shuffle");
  const res = await fetch(`${API_BASE}/new-game`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  sessionId = data.session_id;
  play("audio-card");
  applyState(data);
}

async function apiNewHand() {
  if (!sessionId) {
    await apiNewGame();
    return;
  }
  play("audio-shuffle");
  const res = await fetch(`${API_BASE}/new-hand`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  play("audio-card");
  applyState(data);
}

async function apiAction(action) {
  if (!sessionId) return;
  const res = await fetch(`${API_BASE}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, action }),
  });
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    $("#message").textContent = j.detail || (await res.text());
    return;
  }
  const data = await res.json();
  applyState(data);
}

$("#btn-new").addEventListener("click", () => {
  apiNewHand().catch((e) => {
    $("#message").textContent = String(e);
  });
});

$("#actions").addEventListener("click", (ev) => {
  const btn = ev.target.closest("button[data-action]");
  if (!btn) return;
  apiAction(btn.dataset.action).catch((e) => {
    $("#message").textContent = String(e);
  });
});

setupMusicControls();
apiNewGame().catch((e) => {
  $("#message").textContent = `Could not start: ${e}`;
});

initMusicToggle();
