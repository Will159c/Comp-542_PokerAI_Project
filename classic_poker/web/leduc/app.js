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

/**
 * Show or hide each action button based on what's actually legal in this state.
 * Backend's legal_actions array drives this — possible values: p, b, c, r, f.
 */
function setActions(state) {
  const buttons = document.querySelectorAll("#actions button[data-action]");
  buttons.forEach((btn) => {
    const action = btn.dataset.action;
    const legal =
      state.human_turn &&
      !state.terminal &&
      Array.isArray(state.legal_actions) &&
      state.legal_actions.includes(action);
    btn.disabled = !legal;
    btn.hidden = !legal;
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
  $("#round-label").textContent = state.street_label || "—";

  $("#human-card").innerHTML = renderCard(state.human_card, false);
  $("#robot-card").innerHTML = renderCard(state.opponent_card, !state.terminal);
  $("#community-card").innerHTML = renderCard(
    state.community_card,
    !state.community_card,
  );

  $("#turn").textContent = state.terminal
    ? "Hand complete"
    : state.human_turn
      ? "Current turn: You"
      : "Current turn: Robot";

  $("#message").textContent = state.message || "";

  // model_info is now ONLY set by the server right after a human action,
  // showing what the AI did in response (with its card and strategy).
  // On a fresh hand, between the AI's action and the human's next, model_info
  // is null — and we hide the line entirely.
  const modelEl = $("#model");
  if (state.model_info && state.model_info.infoset) {
    const probs = (state.model_info.strategy_probs || [])
      .map((p, i) => `${state.model_info.strategy_actions[i]}=${p.toFixed(2)}`)
      .join(" ");
    modelEl.textContent = `Opponent's response — infoset ${state.model_info.infoset} | ${probs}`;
    modelEl.hidden = false;
  } else {
    modelEl.textContent = "";
    modelEl.hidden = true;
  }

  if (state.ai_action && state.ai_action.label) {
    $("#robot-status").textContent = `Robot action: ${state.ai_action.label}`;
  } else {
    $("#robot-status").textContent = state.terminal
      ? "Hand complete."
      : "Robot is waiting on your move.";
  }

  if (state.terminal) {
    if (state.winner === "human") {
      $("#human-status").textContent = `You won this hand (+${state.payoff_human}).`;
    } else if (state.winner === "ai") {
      $("#human-status").textContent = `You lost this hand (${state.payoff_human}).`;
    } else {
      $("#human-status").textContent = "Hand tied.";
    }
  } else if (state.human_turn) {
    const acts = state.legal_actions || [];
    if (acts.includes("b")) {
      $("#human-status").textContent = "Your move: check or bet.";
    } else {
      $("#human-status").textContent = "Your move: fold, call, or raise.";
    }
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
  if (!btn || btn.disabled) return;
  apiAction(btn.dataset.action).catch((e) => {
    $("#message").textContent = String(e);
  });
});

setupMusicControls();
apiNewGame().catch((e) => {
  $("#message").textContent = `Could not start: ${e}`;
});

initMusicToggle();
