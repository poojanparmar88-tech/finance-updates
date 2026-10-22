"use strict";

const REGULATORS = ["Income Tax", "GST", "MCA", "RBI", "Supreme Court", "High Court"];
const app = document.getElementById("app");
const state = { feed: [], filter: "All", query: "" };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const SOURCE_LABEL = { official: "Official source", judgment: "Judgment text", news: "News report" };
const sourceBadge = (t) => t ? `<span class="badge src-${esc(t)}">${SOURCE_LABEL[t] || esc(t)}</span>` : "";
const regVar = (r) => `var(--c-${String(r).toLowerCase().replace(/\s+/g, "-")})`;
const fmtDay = (iso) => new Date(iso).toLocaleDateString("en-IN",
  { weekday: "short", day: "numeric", month: "short", year: "numeric" });

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.remove("show"), 1800);
}

async function getJSON(url) {
  const res = await fetch(url, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.json();
}

/* ---------- List view ---------- */

function renderList() {
  const q = state.query.toLowerCase();
  const items = state.feed.filter((p) =>
    (state.filter === "All" || p.regulator === state.filter) &&
    (!q || `${p.headline} ${p.reference} ${p.category}`.toLowerCase().includes(q)));

  let html = `<div class="filters" role="toolbar" aria-label="Filter by regulator">` +
    ["All", ...REGULATORS].map((r) =>
      `<button class="chip" data-filter="${esc(r)}" aria-pressed="${r === state.filter}">${esc(r)}</button>`
    ).join("") + `</div>
    <input class="search" type="search" placeholder="Search headline, notification no., case…"
      value="${esc(state.query)}" aria-label="Search updates">`;

  if (state.feed.some((p) => p.sample)) {
    html += `<div class="sample-note">These are sample posts showing the layout. They are
      replaced automatically once the first live run finds real updates.</div>`;
  }
  if (!items.length) {
    html += `<p class="empty">No updates${state.filter !== "All" ? ` for ${esc(state.filter)}` : ""} yet.</p>`;
  }
  let lastDay = "";
  for (const p of items) {
    const day = fmtDay(p.created_at);
    if (day !== lastDay) { html += `<div class="day">${esc(day)}</div>`; lastDay = day; }
    html += `<a class="card" href="#/p/${esc(p.id)}" style="--reg:${regVar(p.regulator)}">
      <img class="thumb" src="posts/${esc(p.id)}.png" alt="" loading="lazy">
      <div>
        <div class="meta"><span class="reg">${esc(p.regulator)}</span><span>${esc(p.category)}</span>
          ${p.sample ? `<span class="badge">Sample</span>` : sourceBadge(p.source_type)}
          ${p.format === "table" ? `<span class="badge">Table</span>` : ""}</div>
        <h2>${esc(p.headline)}</h2>
        ${p.reference ? `<div class="meta">${esc(p.reference)}</div>` : ""}
      </div></a>`;
  }
  app.innerHTML = html;

  app.querySelectorAll("[data-filter]").forEach((b) => b.addEventListener("click", () => {
    state.filter = b.dataset.filter;
    renderList();
  }));
  const search = app.querySelector(".search");
  search.addEventListener("input", () => {
    state.query = search.value;
    const pos = search.selectionStart;
    renderList();
    const s = app.querySelector(".search");
    s.focus();
    s.setSelectionRange(pos, pos);
  });
}

/* ---------- Post view ---------- */

const CAPTIONS = [["linkedin", "LinkedIn"], ["instagram", "Instagram"], ["x", "X"], ["whatsapp", "WhatsApp"]];

function captionText(p, key) {
  const tags = (p.social.hashtags || []).join(" ");
  return key === "whatsapp" ? p.social[key] : `${p.social[key]}\n\n${tags}`.trim();
}

async function renderPost(id) {
  app.innerHTML = `<p class="empty">Loading…</p>`;
  let p;
  try {
    p = await getJSON(`posts/${encodeURIComponent(id)}.json`);
  } catch {
    app.innerHTML = `<a class="back" href="#/">← All updates</a><p class="empty">This update is no longer available.</p>`;
    return;
  }
  document.title = `${p.headline} · Finance Update Hub`;
  const img = `posts/${encodeURIComponent(p.id)}.png`;
  const table = p.table && p.table.columns && p.table.columns.length ? `
    <div class="section"><h3>At a glance</h3><div class="table-wrap"><table>
      <thead><tr>${p.table.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${p.table.rows.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div></div>` : "";

  app.innerHTML = `
    <a class="back" href="#/">← All updates</a>
    ${p.sample ? `<div class="sample-note">Sample post — illustrative layout only, not a real update.</div>` : ""}
    <div class="post-grid post" style="--reg:${regVar(p.regulator)}">
      <div class="post-media">
        <img src="${img}" alt="Social media post image: ${esc(p.headline)}" width="1080" height="1350">
        <div class="actions">
          <a class="btn primary" href="${img}" download="${esc(p.id)}.png" id="save">Save image</a>
          <button class="btn" id="share">Share</button>
        </div>
      </div>
      <div>
        <div class="meta"><span class="reg">${esc(p.regulator)}</span><span>${esc(p.category)}</span>
          ${p.sample ? "" : sourceBadge(p.source_type)}</div>
        ${p.source_type === "news" ? `<div class="sample-note">Based on a news report, not the official
          document. Check the official notification before posting.</div>` : ""}
        <h1>${esc(p.headline)}</h1>
        <dl class="kv">
          ${p.reference ? `<dt>Reference</dt><dd>${esc(p.reference)}</dd>` : ""}
          ${p.issued_on ? `<dt>Issued</dt><dd>${esc(p.issued_on)}</dd>` : ""}
          ${p.effective_from ? `<dt>Effective</dt><dd>${esc(p.effective_from)}</dd>` : ""}
          ${p.source_url && !p.sample ? `<dt>Source</dt><dd><a href="${esc(p.source_url)}" target="_blank" rel="noopener">${esc(p.source_domain)}</a></dd>` : ""}
        </dl>
        <div class="section"><h3>Summary</h3>
          <ul>${p.summary_points.map((s) => `<li>${esc(s)}</li>`).join("")}</ul></div>
        ${table}
        <div class="section"><h3>Who is affected</h3><p style="margin:0">${esc(p.who_is_affected)}</p></div>
        <div class="section"><h3>Action required</h3><p style="margin:0">${esc(p.action_required)}</p></div>
        <div class="section"><h3>Captions</h3>
          <div class="tabs" role="tablist">${CAPTIONS.map(([k, label], i) =>
            `<button class="chip" role="tab" data-cap="${k}" aria-pressed="${i === 0}">${label}</button>`).join("")}</div>
          <p class="caption" id="caption"></p>
          <button class="btn" id="copy">Copy caption</button>
        </div>
      </div>
    </div>`;

  let current = CAPTIONS[0][0];
  const capEl = document.getElementById("caption");
  const showCap = () => { capEl.textContent = captionText(p, current); };
  showCap();
  app.querySelectorAll("[data-cap]").forEach((b) => b.addEventListener("click", () => {
    current = b.dataset.cap;
    app.querySelectorAll("[data-cap]").forEach((x) => x.setAttribute("aria-pressed", x === b));
    showCap();
  }));

  document.getElementById("copy").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(captionText(p, current)); toast("Caption copied"); }
    catch { toast("Copy not allowed here — long-press the text instead"); }
  });

  // On phones, the share sheet is the reliable way to "Save Image" to Photos/Gallery.
  document.getElementById("share").addEventListener("click", async () => {
    try {
      const blob = await (await fetch(img)).blob();
      const file = new File([blob], `${p.id}.png`, { type: "image/png" });
      const text = captionText(p, current);
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], text, title: p.headline });
      } else if (navigator.share) {
        await navigator.share({ title: p.headline, text, url: location.href });
      } else {
        await navigator.clipboard.writeText(location.href);
        toast("Link copied");
      }
    } catch (e) {
      if (e.name !== "AbortError") toast("Sharing isn't available on this device");
    }
  });
}

/* ---------- Router ---------- */

async function loadFeed() {
  try {
    state.feed = await getJSON("data/updates.json");
    if (state.feed[0]) {
      document.getElementById("updated").textContent =
        "Updated " + new Date(state.feed[0].created_at).toLocaleString("en-IN",
          { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    }
  } catch {
    state.feed = [];
  }
}

async function route() {
  const m = location.hash.match(/^#\/p\/([\w-]+)/);
  if (m) {
    await renderPost(m[1]);
  } else {
    document.title = "Finance Update Hub";
    if (!state.feed.length) await loadFeed();
    renderList();
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
document.addEventListener("visibilitychange", async () => {
  if (document.visibilityState === "visible" && !location.hash.startsWith("#/p/")) {
    await loadFeed();
    renderList();
  }
});
route();

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
