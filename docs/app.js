(() => {
  "use strict";

  const DATA_URL = "data.json";
  const DESCRIPTION_MAX = 300;
  const NEW_THRESHOLD_HOURS = 24;
  const STAGGER_MS = 40;

  const state = {
    projects: [],
    updatedAt: null,
    activeFilter: null,
  };

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

    const allChip = createChip(
      `Alle (${state.projects.length})`,
      null,
      state.activeFilter === null,
    );
    container.appendChild(allChip);

    for (const [kw, count] of collectKeywords()) {
      const chip = createChip(
        `${kw} (${count})`,
        kw,
        state.activeFilter === kw,
      );
      container.appendChild(chip);
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
      const empty = document
        .getElementById("empty-state-template")
        .content.cloneNode(true);
      container.appendChild(empty);
      return;
    }

    const cardTpl = document.getElementById("card-template");
    const now = Date.now();

    projects.forEach((project, index) => {
      const fragment = cardTpl.content.cloneNode(true);
      const article = fragment.querySelector(".card");
      article.style.animationDelay = `${index * STAGGER_MS}ms`;

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

  // ---------- bootstrap ----------

  function renderError() {
    const container = document.getElementById("project-list");
    const tpl = document.getElementById("error-state-template");
    container.replaceChildren(tpl.content.cloneNode(true));
  }

  async function init() {
    try {
      const data = await loadData();
      state.projects = Array.isArray(data.projects) ? data.projects : [];
      state.updatedAt = data.updated_at || null;
      renderHeader();
      renderFilterChips();
      renderProjects();
    } catch (err) {
      console.error("Failed to load data.json:", err);
      renderError();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
