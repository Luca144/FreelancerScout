(() => {
  "use strict";

  const DATA_URL = "data.json";
  const DESCRIPTION_MAX = 300;
  const NEW_THRESHOLD_HOURS = 24;
  const STAGGER_MS = 40;
  const POLL_INTERVAL_MS = 5 * 60 * 1000;
  const SEEN_IDS_KEY = "seenIds";
  const MAX_SEEN_IDS = 500;
  const BEEP_FREQ_HZ = 880;
  const BEEP_DURATION_MS = 200;

  const state = {
    projects: [],
    updatedAt: null,
    activeFilter: null,
    newIds: new Set(),
  };

  let audioCtx = null;

  // ---------- localStorage: seen ids ----------

  function loadSeenIds() {
    try {
      const raw = localStorage.getItem(SEEN_IDS_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (err) {
      console.warn("seenIds read failed:", err);
      return [];
    }
  }

  function saveSeenIds(ids) {
    try {
      localStorage.setItem(SEEN_IDS_KEY, JSON.stringify(ids.slice(0, MAX_SEEN_IDS)));
    } catch (err) {
      console.warn("seenIds write failed:", err);
    }
  }

  // ---------- helpers ----------

  function truncate(text, limit) {
    if (!text) return "";
    if (text.length <= limit) return text;
    return text.slice(0, limit).trimEnd() + "…";
  }

  function formatRelative(thenMs, nowMs) {
    const diffSec = Math.max(0, Math.floor((nowMs - thenMs) / 1000));
    if (diffSec < 60) return "gerade eben";
    if (diffSec < 3600) {
      const min = Math.floor(diffSec / 60);
      return `vor ${min} ${min === 1 ? "Minute" : "Minuten"}`;
    }
    if (diffSec < 86400) {
      const h = Math.floor(diffSec / 3600);
      return `vor ${h} ${h === 1 ? "Stunde" : "Stunden"}`;
    }
    const d = Math.floor(diffSec / 86400);
    return `vor ${d} ${d === 1 ? "Tag" : "Tagen"}`;
  }

  function plural(n, sg, pl) {
    return n === 1 ? sg : pl;
  }

  // ---------- data ----------

  async function loadData() {
    // Prefer fetch so GitHub Pages picks up new data without a fresh HTML
    // build. Fall back to the inline <script id="bootstrap-data"> when
    // running via file:// (where browsers block fetch from local files).
    try {
      const url = `${DATA_URL}?t=${Date.now()}`;
      const resp = await fetch(url, { cache: "no-store" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    } catch (err) {
      const el = document.getElementById("bootstrap-data");
      if (el && el.textContent.trim()) {
        console.info("Using embedded bootstrap data:", err.message);
        return JSON.parse(el.textContent);
      }
      throw err;
    }
  }

  // ---------- sound ----------

  function playBeep() {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      if (!audioCtx) audioCtx = new Ctx();
      if (audioCtx.state === "suspended") audioCtx.resume();

      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      const t0 = audioCtx.currentTime;
      const end = t0 + BEEP_DURATION_MS / 1000;

      osc.type = "sine";
      osc.frequency.value = BEEP_FREQ_HZ;
      // Short attack/release ramp to avoid a click.
      gain.gain.setValueAtTime(0.0001, t0);
      gain.gain.exponentialRampToValueAtTime(0.15, t0 + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, end);

      osc.connect(gain).connect(audioCtx.destination);
      osc.start(t0);
      osc.stop(end);
    } catch (err) {
      console.warn("playBeep failed:", err);
    }
  }

  // ---------- notifications ----------

  function updateNotificationButton() {
    const btn = document.getElementById("enable-notifications");
    if (!btn) return;
    const supported = "Notification" in window;
    btn.hidden = !supported || Notification.permission !== "default";
  }

  function requestNotificationPermission() {
    if (!("Notification" in window)) return;
    // Touch the audio context within this user gesture so later beeps are allowed.
    playBeep();
    Notification.requestPermission().finally(updateNotificationButton);
  }

  function notify(count) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    const title =
      count === 1 ? "1 neues Projekt" : `${count} neue Projekte`;
    try {
      new Notification(title, {
        body: "Freelancer Scout hat neue Treffer gefunden.",
        tag: "freelancer-scout",
      });
    } catch (err) {
      // Android Chrome requires ServiceWorker notifications — accepted fallback.
      console.warn("Notification failed:", err);
    }
  }

  // ---------- render: header ----------

  function renderHeader() {
    const count = state.projects.length;
    document.getElementById("project-count").textContent = String(count);
    document.getElementById("project-count-label").textContent = plural(
      count,
      "Projekt",
      "Projekte",
    );

    const lastUpdated = document.getElementById("last-updated");
    if (state.updatedAt) {
      const updatedMs = new Date(state.updatedAt).getTime();
      lastUpdated.textContent = `zuletzt aktualisiert ${formatRelative(updatedMs, Date.now())}`;
    } else {
      lastUpdated.textContent = "";
    }
  }

  // ---------- render: filter chips ----------

  function collectKeywords() {
    const counts = new Map();
    state.projects.forEach((p) => {
      (p.matched_keywords || []).forEach((k) => {
        counts.set(k, (counts.get(k) || 0) + 1);
      });
    });
    return [...counts.entries()].sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1];
      return a[0].localeCompare(b[0]);
    });
  }

  function renderFilterChips() {
    const container = document.getElementById("filter-chips");
    container.replaceChildren();

    container.appendChild(
      createChip(`Alle (${state.projects.length})`, null, state.activeFilter === null),
    );

    for (const [kw, count] of collectKeywords()) {
      container.appendChild(
        createChip(`${kw} (${count})`, kw, state.activeFilter === kw),
      );
    }
  }

  function createChip(label, value, isActive) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "filter-chip" + (isActive ? " is-active" : "");
    btn.textContent = label;
    btn.addEventListener("click", () => {
      state.activeFilter = value;
      renderFilterChips();
      renderProjects();
    });
    return btn;
  }

  // ---------- render: project cards ----------

  function visibleProjects() {
    if (state.activeFilter === null) return state.projects;
    return state.projects.filter((p) =>
      (p.matched_keywords || []).includes(state.activeFilter),
    );
  }

  function renderProjects() {
    const container = document.getElementById("project-list");
    container.replaceChildren();

    const projects = visibleProjects();

    if (projects.length === 0) {
      container.appendChild(
        document.getElementById("empty-state-template").content.cloneNode(true),
      );
      return;
    }

    const cardTpl = document.getElementById("card-template");
    const now = Date.now();

    projects.forEach((project, index) => {
      const fragment = cardTpl.content.cloneNode(true);
      const article = fragment.querySelector(".card");
      article.style.animationDelay = `${index * STAGGER_MS}ms`;

      if (state.newIds.has(project.id)) {
        article.classList.add("is-new-arrival");
      }

      const firstSeenMs = project.first_seen
        ? new Date(project.first_seen).getTime()
        : null;
      const isNew =
        firstSeenMs !== null &&
        (now - firstSeenMs) / 3_600_000 < NEW_THRESHOLD_HOURS;
      if (isNew) {
        fragment.querySelector(".new-badge").hidden = false;
      }

      fragment.querySelector(".card-title").textContent = project.title || "";
      fragment.querySelector(".card-description").textContent = truncate(
        project.description || "",
        DESCRIPTION_MAX,
      );

      const keywordsUl = fragment.querySelector(".card-keywords");
      (project.matched_keywords || []).forEach((kw) => {
        const li = document.createElement("li");
        li.textContent = kw;
        keywordsUl.appendChild(li);
      });

      const time = fragment.querySelector(".card-time");
      time.textContent =
        firstSeenMs !== null ? formatRelative(firstSeenMs, now) : "";

      const link = fragment.querySelector(".card-link");
      link.href = project.url || "#";

      container.appendChild(fragment);
    });
  }

  function renderError() {
    const container = document.getElementById("project-list");
    container.replaceChildren(
      document.getElementById("error-state-template").content.cloneNode(true),
    );
  }

  // ---------- core update cycle ----------

  function applyData(data, { alert }) {
    state.projects = Array.isArray(data.projects) ? data.projects : [];
    state.updatedAt = data.updated_at || null;

    const seenArr = loadSeenIds();
    const seen = new Set(seenArr);
    const incomingIds = state.projects.map((p) => p.id);

    const freshIds = alert ? incomingIds.filter((id) => !seen.has(id)) : [];
    state.newIds = new Set(freshIds);

    renderHeader();
    renderFilterChips();
    renderProjects();

    if (freshIds.length > 0) {
      playBeep();
      notify(freshIds.length);
    }

    // Prepend the current ids (newest first) ahead of the prior history,
    // de-duplicated, then cap to MAX_SEEN_IDS in saveSeenIds().
    const merged = [...incomingIds, ...seenArr.filter((id) => !incomingIds.includes(id))];
    saveSeenIds(merged);
  }

  async function refresh({ alert }) {
    let data;
    try {
      data = await loadData();
    } catch (err) {
      console.error("Failed to load data.json:", err);
      if (state.projects.length === 0) renderError();
      return;
    }
    applyData(data, { alert });
  }

  // ---------- bootstrap ----------

  function wireButtons() {
    const notifBtn = document.getElementById("enable-notifications");
    if (notifBtn) notifBtn.addEventListener("click", requestNotificationPermission);
    const soundBtn = document.getElementById("test-sound");
    if (soundBtn) soundBtn.addEventListener("click", playBeep);
  }

  async function init() {
    updateNotificationButton();
    wireButtons();

    // First-ever visit (no stored ids): seed silently, do not alert.
    // Returning visit: compare against stored ids and alert on new ones.
    const isReturningVisitor = localStorage.getItem(SEEN_IDS_KEY) !== null;
    await refresh({ alert: isReturningVisitor });

    setInterval(() => refresh({ alert: true }), POLL_INTERVAL_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
