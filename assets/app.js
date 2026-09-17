(() => {
  const state = {
    events: [], generatedAt: null, watchedCount: null, recovery: {}, recoverySummary: {},
    evidence: {}, manifests: {}, incidents: [], incidentByModel: {},
    mode: "all", q: "",
    statusFilters: new Set(), reasonFilters: new Set(), evidenceFilters: new Set(),
    expanded: new Set()
  };
  const vanishedStatuses = new Set(["DISABLED", "DELETED", "PRIVATE", "STRIPPED", "AUTH_REQUIRED"]);
  const chipClass = { DISABLED: "dis", DELETED: "del", PRIVATE: "priv", GATED: "gate", STRIPPED: "strip", AUTH_REQUIRED: "auth", RESTORED: "restored" };
  const byId = (id) => document.getElementById(id);

  function escapeHtml(value) {
    return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function group(event) {
    const status = String(event.status || "").toUpperCase();
    if (status === "RESTORED") return "restored";
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
  function hasArchive(event) { return Boolean(event.wayback_url); }
  function before(event) {
    if (event.prev && event.prev.visibility === "public") return "Public";
    return exactArchive(event) ? "Public (archived)" : "Public (reported)";
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
  function preservationLabel(value) { return String(value || "UNKNOWN").replaceAll("_", " ").toLowerCase(); }
  function titleCase(value) {
    return String(value || "").replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  }
  function reasonMeta(reason) {
    const status = String((reason && reason.status) || "UNKNOWN").toUpperCase();
    if (status === "UNKNOWN") return "Unknown";
    const category = String((reason && reason.category) || "").replaceAll("_", " ");
    if (category && category.toLowerCase() !== "unknown") return `${titleCase(status)} · ${category}`;
    return titleCase(status);
  }
  function finiteNumber(value) { return typeof value === "number" && Number.isFinite(value); }
  function compactNumber(value) {
    if (!finiteNumber(value)) return null;
    const abs = Math.abs(value);
    if (abs >= 1e9) return `${(value / 1e9).toFixed(abs >= 1e11 ? 0 : 1).replace(/\.0$/, "")}B`;
    if (abs >= 1e6) return `${(value / 1e6).toFixed(abs >= 1e8 ? 0 : 1).replace(/\.0$/, "")}M`;
    if (abs >= 1e3) return `${(value / 1e3).toFixed(abs >= 1e5 ? 0 : 1).replace(/\.0$/, "")}K`;
    return value.toLocaleString();
  }
  function parameterLabel(value) {
    if (!finiteNumber(value)) return null;
    if (value >= 1e12) return `${(value / 1e12).toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}T`;
    if (value >= 1e9) return `${(value / 1e9).toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}B`;
    if (value >= 1e6) return `${(value / 1e6).toFixed(1).replace(/\.0$/, "")}M`;
    return compactNumber(value);
  }
  function bytesLabel(value) {
    if (!finiteNumber(value) || value < 0) return null;
    const units = ["B", "KB", "MB", "GB", "TB"];
    let n = value, i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1; }
    return `${n >= 100 || i === 0 ? n.toFixed(0) : n.toFixed(1).replace(/\.0$/, "")} ${units[i]}`;
  }
  function hasManifest(event) {
    const manifest = manifestFor(event.id);
    const forensic = forensicFor(event.id);
    return Boolean((manifest && manifest.root_sha256) || (forensic && forensic.manifest_root_sha256));
  }
  function hasDiscussions(event) {
    const forensic = forensicFor(event.id);
    return Boolean(forensic && Array.isArray(forensic.discussions) && forensic.discussions.length);
  }
  function hasRecoveryCopy(event) {
    const recovery = recoveryFor(event.id);
    if (!recovery) return false;
    const pres = String(recovery.preservation || "").toUpperCase();
    if (pres === "PROTECTED" || pres === "RESCUED") return true;
    const pf = recovery.pirateface || {};
    return Boolean(pf.magnet || (pf.seeders != null && Number(pf.seeders) > 0));
  }
  function hubRevision(event) {
    const manifest = manifestFor(event.id);
    if (manifest && manifest.revision) return manifest.revision;
    const lp = (recoveryFor(event.id) && recoveryFor(event.id).last_public) || event.last_public || {};
    return lp.sha || null;
  }

  function snapshotBlock(lp) {
    if (!lp || typeof lp !== "object") return "";
    const meaningful = [lp.checked_at, lp.downloads, lp.likes, lp.pipeline_tag, lp.model_type, lp.parameter_count, lp.formats && lp.formats.length, lp.quantization && lp.quantization.length].some((value) => value !== null && value !== undefined && value !== "" && value !== 0);
    if (!meaningful) return "";

    const metrics = [];
    const downloads = compactNumber(lp.downloads);
    const likes = compactNumber(lp.likes);
    const params = parameterLabel(lp.parameter_count);
    const storage = bytesLabel(lp.used_storage);
    if (downloads !== null) metrics.push(`<div class="snapshot-metric"><strong>${escapeHtml(downloads)}</strong><span>HF DOWNLOADS</span></div>`);
    if (likes !== null) metrics.push(`<div class="snapshot-metric"><strong>${escapeHtml(likes)}</strong><span>LIKES</span></div>`);
    if (params !== null) metrics.push(`<div class="snapshot-metric"><strong>${escapeHtml(params)}</strong><span>PARAMETERS</span></div>`);
    if (storage !== null) metrics.push(`<div class="snapshot-metric"><strong>${escapeHtml(storage)}</strong><span>STORAGE</span></div>`);

    const tags = [];
    if (lp.pipeline_tag) tags.push(`TASK ${String(lp.pipeline_tag).replaceAll("-", " ")}`);
    if (lp.model_type) tags.push(`TYPE ${lp.model_type}`);
    if (Array.isArray(lp.architectures)) lp.architectures.slice(0, 2).forEach((value) => tags.push(`ARCH ${value}`));
    if (lp.library_name) tags.push(`LIB ${lp.library_name}`);
    if (Array.isArray(lp.formats)) lp.formats.forEach((value) => tags.push(`FORMAT ${value}`));
    if (Array.isArray(lp.quantization)) lp.quantization.forEach((value) => tags.push(`QUANT ${value}`));
    if (lp.license) tags.push(`LICENSE ${lp.license}`);

    const context = [];
    if (lp.namespace) context.push(`namespace ${lp.namespace}`);
    if (Array.isArray(lp.base_models) && lp.base_models.length) context.push(`base ${lp.base_models.slice(0, 2).join(", ")}`);
    if (lp.last_modified) context.push(`Hub modified ${dateOnly(lp.last_modified)}`);

    return `<section class="last-public">
      <div class="snapshot-head"><strong>LAST PUBLIC SNAPSHOT</strong><span>${lp.checked_at ? `captured ${escapeHtml(dateOnly(lp.checked_at))}` : "historical metadata"}</span></div>
      ${metrics.length ? `<div class="snapshot-metrics">${metrics.join("")}</div>` : ""}
      ${tags.length ? `<div class="snapshot-tags">${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
      ${context.length ? `<div class="snapshot-context">${escapeHtml(context.join(" · "))}</div>` : ""}
    </section>`;
  }

  function filteredEvents() {
    const query = state.q.trim().toLowerCase();
    return state.events.filter((event) => {
      if (state.mode !== "all" && group(event) !== state.mode) return false;
      const status = String(event.status || "").toUpperCase();
      if (state.statusFilters.size && !state.statusFilters.has(status)) return false;
      const forensic = forensicFor(event.id) || {};
      const reason = forensic.reason || {};
      const reasonStatus = String(reason.status || "UNKNOWN").toUpperCase();
      if (state.reasonFilters.size && !state.reasonFilters.has(reasonStatus)) return false;
      if (state.evidenceFilters.size) {
        const flags = {
          manifest: hasManifest(event),
          archive: hasArchive(event),
          discussions: hasDiscussions(event),
          recovery: hasRecoveryCopy(event)
        };
        for (const key of state.evidenceFilters) if (!flags[key]) return false;
      }
      if (!query) return true;
      const recovery = recoveryFor(event.id) || {};
      const lp = recovery.last_public || event.last_public || {};
      const profile = [lp.pipeline_tag, lp.model_type, lp.library_name, ...(lp.architectures || []), ...(lp.formats || []), ...(lp.quantization || []), lp.license, lp.namespace, ...(lp.base_models || [])].filter(Boolean).join(" ");
      return `${event.id || ""} ${event.summary || ""} ${event.status || ""} ${reason.category || ""} ${reason.summary || ""} ${reason.status || ""} ${profile}`.toLowerCase().includes(query);
    });
  }

  function evidenceBits(event) {
    const forensic = forensicFor(event.id) || {};
    const bits = [];
    if (exactArchive(event)) bits.push("Snapshot");
    else if (event.wayback_url) bits.push("Archive");
    if (hasManifest(event)) bits.push("Manifest");
    const commits = Array.isArray(forensic.commits) ? forensic.commits.length : 0;
    const discussions = Array.isArray(forensic.discussions) ? forensic.discussions.length : 0;
    if (commits) bits.push(`${commits} commit${commits === 1 ? "" : "s"}`);
    if (discussions) bits.push(`${discussions} discussion${discussions === 1 ? "" : "s"}`);
    if (hasRecoveryCopy(event)) bits.push("Recovery copy");
    return bits;
  }

  function updateStats() {
    const vanished = state.events.filter((event) => group(event) === "vanished").length;
    const restricted = state.events.filter((event) => group(event) === "restricted").length;
    const restored = state.events.filter((event) => group(event) === "restored").length;
    const reasoned = Object.values(state.evidence).filter((row) => String(((row || {}).reason || {}).status || "UNKNOWN").toUpperCase() !== "UNKNOWN").length;
    byId("statEvents").textContent = state.events.length.toLocaleString();
    byId("statVanished").textContent = vanished.toLocaleString();
    byId("statReasoned").textContent = reasoned.toLocaleString();
    byId("statIncidents").textContent = state.incidents.length.toLocaleString();
    byId("statRescued").textContent = Number(state.recoverySummary.rescued || 0).toLocaleString();
    byId("statWatched").textContent = state.watchedCount == null ? "—" : state.watchedCount.toLocaleString();
    byId("statScan").textContent = relativeTime(state.generatedAt);
    byId("countAll").textContent = state.events.length;
    byId("countVanished").textContent = vanished;
    byId("countRestricted").textContent = restricted;
    byId("countRestored").textContent = restored;
  }

  function hashRow(label, value) {
    if (!value) return "";
    return `<div class="hash-row">
      <span class="hash-label">${escapeHtml(label)}</span>
      <code class="hash-value">${escapeHtml(value)}</code>
      <button type="button" class="copy-hash" data-copy="${escapeHtml(value)}">Copy</button>
    </div>`;
  }

  function evidencePanel(event) {
    const forensic = forensicFor(event.id);
    const manifest = manifestFor(event.id);
    const incident = incidentFor(event.id);
    const recovery = recoveryFor(event.id);
    const reason = (forensic && forensic.reason) || { status: "UNKNOWN", category: "unknown", summary: "No public source documenting the cause has been recorded.", sources: [] };
    const sourced = String(reason.status || "UNKNOWN").toUpperCase() !== "UNKNOWN";
    const sources = Array.isArray(reason.sources) ? reason.sources.filter((row) => row && row.url) : [];
    const discussions = forensic && Array.isArray(forensic.discussions) ? forensic.discussions : [];
    const commits = forensic && Array.isArray(forensic.commits) ? forensic.commits : [];
    const signals = forensic && Array.isArray(forensic.reason_signals) ? forensic.reason_signals : [];
    const timeline = forensic && Array.isArray(forensic.timeline) ? forensic.timeline : [];
    const pf = recovery && recovery.pirateface ? recovery.pirateface : null;
    const frost = recovery && recovery.frostbyte ? recovery.frostbyte : null;
    const lp = (recovery && recovery.last_public) || event.last_public || {};
    const open = state.expanded.has(event.id);
    const panelId = `ev-${modelAnchor(event.id)}`;

    const sourceList = sources.length
      ? `<ul>${sources.map((source) => `<li><a href="${escapeHtml(source.url)}" rel="noopener noreferrer">${escapeHtml(source.title || source.label || source.url)}</a>${source.publisher ? ` <span class="empty">(${escapeHtml(source.publisher)})</span>` : ""}</li>`).join("")}</ul>`
      : `<p class="empty">No public source URLs recorded.</p>`;

    const discussionList = discussions.length
      ? `<ul>${discussions.slice(0, 8).map((row) => {
          const href = row.num != null ? `https://huggingface.co/${escapeHtml(event.id)}/discussions/${escapeHtml(row.num)}` : (row.url || event.hf_url);
          return `<li><a href="${escapeHtml(href)}" rel="noopener noreferrer">${escapeHtml(row.title || `Discussion #${row.num}`)}</a></li>`;
        }).join("")}</ul>`
      : "";
    const commitList = commits.length
      ? `<ul>${commits.slice(0, 8).map((row) => `<li><code>${escapeHtml((row.oid || row.sha || row.id || "").slice(0, 10))}</code> ${escapeHtml(row.title || row.message || "commit")}</li>`).join("")}</ul>`
      : "";

    const ctx = [];
    ctx.push(`${discussions.length} discussion${discussions.length === 1 ? "" : "s"}`);
    ctx.push(`${commits.length} commit${commits.length === 1 ? "" : "s"}`);
    ctx.push(exactArchive(event) ? "exact archive snapshot" : (event.wayback_url ? "Wayback index" : "no archive recorded"));
    if (signals.length) ctx.push(`${signals.length} non-causal lead${signals.length === 1 ? "" : "s"}`);
    if (manifest && manifest.completeness) ctx.push(`manifest ${String(manifest.completeness).replaceAll("_", " ").toLowerCase()}`);
    if (event.curr && event.curr.http != null) ctx.push(`HTTP ${event.curr.http}`);
    if (lp.license) ctx.push(`license ${lp.license}`);

    const recoveryBits = [];
    if (recovery && recovery.preservation) recoveryBits.push(`Preservation: ${escapeHtml(preservationLabel(recovery.preservation))}`);
    const recoveryLinks = [];
    if (event.wayback_url) recoveryLinks.push(`<a class="action" href="${escapeHtml(event.wayback_url)}" rel="noopener noreferrer">Wayback</a>`);
    if (pf && pf.url) recoveryLinks.push(`<a class="action" href="${escapeHtml(pf.url)}" rel="noopener noreferrer">Pirate Face</a>`);
    if (pf && pf.magnet) recoveryLinks.push(`<button type="button" class="action copy-magnet" data-magnet="${encodeURIComponent(pf.magnet)}">Copy magnet</button>`);
    if (frost && frost.app_url) recoveryLinks.push(`<a class="action" href="${escapeHtml(frost.app_url)}" rel="noopener noreferrer">FrostByte</a>`);
    if (pf && pf.seeders != null) recoveryBits.push(`${escapeHtml(pf.seeders)} seeder${Number(pf.seeders) === 1 ? "" : "s"}`);

    const incidentBlock = incident
      ? `<div>
          <h3>Incident</h3>
          <p class="incident-id">${escapeHtml(incident.id)}</p>
          <p>${escapeHtml(incident.models.length)} models · ${escapeHtml(((incident.signals || [])[0] && (incident.signals[0].window_hours)) || 24)}h window</p>
          <p class="correlation-note">Correlation signal only. Does not establish cause or coordination.</p>
        </div>`
      : "";

    return `
      <button type="button" class="evidence-toggle" data-expand="${escapeHtml(event.id)}" aria-expanded="${open ? "true" : "false"}" aria-controls="${panelId}">
        Evidence ${open ? "▴" : "▾"}
      </button>
      <div class="evidence-wrap${open ? " open" : ""}" id="${panelId}">
        <div class="evidence-inner">
          <div class="evidence-panel">
            <div>
              <h3>Why</h3>
              <p>${escapeHtml(reason.summary || "No public source documenting the cause has been recorded.")}${sourced ? ` <span class="empty">(${escapeHtml(reasonMeta(reason))})</span>` : ""}</p>
              ${forensic && forensic.reason_signals_note ? `<p class="empty">${escapeHtml(forensic.reason_signals_note)}</p>` : ""}
            </div>
            <div>
              <h3>Public sources</h3>
              ${sourceList}
            </div>
            <div>
              <h3>Forensic context</h3>
              <p class="ctx-line">${escapeHtml(ctx.join(" · "))}</p>
              ${discussionList}
              ${commitList}
              ${timeline.length ? `<p class="empty">${timeline.length} timeline entries captured.</p>` : ""}
            </div>
            <div>
              <h3>Identity</h3>
              ${hashRow("Evidence SHA", forensic && forensic.evidence_sha256)}
              ${hashRow("Manifest root", (manifest && manifest.root_sha256) || (forensic && forensic.manifest_root_sha256))}
              ${hashRow("Hub revision", hubRevision(event))}
              ${hashRow("Model card SHA", forensic && forensic.readme_sha256)}
              ${!(forensic && forensic.evidence_sha256) && !(manifest && manifest.root_sha256) && !hubRevision(event) ? `<p class="empty">No hash identity recorded yet.</p>` : ""}
            </div>
            ${incidentBlock}
            <div>
              <h3>Recovery</h3>
              ${recoveryBits.length ? `<p class="ctx-line">${recoveryBits.join(" · ")}</p>` : `<p class="empty">No verified surviving copy recorded.</p>`}
              ${recoveryLinks.length ? `<div class="recovery-links">${recoveryLinks.join("")}</div>` : ""}
            </div>
          </div>
        </div>
      </div>`;
  }

  function render() {
    const rows = filteredEvents(); updateStats();
    byId("meta").textContent = `${rows.length} shown · ${state.events.length} recorded · scan ${relativeTime(state.generatedAt)}`;
    if (!rows.length) { byId("feed").innerHTML = '<article class="item muted">No recorded events match.</article>'; return; }

    byId("feed").innerHTML = rows.map((event) => {
      const rawStatus = String(event.status || "UNKNOWN").toUpperCase();
      const current = displayStatus(event);
      const recovery = recoveryFor(event.id);
      const lp = (recovery && recovery.last_public) || event.last_public || {};
      const forensic = forensicFor(event.id);
      const reason = (forensic && forensic.reason) || { status: "UNKNOWN" };
      const incident = incidentFor(event.id);
      const bits = evidenceBits(event);

      return `<article class="item" id="${modelAnchor(event.id)}">
        <div class="item-top">
          <div class="id">${escapeHtml(event.id || "unknown")}</div>
          <div class="detected">${escapeHtml(dateOnly(event.detected_at))}</div>
        </div>
        <span class="badge ${chipClass[rawStatus] || ""}">${escapeHtml(current)}</span>
        <div class="transition">
          <span><span class="lbl">Before</span><span class="before">${escapeHtml(before(event))}</span></span>
          <span class="arrow" aria-hidden="true">→</span>
          <span><span class="lbl">Now</span><span class="now">${escapeHtml(current)}</span></span>
        </div>
        <p class="summary">${escapeHtml(event.summary || "Observed availability change.")}</p>
        <div class="meta-rows">
          <div><span class="k">Reason</span> ${escapeHtml(reasonMeta(reason))}</div>
          <div><span class="k">Evidence</span> ${escapeHtml(bits.length ? bits.join(" · ") : "None recorded")}</div>
          ${incident ? `<div><span class="k">Incident</span> <span class="incident-id">${escapeHtml(incident.id)}</span></div>` : ""}
        </div>
        ${snapshotBlock(lp)}
        <div class="actions">
          ${event.hf_url ? `<a class="action" href="${escapeHtml(event.hf_url)}" rel="noopener noreferrer">Current Hub</a>` : ""}
          <a class="action" href="${escapeHtml(mirrorSearchUrl(event.id))}" rel="noopener noreferrer">Find copies</a>
          ${evidencePanel(event)}
        </div>
      </article>`;
    }).join("");
  }

  document.querySelectorAll(".mode").forEach((button) => button.addEventListener("click", () => {
    state.mode = button.dataset.mode;
    document.querySelectorAll(".mode").forEach((item) => {
      item.classList.toggle("active", item === button);
      item.setAttribute("aria-selected", item === button ? "true" : "false");
    });
    render();
  }));

  const filtersToggle = byId("filtersToggle");
  const filtersPanel = byId("filtersPanel");
  filtersToggle.addEventListener("click", () => {
    const open = filtersToggle.getAttribute("aria-expanded") === "true";
    filtersToggle.setAttribute("aria-expanded", open ? "false" : "true");
    filtersPanel.hidden = open;
    const chevron = filtersToggle.querySelector(".chevron");
    if (chevron) chevron.textContent = open ? "▾" : "▴";
  });
  filtersPanel.addEventListener("change", (event) => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "checkbox") return;
    const bucket = input.name === "status" ? state.statusFilters : input.name === "reason" ? state.reasonFilters : state.evidenceFilters;
    if (input.checked) bucket.add(input.value); else bucket.delete(input.value);
    render();
  });

  byId("q").addEventListener("input", (event) => { state.q = event.target.value; render(); });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
    const tag = (event.target && event.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || event.target.isContentEditable) return;
    event.preventDefault();
    byId("q").focus();
  });

  byId("feed").addEventListener("click", async (event) => {
    const expand = event.target.closest("[data-expand]");
    if (expand) {
      const id = expand.getAttribute("data-expand");
      if (state.expanded.has(id)) state.expanded.delete(id); else state.expanded.add(id);
      const wrap = document.getElementById(`ev-${modelAnchor(id)}`);
      const open = state.expanded.has(id);
      expand.setAttribute("aria-expanded", open ? "true" : "false");
      expand.textContent = open ? "Evidence ▴" : "Evidence ▾";
      if (wrap) wrap.classList.toggle("open", open);
      return;
    }
    const copyHash = event.target.closest(".copy-hash");
    if (copyHash) {
      const value = copyHash.getAttribute("data-copy") || "";
      try { await navigator.clipboard.writeText(value); copyHash.textContent = "Copied"; copyHash.classList.add("copied"); setTimeout(() => { copyHash.textContent = "Copy"; copyHash.classList.remove("copied"); }, 1600); }
      catch { window.prompt("Copy hash:", value); }
      return;
    }
    const magnet = event.target.closest(".copy-magnet");
    if (!magnet) return;
    const value = decodeURIComponent(magnet.dataset.magnet || ""); if (!value) return;
    try { await navigator.clipboard.writeText(value); magnet.textContent = "Magnet copied"; setTimeout(() => { magnet.textContent = "Copy magnet"; }, 1800); }
    catch { window.prompt("Copy this magnet into FrostByte or another torrent client:", value); }
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
    if (location.hash.length > 1) {
      const element = document.getElementById(location.hash.slice(1));
      if (element) {
        element.classList.add("focus-card");
        const id = decodeURIComponent(location.hash.slice(1));
        if (state.events.some((row) => row.id === id)) { state.expanded.add(id); render(); document.getElementById(location.hash.slice(1))?.classList.add("focus-card"); }
      }
    }
  }).catch((error) => {
    byId("feed").innerHTML = `<article class="item muted">Failed to load ledger (${escapeHtml(error.message)}).</article>`;
    byId("meta").textContent = "offline / missing data";
  });
})();
