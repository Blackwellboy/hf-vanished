(() => {
  const state = {
    events: [], generatedAt: null, watchedCount: null, recovery: {}, recoverySummary: {},
    evidence: {}, manifests: {}, incidents: [], incidentByModel: {},
    mode: "all", status: null, q: ""
  };
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
  function evidenceStrength(event) {
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
  function forensicFor(id) { return state.evidence[String(id || "")] || null; }
  function manifestFor(id) { return state.manifests[String(id || "")] || null; }
  function incidentFor(id) { return state.incidentByModel[String(id || "")] || null; }
  function preservationLabel(value) { return String(value || "UNKNOWN").replaceAll("_", " "); }
  function shortSha(value, n = 10) { return value ? String(value).slice(0, n) : null; }
  function reasonLabel(reason) {
    const category = String((reason && reason.category) || "unknown").replaceAll("_", " ").toUpperCase();
    const status = String((reason && reason.status) || "UNKNOWN").toUpperCase();
    return status === "UNKNOWN" ? "WHY UNKNOWN" : `WHY ${category} · ${status}`;
  }

  function filteredEvents() {
    const query = state.q.trim().toLowerCase();
    return state.events.filter((event) => {
      if (state.mode !== "all" && group(event) !== state.mode) return false;
      if (state.status && String(event.status || "").toUpperCase() !== state.status) return false;
      if (!query) return true;
      const forensic = forensicFor(event.id) || {};
      const reason = forensic.reason || {};
      return `${event.id || ""} ${event.summary || ""} ${event.status || ""} ${reason.category || ""} ${reason.summary || ""}`.toLowerCase().includes(query);
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

  function forensicBlock(event) {
    const forensic = forensicFor(event.id);
    const manifest = manifestFor(event.id);
    const incident = incidentFor(event.id);
    if (!forensic && !manifest && !incident) return "";
    const reason = (forensic && forensic.reason) || { status: "UNKNOWN", category: "unknown", summary: "No public source documenting the cause has been recorded." };
    const sourced = String(reason.status || "UNKNOWN").toUpperCase() !== "UNKNOWN";
    const discussions = forensic && Array.isArray(forensic.discussions) ? forensic.discussions.length : 0;
    const commits = forensic && Array.isArray(forensic.commits) ? forensic.commits.length : 0;
    const signals = forensic && Array.isArray(forensic.reason_signals) ? forensic.reason_signals.length : 0;
    const evidenceHash = forensic && forensic.evidence_sha256 ? shortSha(forensic.evidence_sha256, 16) : null;
    const manifestHash = manifest && manifest.root_sha256 ? shortSha(manifest.root_sha256, 16) : (forensic && forensic.manifest_root_sha256 ? shortSha(forensic.manifest_root_sha256, 16) : null);
    const details = [];
    if (discussions) details.push(`${discussions} discussion${discussions === 1 ? "" : "s"}`);
    if (commits) details.push(`${commits} recent commit${commits === 1 ? "" : "s"}`);
    if (signals) details.push(`${signals} non-causal lead${signals === 1 ? "" : "s"}`);
    if (manifest && manifest.completeness) details.push(`manifest ${String(manifest.completeness).replaceAll("_", " ").toLowerCase()}`);
    const source = sourced && Array.isArray(reason.sources) && reason.sources[0] ? reason.sources[0] : null;
    const sourceLink = source && source.url ? `<a class="action evidence-link" href="${escapeHtml(source.url)}" rel="noopener noreferrer">REASON SOURCE ↗</a>` : "";
    const discussionLink = forensic && forensic.discussions && forensic.discussions[0] && forensic.discussions[0].num != null
      ? `<a class="action evidence-link" href="https://huggingface.co/${escapeHtml(event.id)}/discussions/${escapeHtml(forensic.discussions[0].num)}" rel="noopener noreferrer">DISCUSSION ↗</a>` : "";
    const correlation = incident
      ? `<div class="correlation">${escapeHtml(incident.id)} · correlation only · ${escapeHtml(incident.models.length)} models / 24h window. Timing/family overlap is not proof of coordination or motive.</div>`
      : "";
    return `<div class="forensics">
      <div><span class="reason-chip ${sourced ? "sourced" : "unknown"}">${escapeHtml(reasonLabel(reason))}</span>${incident ? ` <span class="incident-chip">${escapeHtml(incident.id)}</span>` : ""}</div>
      <div class="why ${sourced ? "" : "unknown"}"><strong>WHY:</strong> ${escapeHtml(reason.summary || "No public source documenting the cause has been recorded.")}</div>
      ${details.length ? `<div class="evidence-line">PUBLIC EVIDENCE: ${escapeHtml(details.join(" · "))}</div>` : ""}
      ${(evidenceHash || manifestHash) ? `<div class="evidence-line">${evidenceHash ? `EVIDENCE <code>${escapeHtml(evidenceHash)}</code>` : ""}${evidenceHash && manifestHash ? " · " : ""}${manifestHash ? `MANIFEST <code>${escapeHtml(manifestHash)}</code>` : ""}</div>` : ""}
      ${correlation}
      ${(sourceLink || discussionLink) ? `<div class="actions">${sourceLink}${discussionLink}</div>` : ""}
    </div>`;
  }

  function render() {
    const rows = filteredEvents(); updateStats();
    byId("meta").textContent = `${rows.length} shown · ${state.events.length} recorded · ${Object.keys(state.evidence).length} evidence packets · scan ${relativeTime(state.generatedAt)}`;
    if (!rows.length) { byId("feed").innerHTML = '<div class="item muted">No recorded events match.</div>'; return; }

    byId("feed").innerHTML = rows.map((event) => {
      const rawStatus = String(event.status || "UNKNOWN").toUpperCase();
      const current = displayStatus(event), ev = evidenceStrength(event), recovery = recoveryFor(event.id);
      const pf = recovery && recovery.pirateface ? recovery.pirateface : null;
      const frost = recovery && recovery.frostbyte ? recovery.frostbyte : null;
      const pres = recovery ? recovery.preservation : "UNKNOWN";
      const lp = (recovery && recovery.last_public) || event.last_public || {};
      const forensic = forensicFor(event.id);
      const reason = forensic && forensic.reason ? forensic.reason : null;
      const incident = incidentFor(event.id);
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
      const reasonChip = reason ? `<span class="reason-chip ${String(reason.status).toUpperCase() === "UNKNOWN" ? "unknown" : "sourced"}">${escapeHtml(reasonLabel(reason))}</span>` : "";
      const incidentChip = incident ? `<span class="incident-chip">${escapeHtml(incident.id)}</span>` : "";

      return `<article class="item" id="${modelAnchor(event.id)}">
        <div class="item-head"><span class="chip ${chipClass[rawStatus] || ""}">${escapeHtml(current)}</span><span class="evidence ${ev[1]}">${ev[0]}</span>${recoveryChip}${reasonChip}${incidentChip}<span class="detected">detected ${escapeHtml(dateOnly(event.detected_at))}</span></div>
        <div class="id">${escapeHtml(event.id || "unknown")}</div>
        <div class="transition"><div class="state-box before"><small>BEFORE</small><strong>${escapeHtml(before(event))}</strong></div><div class="arrow">→</div><div class="state-box now"><small>NOW</small><strong>${escapeHtml(current)}</strong></div></div>
        <div class="summary">${escapeHtml(event.summary || "Observed availability change.")}</div>
        ${technical.length ? `<div class="technical">${technical.join(" · ")}</div>` : ""}
        ${forensicBlock(event)}
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

  const optionalJson = (url) => fetch(url, { cache: "no-store" }).then((r) => r.ok ? r.json() : null).catch(() => null);
  Promise.all([
    fetch("data/events.json", { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error(`events HTTP ${r.status}`); return r.json(); }),
    optionalJson("data/state.json"),
    optionalJson("data/status.json"),
    optionalJson("data/evidence.json"),
    optionalJson("data/manifests.json"),
    optionalJson("data/incidents.json")
  ]).then(([ledger, snapshot, recovery, evidence, manifests, incidents]) => {
    state.events = ledger.events || [];
    state.generatedAt = (evidence && evidence.generated_at) || (recovery && recovery.generated_at) || ledger.generated_at || (snapshot && snapshot.updated_at) || null;
    state.recovery = (recovery && recovery.models) || {};
    state.recoverySummary = (recovery && recovery.summary) || {};
    state.evidence = (evidence && evidence.models) || {};
    state.manifests = (manifests && manifests.models) || {};
    state.incidents = (incidents && incidents.incidents) || [];
    state.incidentByModel = {};
    state.incidents.forEach((incident) => (incident.models || []).forEach((id) => {
      if (!state.incidentByModel[id]) state.incidentByModel[id] = incident;
    }));
    state.watchedCount = Number(state.recoverySummary.watched || 0) || (snapshot && snapshot.models ? Object.keys(snapshot.models).length : null);
    render();
    if (location.hash.length > 1) { const element = document.getElementById(location.hash.slice(1)); if (element) element.classList.add("focus-card"); }
  }).catch((error) => {
    byId("feed").innerHTML = `<div class="item muted">Failed to load ledger (${escapeHtml(error.message)}).</div>`;
    byId("meta").textContent = "offline / missing data";
  });
})();
