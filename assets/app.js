(() => {
  const CHIP = {
    DISABLED: "dis",
    DELETED: "del",
    GATED: "gate",
    PRIVATE: "priv",
    STRIPPED: "strip",
  };

  const state = {
    events: [],
    generatedAt: null,
    filterStatus: null,
    hardOnly: false,
    q: "",
  };

  const feed = document.getElementById("feed");
  const meta = document.getElementById("meta");
  const qInput = document.getElementById("q");
  const hardOnly = document.getElementById("hardOnly");

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function filtered() {
    const q = state.q.trim().toLowerCase();
    return state.events.filter((e) => {
      if (state.hardOnly && e.severity !== "hard") return false;
      if (state.filterStatus && (e.status || "").toUpperCase() !== state.filterStatus) return false;
      if (!q) return true;
      const hay = `${e.id || ""} ${e.summary || ""} ${e.status || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }

  function render() {
    const rows = filtered();
    meta.textContent = `${rows.length} shown · ${state.events.length} total` +
      (state.generatedAt ? ` · generated ${state.generatedAt}` : "");

    if (!rows.length) {
      feed.innerHTML = `<div class="item muted">No events match.</div>`;
      return;
    }

    feed.innerHTML = rows
      .map((e) => {
        const st = String(e.status || "UNKNOWN").toUpperCase();
        const cls = CHIP[st] || "";
        const sev = e.severity === "hard" ? "hard" : "soft";
        const links = [];
        if (e.hf_url) links.push(`<a href="${esc(e.hf_url)}" rel="noopener noreferrer">Hub</a>`);
        if (e.wayback_url) {
          links.push(`<a href="${esc(e.wayback_url)}" rel="noopener noreferrer">Wayback last-public</a>`);
        }
        const prev = e.prev || {};
        const curr = e.curr || {};
        const diffBits = [];
        if (prev.visibility || curr.visibility) {
          diffBits.push(`vis ${esc(prev.visibility || "—")} → ${esc(curr.visibility || "—")}`);
        }
        if (prev.gated !== undefined || curr.gated !== undefined) {
          diffBits.push(`gated ${esc(JSON.stringify(prev.gated))} → ${esc(JSON.stringify(curr.gated))}`);
        }
        if (prev.weight_count != null || curr.weight_count != null) {
          diffBits.push(`weights ${esc(prev.weight_count ?? "—")} → ${esc(curr.weight_count ?? "—")}`);
        }
        return `
          <article class="item">
            <div class="top">
              <span class="chip ${cls}">${esc(st)}</span>
              <span class="badge ${sev}">${esc(sev.toUpperCase())}</span>
            </div>
            <div class="id">${esc(e.id || "unknown")}</div>
            <div class="summary">${esc(e.summary || "")}</div>
            <div class="row">
              <span>${esc(e.detected_at || "")}</span>
              ${diffBits.length ? `<span>${diffBits.join(" · ")}</span>` : ""}
              <span>${links.join(" · ")}</span>
            </div>
          </article>`;
      })
      .join("");
  }

  document.querySelectorAll(".legend .chip").forEach((el) => {
    el.addEventListener("click", () => {
      const v = el.getAttribute("data-filter");
      if (state.filterStatus === v) {
        state.filterStatus = null;
        el.classList.remove("active");
      } else {
        state.filterStatus = v;
        document.querySelectorAll(".legend .chip").forEach((c) => c.classList.remove("active"));
        el.classList.add("active");
      }
      render();
    });
  });

  qInput.addEventListener("input", () => {
    state.q = qInput.value;
    render();
  });
  hardOnly.addEventListener("change", () => {
    state.hardOnly = hardOnly.checked;
    render();
  });

  fetch("data/events.json", { cache: "no-store" })
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((data) => {
      state.events = data.events || [];
      state.generatedAt = data.generated_at || null;
      render();
    })
    .catch((err) => {
      feed.innerHTML = `<div class="item muted">Failed to load events.json (${esc(err.message)}).</div>`;
      meta.textContent = "offline / missing data";
    });
})();
