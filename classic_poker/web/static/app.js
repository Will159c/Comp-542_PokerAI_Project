/**
 * Texas Hold'em poker UI (you vs AI) — state from POST /classic-poker/api/* (FastAPI).
 */

const API_BASE = "/classic-poker/api";

const DEALER_FRAME1 = "/images/d1.png";
const DEALER_FRAME2 = "/images/d2.png";

const $ = (sel) => document.querySelector(sel);

let dealerFrameReturnTimer = null;

/** Frame 1 = idle (d1); frame 2 = passing / dealing (d2). */
function setDealerFrame(frame) {
  const img = document.getElementById("dealer-img");
  if (!img) return;
  const isTwo = frame === 2;
  img.src = isTwo ? DEALER_FRAME2 : DEALER_FRAME1;
  img.dataset.frame = isTwo ? "2" : "1";
}

/**
 * Dealer animation: switch to frame 2 while cards are passed, then back to frame 1.
 * @param {number} [holdMs] how long to show the passing pose
 */
function dealerPassingCards(holdMs = 480) {
  if (dealerFrameReturnTimer) {
    clearTimeout(dealerFrameReturnTimer);
    dealerFrameReturnTimer = null;
  }
  setDealerFrame(2);
  dealerFrameReturnTimer = setTimeout(() => {
    setDealerFrame(1);
    dealerFrameReturnTimer = null;
  }, holdMs);
}

let sessionId = null;
let lastBoardLen = 0;
let prevWasTerminal = false;

/** Display order (columns); server uses greedy largest-first for stack contents. */
const CHIP_DENOMS = [10, 25, 50, 100, 200];
const CHIP_COLOR_CLASS = {
  10: "grey",
  25: "red",
  50: "blue",
  100: "green",
  200: "black",
};

function play(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.currentTime = 0;
  el.play().catch(() => {});
}

function playEvent(name) {
  const map = {
    shuffle: "audio-shuffle",
    deal: "audio-deal",
    raise: "audio-raise",
    check: "audio-check",
    call: "audio-raise",
    fold: "audio-check",
    win: "audio-deal",
    lose: "audio-check",
    bet: "audio-raise",
  };
  const id = map[name];
  if (id) play(id);
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

function suitClass(suit) {
  return suit === "♥" || suit === "♦" ? "red" : "";
}

function renderCard(rank, suit, { back = false, small = false } = {}) {
  const sz = small ? " card-sm" : "";
  if (back) {
    return `<div class="card back${sz}" role="img" aria-label="Hidden card"></div>`;
  }
  return `<div class="card ${suitClass(suit)}${sz}" aria-label="${rank} of ${suit}">
    <span class="rank">${rank}</span>
    <span class="suit">${suit}</span>
  </div>`;
}

function renderHole(cards, { hide = false } = {}) {
  if (!cards || !cards.length) return "";
  const bits = cards.map((c) => (hide ? renderCard("", "", { back: true }) : renderCard(c.rank, c.suit)));
  return bits.join("");
}

/** Five community cards in one row; empty seats show placeholders until dealt. */
function renderBoardLine(board) {
  const el = $("#board-line");
  if (!el) return;
  const b = board || [];
  const parts = [];
  for (let i = 0; i < 5; i++) {
    if (i < b.length) {
      parts.push(renderCard(b[i].rank, b[i].suit, { small: true }));
    } else {
      parts.push('<div class="card card-sm board-placeholder" aria-hidden="true"></div>');
    }
  }
  el.innerHTML = parts.join("");
}

function feltEl() {
  return document.querySelector(".felt");
}

function chipFlyLayer() {
  return document.getElementById("chip-flight-layer");
}

/** Remove chips that were dragged onto the felt so they do not stack up across API updates. */
function cleanupStrayFeltChips(felt) {
  if (!felt) return;
  felt.querySelectorAll(":scope > .chip-on-table").forEach((n) => n.remove());
}

function countChipsByDenom(stack) {
  const m = Object.fromEntries(CHIP_DENOMS.map((d) => [d, 0]));
  for (const c of stack || []) {
    const v = Number(c.value);
    if (m[v] !== undefined) m[v] += 1;
  }
  return m;
}

/** Snapshot pile chip positions before DOM is cleared for a terminal state. */
function captureChipsFromPilesForFlight() {
  const nodes = document.querySelectorAll("#pile-pot .chip-on-table");
  const rects = [];
  nodes.forEach((el) => {
    const r = el.getBoundingClientRect();
    rects.push({
      left: r.left,
      top: r.top,
      width: r.width,
      height: r.height,
      text: el.textContent,
      className: el.className,
    });
  });
  return rects;
}

function capFlightRects(rects, max = 44) {
  if (rects.length <= max) return rects;
  const out = [];
  const step = rects.length / max;
  for (let i = 0; i < max; i++) {
    out.push(rects[Math.floor(i * step)]);
  }
  return out;
}

function centerOfRect(r) {
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}

function targetPointForWinner(winner, index, total) {
  const humanPill = document.querySelector(".human-seat .stack-pill");
  const aiPill = document.querySelector(".ai-seat .stack-pill");
  if (winner === "human" && humanPill) {
    return centerOfRect(humanPill.getBoundingClientRect());
  }
  if (winner === "ai" && aiPill) {
    return centerOfRect(aiPill.getBoundingClientRect());
  }
  if (winner === "tie") {
    const el = index < total / 2 ? humanPill : aiPill;
    if (el) return centerOfRect(el.getBoundingClientRect());
  }
  const felt = feltEl();
  if (felt) return centerOfRect(felt.getBoundingClientRect());
  return { x: window.innerWidth / 2, y: window.innerHeight / 2 };
}

/** After a hand ends, fly pot chips from the piles toward the winner's stack. */
function runChipFlightToWinner(winner, rects) {
  const layer = chipFlyLayer();
  if (!layer || !rects.length || !winner) return;

  const capped = capFlightRects(rects, 44);
  const total = capped.length;

  capped.forEach((snap, i) => {
    const clone = document.createElement("div");
    clone.className = `${snap.className} chip-fly-clone`.replace(/\s+/g, " ").trim();
    clone.textContent = snap.text;
    if (String(snap.text).length >= 3) clone.classList.add("chip-3digit");

    const w = snap.width;
    const h = snap.height;
    clone.style.left = `${snap.left}px`;
    clone.style.top = `${snap.top}px`;
    clone.style.width = `${w}px`;
    clone.style.height = `${h}px`;
    clone.style.transformOrigin = "center center";

    const end = targetPointForWinner(winner, i, total);
    const startCx = snap.left + w / 2;
    const startCy = snap.top + h / 2;
    const dx = end.x - startCx;
    const dy = end.y - startCy;
    const sway = winner === "tie" ? (i % 2 === 0 ? -16 : 16) : (Math.random() * 20 - 10);
    const midY = dy * 0.42 + sway;

    layer.appendChild(clone);

    const delay = Math.floor(i * 36);
    const anim = clone.animate(
      [
        { transform: "translate(0, 0) scale(1)", opacity: 1, offset: 0 },
        {
          transform: `translate(${dx * 0.52}px, ${midY}px) scale(1.06)`,
          opacity: 1,
          offset: 0.48,
        },
        {
          transform: `translate(${dx}px, ${dy}px) scale(0.7)`,
          opacity: 0.88,
          offset: 1,
        },
      ],
      {
        duration: 900 + (i % 6) * 35,
        delay,
        easing: "cubic-bezier(0.18, 0.75, 0.18, 1)",
        fill: "forwards",
      },
    );
    (anim.finished ?? Promise.resolve()).finally(() => clone.remove());
  });
}

function attachChipDrag(chipEl, felt) {
  if (!felt) return;
  chipEl.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const fr = felt.getBoundingClientRect();
    const rect = chipEl.getBoundingClientRect();
    const grabX = e.clientX - rect.left;
    const grabY = e.clientY - rect.top;

    if (chipEl.parentElement !== felt) {
      felt.appendChild(chipEl);
      chipEl.style.position = "absolute";
      chipEl.style.left = `${rect.left - fr.left}px`;
      chipEl.style.top = `${rect.top - fr.top}px`;
    }

    chipEl.setPointerCapture(e.pointerId);
    chipEl.classList.add("dragging");

    const move = (ev) => {
      const fr2 = felt.getBoundingClientRect();
      let x = ev.clientX - fr2.left - grabX;
      let y = ev.clientY - fr2.top - grabY;
      const maxX = Math.max(0, fr2.width - chipEl.offsetWidth);
      const maxY = Math.max(0, fr2.height - chipEl.offsetHeight);
      x = Math.min(maxX, Math.max(0, x));
      y = Math.min(maxY, Math.max(0, y));
      chipEl.style.position = "absolute";
      chipEl.style.left = `${x}px`;
      chipEl.style.top = `${y}px`;
    };

    const up = (ev) => {
      try {
        chipEl.releasePointerCapture(ev.pointerId);
      } catch {
        /* released */
      }
      chipEl.classList.remove("dragging");
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", up);
    };

    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", up);
    move(e);
  });
}

function renderChipPile(container, stack) {
  if (!container) return;
  container.innerHTML = "";
  const felt = feltEl();
  if (!stack || !stack.length) {
    const empty = document.createElement("span");
    empty.className = "pile-empty";
    empty.textContent = "—";
    container.appendChild(empty);
    return;
  }

  const counts = countChipsByDenom(stack);
  const grid = document.createElement("div");
  grid.className = "chip-pile-grid";

  for (const d of CHIP_DENOMS) {
    const col = document.createElement("div");
    col.className = "chip-column";

    const lab = document.createElement("span");
    lab.className = "chip-column-label";
    lab.textContent = String(d);
    col.appendChild(lab);

    const stackWrap = document.createElement("div");
    stackWrap.className = "chip-column-stack";

    const n = counts[d] || 0;
    for (let i = 0; i < n; i++) {
      const ch = document.createElement("div");
      const color = CHIP_COLOR_CLASS[d] || "";
      ch.className = `chip chip-on-table ${color}`.trim();
      ch.dataset.chipValue = String(d);
      if (d >= 100) ch.classList.add("chip-3digit");
      ch.textContent = String(d);
      ch.title = `${d} — drag on the felt`;
      ch.style.zIndex = String(i + 1);
      attachChipDrag(ch, felt);
      stackWrap.appendChild(ch);
    }

    col.appendChild(stackWrap);
    grid.appendChild(col);
  }

  container.appendChild(grid);
}

function renderTableChipPiles(state) {
  cleanupStrayFeltChips(feltEl());
  renderChipPile($("#pile-pot"), state.pot_chip_stack);

  const pilePot = $("#pile-pot");
  if (!pilePot) return;
  pilePot.classList.remove("ai-pile-highlight");
  const trace = state.ai_trace;
  if (trace && trace.length && trace[trace.length - 1].action === "b") {
    pilePot.offsetHeight;
    pilePot.classList.add("ai-pile-highlight");
  }
}

function setButtons(state) {
  const actionsRoot = $("#actions");
  const openRow = actionsRoot?.querySelector(".actions-row-open");
  const facingRow = actionsRoot?.querySelector(".actions-row-facing");
  for (const id of ["btn-p", "btn-allin", "btn-fold", "btn-call"]) {
    const el = $(`#${id}`);
    if (el) {
      el.hidden = true;
      if (id === "btn-allin") el.removeAttribute("data-bet-amount");
    }
  }
  const betRow = $("#bet-size-row");
  if (betRow) {
    betRow.innerHTML = "";
    betRow.hidden = true;
  }
  if (openRow) openRow.hidden = true;
  if (facingRow) facingRow.hidden = true;

  if (!state.human_turn || state.terminal) return;

  const a = state.legal_actions;
  const callAmt = state.call_amount ?? state.bet_size ?? 0;

  if (a.includes("b")) {
    if (openRow) openRow.hidden = false;
    const bp = $("#btn-p");
    if (bp) {
      bp.hidden = false;
      bp.textContent = "Check";
    }
    const legal =
      Array.isArray(state.legal_bet_sizes) && state.legal_bet_sizes.length
        ? state.legal_bet_sizes
        : [10, 25, 50, 100, 200];
    const stack = state.human_chips ?? 0;
    const stdSizes = CHIP_DENOMS.filter((d) => legal.includes(d));
    if (betRow) {
      betRow.hidden = false;
      for (const n of stdSizes) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn primary btn-bet-size";
        btn.dataset.action = "b";
        btn.dataset.betAmount = String(n);
        btn.textContent = `+${n}`;
        btn.title = `Bet ${n} chips`;
        betRow.appendChild(btn);
      }
    }
    const showAllIn =
      stack > 0 &&
      legal.includes(stack) &&
      (stack > 200 || !CHIP_DENOMS.includes(stack));
    const allInBtn = $("#btn-allin");
    if (showAllIn && allInBtn) {
      allInBtn.hidden = false;
      allInBtn.dataset.betAmount = String(stack);
      allInBtn.textContent = `All in (${stack})`;
      allInBtn.title = `Bet all ${stack} chips`;
    }
  } else if (a.includes("c")) {
    if (facingRow) facingRow.hidden = false;
    const bf = $("#btn-fold");
    const bc = $("#btn-call");
    if (bf) {
      bf.hidden = false;
      bf.textContent = "Fold";
    }
    if (bc) {
      bc.hidden = false;
      bc.textContent = `Call (${callAmt})`;
    }
  } else if (a.includes("p") && !a.includes("b")) {
    const hist = state.street_history || "";
    const foldOnly = hist.endsWith("b");
    if (foldOnly) {
      if (facingRow) facingRow.hidden = false;
      const bf = $("#btn-fold");
      if (bf) {
        bf.hidden = false;
        bf.textContent = "Fold";
      }
    } else if (openRow) {
      openRow.hidden = false;
      const bp = $("#btn-p");
      if (bp) {
        bp.hidden = false;
        bp.textContent = "Check";
      }
    }
  }
}

function renderAiTrace(trace) {
  const el = $("#ai-log");
  if (!trace || !trace.length) {
    el.textContent = "";
    return;
  }
  el.textContent = `Opponent's last actions: ${trace.map((t) => t.label).join(" → ")}`;
}

function applyState(payload) {
  const state = payload.state || payload;
  const enteringTerminal = state.terminal && !prevWasTerminal;
  const flightRects = enteringTerminal ? captureChipsFromPilesForFlight() : null;

  $("#message").textContent = state.message || "";

  const board = state.board || [];
  if (board.length > lastBoardLen) {
    play("audio-deal");
    dealerPassingCards();
  }
  lastBoardLen = board.length;

  $("#street-badge").textContent = state.street_label || state.street || "—";
  $("#pot-amount").textContent = `${state.pot_chips ?? 0} chips`;
  renderBoardLine(board);

  const aiChipsEl = $("#ai-chips");
  const humanChipsEl = $("#human-chips");
  if (aiChipsEl) {
    aiChipsEl.textContent = state.ai_chips != null ? `${state.ai_chips} chips` : "—";
  }
  if (humanChipsEl) {
    humanChipsEl.textContent =
      state.human_chips != null ? `${state.human_chips} chips` : "—";
  }

  $("#human-hole").innerHTML = renderHole(state.human_hole);
  $("#ai-hole").innerHTML = renderHole(state.opponent_hole, {
    hide: !state.opponent_hole_revealed,
  });

  const net = state.payoff_human;
  const why = state.finish_reason;
  $("#human-status").textContent = state.terminal
    ? state.winner === "tie"
      ? net === 0
        ? "Push."
        : `Split pot · net ${net > 0 ? "+" : ""}${net} chips.`
      : state.winner === "human"
        ? why === "fold"
          ? net > 0
            ? `Pot yours — opponent folded (+${net} net).`
            : "Pot yours — opponent folded."
          : net > 0
            ? `Showdown win — best 5-card hand (+${net} net).`
            : "Showdown win — best 5-card hand."
        : net < 0
          ? `You lost ${-net} chips (net).`
          : "Hand complete."
    : state.human_turn
      ? "Your turn — respond to the pot and your opponent."
      : "Opponent is acting against your hand…";

  $("#ai-status").textContent = state.terminal
    ? state.winner === "ai"
      ? why === "fold"
        ? "You folded — opponent wins the pot."
        : "Showdown — opponent had the best hand."
      : state.winner === "human"
        ? why === "fold"
          ? "Folded to your bet — mucked cards; pot not decided by showdown."
          : "Lost at showdown — opponent's hand was better."
        : "Split pot."
    : state.human_turn
      ? "Waiting for you — same board, betting against your cards."
      : "Opponent is betting or checking…";

  const line = state.street_history ? ` · this street: “${state.street_history}”` : "";
  $("#pot-text").textContent = state.terminal
    ? `Hand over${line}`
    : `${state.street_label || ""} · pot ${state.pot_chips ?? 0}${line}`;

  renderTableChipPiles(state);
  renderAiTrace(state.ai_trace);
  setButtons(state);

  if (state.audio_event) playEvent(state.audio_event);

  if (enteringTerminal && flightRects && flightRects.length && state.winner) {
    requestAnimationFrame(() => runChipFlightToWinner(state.winner, flightRects));
  }
  prevWasTerminal = !!state.terminal;
}

async function apiNewGame() {
  play("audio-shuffle");
  lastBoardLen = 0;
  prevWasTerminal = false;
  const res = await fetch(`${API_BASE}/new-game`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  sessionId = data.session_id;
  play("audio-deal");
  applyState(data);
  dealerPassingCards();
}

async function apiNewHand() {
  play("audio-shuffle");
  lastBoardLen = 0;
  if (sessionId) {
    const res = await fetch(`${API_BASE}/new-hand`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
    if (res.ok) {
      const data = await res.json();
      applyState(data);
      play("audio-deal");
      dealerPassingCards();
      return;
    }
  }
  await apiNewGame();
}

async function apiAction(action, betAmount) {
  if (!sessionId) return;
  const payload = { session_id: sessionId, action };
  if (action === "b" && betAmount != null) {
    payload.bet_amount = betAmount;
  }
  const res = await fetch(`${API_BASE}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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
  const t = ev.target.closest("button[data-action]");
  if (!t) return;
  const action = t.getAttribute("data-action");
  const raw = t.getAttribute("data-bet-amount");
  const betAmount = raw != null && raw !== "" ? Number(raw) : undefined;
  apiAction(action, Number.isFinite(betAmount) ? betAmount : undefined).catch((e) => {
    $("#message").textContent = String(e);
  });
});

apiNewGame().catch((e) => {
  $("#message").textContent = `Could not start: ${e}`;
});

initMusicToggle();
