(() => {
  const state = { events: [], generatedAt: null, watchedCount: null, recovery: {}, recoverySummary: {}, mode: "all", status: null, q: "" };
  const vanishedStatuses = new Set(["DISABLED", "DELETED", "PRIVATE", "STRIPPED", "AUTH_REQUIRED"]);
  const chipClass = { DISABLED: "dis", DELETED: "del", PRIVATE: "priv", GATED: "gate", STRIPPED: "strip", AUTH_REQUIRED: "auth" };
  const preservationClass = { PROTECTED: "protected", RESCUED: "rescued", AT_RISK: "risk", NO_KNOWN_COPY: "lost", UNMIRRORED: "unmirrored", UNKNOWN: "unknown" };
  const byId = (id) => document.getElementById(id);

  function escapeHtml(value) {
    return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function group(event) {
    const status = String(event.status || "").toUpperCase();
    return event.severity === "hard" || vanishedStatuses.has(status) ? "vanished" : "restricted";
  }
  function displayStatus(event) {
    const status = String(event.status || "UNKNOWN").toUpperCase();
    const http = event.curr && event.curr.http;
    if ((http === 401 || http === 403) && (status === "PRIVATE" || status === "DELETED")) return "AUTH REQUIRED";
    if (status === "STRIPPED") return "FILES REMOVED";
    return status.replaceAll("_", " ");
  }
  function exactArchive(event) { return Boolean(event.wayback_url && !event.wayback_url.includes("/web/*/")); }
  function evidence(event) {
    if (event.prev && event.prev.visibility === "public") return ["VERIFIED", "verified"];
    if (exactArchive(event)) return ["ARCHIVED", "archived"];
    return ["REPORTED", "reported"];
  }
  function before(event) {
    if (event.prev && event.prev.visibility === "public") return "PUBLIC";
    return exactArchive(event) ? "PUBLIC (ARCHIVED)" : "PUBLIC (REPORTED)";
  }
  function relativeTime(timestamp) {
    if (!timestamp) return "—";
    const date = new Date(timestamp); if (Number.isNaN(date.getTime())) return timestamp;
    const minutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60000));
    if (minutes < 2) return "now"; if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.round(minutes / 60); if (hours < 48) return `${hours}h ago`;
    return `${Math.round(hours / 24)}d ago`;
  }
  function dateOnly(timestamp) {
    if (!timestamp) return "unknown";
    const date = new Date(timestamp);
    return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }
  function modelAnchor(id) { return encodeURIComponent(String(id || "unknown")); }
  function mirrorSearchUrl(id) {
    const value = String(id || ""), parts = value.split("/"), modelName = parts[parts.length - 1] || value;
    return `https://huggingface.co/models?search=${encodeURIComponent(modelName)}`;
  }
  function recoveryFor(id) { return state.recovery[String(id || "")] || null; }
  function preservationLabel(value) { return String(value || "UNKNOWN").replaceAll("_", " "); }
  function shortSha(value) { return value ? String(value).slice(0, 10) : null; }

  function filteredEvents() {
    const query = state.q.trim().toLowerCase();
    return state.events.filter((event) => {
      if (state.mode !== "all" && group(event) !== state.mode) return false;
      if (state.status && String(event.status || "").toUpperCase() !== state.status) return false;
      if (!query) return true;
      return `${event.id || ""} ${event.summary || ""} ${event.status || ""}`.toLowerCase().includes(query);
    });
  }

  function updateStats() {
    const vanished = state.events.filter((event) => group(event) === "vanished").length;
    const restricted = state.events.length - vanished;
    byId("statEvents").textContent = state.events.length.toLocaleString();
    byId("statVanished").textContent = vanished.toLocaleString();
    byId("statRescued").textContent = Number(state.recoverySummary.rescued || 0).toLocaleString();
    byId("statWatched").textContent = state.watchedCount == null ? "—" : state.watchedCount.toLocaleString();
    byId("statScan").textContent = relativeTime(state.generatedAt);
    byId("countAll").textContent = state.events.length;
    byId("countVanished").textContent = vanished;
    byId("countRestricted").textContent = restricted;
  }

  function render() {
    const rows = filteredEvents(); updateStats();
    byId("meta").textContent = `${rows.length} shown · ${state.events.length} recorded · scan ${relativeTime(state.generatedAt)}`;
    if (!rows.length) { byId("feed").innerHTML = '<div class="item muted">No recorded events match.</div>'; return; }

    byId("feed").innerHTML = rows.map((event) => {
      const rawStatus = String(event.status || "UNKNOWN").toUpperCase();
      const current = displayStatus(event), ev = evidence(event), recovery = recoveryFor(event.id);
      const pf = recovery && recovery.pirateface ? recovery.pirateface : null;
      const frost = recovery && recovery.frostbyte ? recovery.frostbyte : null;
      const pres = recovery ? recovery.preservation : "UNKNOWN";
      const lp = (recovery && recovery.last_public) || event.last_public || {};
      const links = [];
      if (event.hf_url) links.push(`<a class="action" href="${escapeHtml(event.hf_url)}" rel="noopener noreferrer">CURRENT HUB ↗</a>`);
      if (event.wayback_url) links.push(`<a class="action" href="${escapeHtml(event.wayback_url)}" rel="noopener noreferrer">BEFORE / WAYBACK ↗</a>`);
      if (pf && pf.url) links.push(`<a class="action pf" href="${escapeHtml(pf.url)}" rel="noopener noreferrer">PIRATE FACE ↗</a>`);
      if (pf && pf.magnet) links.push(`<button class="action copy-magnet" data-magnet="${encodeURIComponent(pf.magnet)}">COPY MAGNET</button>`);
      if (frost && frost.app_url && pf && pf.magnet) links.push(`<a class="action frost" href="${escapeHtml(frost.app_url)}" rel="noopener noreferrer" title="FrostByte accepts magnet links">FROSTBYTE ↗</a>`);
      links.push(`<a class="action" href="${escapeHtml(mirrorSearchUrl(event.id))}" rel="noopener noreferrer">FIND LIVE COPIES ↗</a>`);
      links.push(`<a class="action" href="#${modelAnchor(event.id)}">DIRECT LINK</a>`);

      const technical = [];
      if (event.curr && event.curr.http != null) technical.push(`HTTP ${escapeHtml(event.curr.http)}`);
      if (lp.license) technical.push(`LICENSE ${escapeHtml(lp.license)}`);
      if (lp.sha) technical.push(`REV ${escapeHtml(shortSha(lp.sha))}`);
      if (pf && pf.seeders != null) technical.push(`${escapeHtml(pf.seeders)} SEEDER${Number(pf.seeders) === 1 ? "" : "S"}`);
      const recoveryChip = `<span class="preservation ${preservationClass[pres] || "unknown"}">${escapeHtml(preservationLabel(pres))}</span>`;

      return `<article class="item" id="${modelAnchor(event.id)}">
        <div class="item-head"><span class="chip ${chipClass[rawStatus] || ""}">${escapeHtml(current)}</span><span class="evidence ${ev[1]}">${ev[0]}</span>${recoveryChip}<span class="detected">detected ${escapeHtml(dateOnly(event.detected_at))}</span></div>
        <div class="id">${escapeHtml(event.id || "unknown")}</div>
        <div class="transition"><div class="state-box before"><small>BEFORE</small><strong>${escapeHtml(before(event))}</strong></div><div class="arrow">→</div><div class="state-box now"><small>NOW</small><strong>${escapeHtml(current)}</strong></div></div>
        <div class="summary">${escapeHtml(event.summary || "Observed availability change.")}</div>
        ${technical.length ? `<div class="technical">${technical.join(" · ")}</div>` : ""}
        <div class="actions">${links.join("")}</div>
      </article>`;
    }).join("");
  }

  document.querySelectorAll(".mode").forEach((button) => button.addEventListener("click", () => {
    state.mode = button.dataset.mode; document.querySelectorAll(".mode").forEach((item) => item.classList.remove("active")); button.classList.add("active"); render();
  }));
  document.querySelectorAll(".legend .chip").forEach((button) => button.addEventListener("click", () => {
    const value = button.dataset.filter; state.status = state.status === value ? null : value;
    document.querySelectorAll(".legend .chip").forEach((item) => item.classList.remove("active")); if (state.status) button.classList.add("active"); render();
  }));
  byId("q").addEventListener("input", (event) => { state.q = event.target.value; render(); });
  byId("feed").addEventListener("click", async (event) => {
    const button = event.target.closest(".copy-magnet"); if (!button) return;
    const magnet = decodeURIComponent(button.dataset.magnet || ""); if (!magnet) return;
    try { await navigator.clipboard.writeText(magnet); button.textContent = "MAGNET COPIED"; setTimeout(() => { button.textContent = "COPY MAGNET"; }, 1800); }
    catch { window.prompt("Copy this magnet into FrostByte or another torrent client:", magnet); }
  });

  Promise.all([
    fetch("data/events.json", { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error(`events HTTP ${r.status}`); return r.json(); }),
    fetch("data/state.json", { cache: "no-store" }).then((r) => r.ok ? r.json() : null).catch(() => null),
    fetch("data/status.json", { cache: "no-store" }).then((r) => r.ok ? r.json() : null).catch(() => null)
  ]).then(([ledger, snapshot, recovery]) => {
    state.events = ledger.events || [];
    state.generatedAt = (recovery && recovery.generated_at) || ledger.generated_at || (snapshot && snapshot.updated_at) || null;
    state.recovery = (recovery && recovery.models) || {};
    state.recoverySummary = (recovery && recovery.summary) || {};
    state.watchedCount = Number(state.recoverySummary.watched || 0) || (snapshot && snapshot.models ? Object.keys(snapshot.models).length : null);
    render();
    if (location.hash.length > 1) { const element = document.getElementById(location.hash.slice(1)); if (element) element.classList.add("focus-card"); }
  }).catch((error) => {
    byId("feed").innerHTML = `<div class="item muted">Failed to load ledger (${escapeHtml(error.message)}).</div>`;
    byId("meta").textContent = "offline / missing data";
  });
})();
