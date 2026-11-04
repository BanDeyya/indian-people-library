"use strict";
// Catalogue for the Indian People Library. Reads data/index.json (one row per public character) and
// loads data/regions/<slug>.json only when a state or a character is opened. No tracking, no cookies.

const REPO = "BanDeyya/indian-people-library";
const PAGE = 48;
// Monk Skin Tone scale swatches (Google, CC BY 4.0), 1 = lightest.
const MST = ["#f6ede4", "#f3e7db", "#f7ead0", "#eadaba", "#d7bd96", "#a07e56", "#825c43", "#604134", "#3a312a", "#292420"];
const REL_COLORS = { hindu: "#d9822b", muslim: "#2f8f5b", christian: "#3b6fb6", sikh: "#c9a227", buddhist: "#8a5fb0",
  jain: "#c45c8a", other: "#7d8a8f" };
const SETTINGS = { rural: "rural", urban: "urban" };

const $ = (id) => document.getElementById(id);
const num = (n) => (Number.isFinite(Number(n)) ? Number(n) : 0);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : "");

let INDEX = null, ROWS = [], shown = 0, filtered = [];
const regionCache = new Map();

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}
async function region(slug) {
  if (!INDEX.regions.some((r) => r.slug === slug)) throw new Error(`unknown region ${slug}`);
  if (!regionCache.has(slug)) regionCache.set(slug, getJSON(`data/regions/${slug}.json`));
  return regionCache.get(slug);
}

function opt(sel, value, label) {
  const o = document.createElement("option");
  o.value = value; o.textContent = label; sel.appendChild(o);
}
function resetSelect(sel, firstLabel, disabled) {
  sel.innerHTML = ""; opt(sel, "", firstLabel); sel.disabled = disabled;
}

function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  for (const k of ["q", "region", "group", "religion", "xstate", "setting", "origin"]) if (p.has(k)) $(k).value = p.get(k);
  return p;
}
function writeHash(extra = {}) {
  const p = new URLSearchParams();
  for (const k of ["q", "region", "group", "religion", "xstate", "community", "festival", "setting", "origin"]) {
    const v = $(k).value; if (v) p.set(k, v);
  }
  for (const [k, v] of Object.entries(extra)) if (v) p.set(k, v);
  history.replaceState(null, "", p.toString() ? `#${p}` : location.pathname);
}

async function onRegionChange(keep = {}) {
  const slug = $("region").value;
  const comm = $("community"), fest = $("festival"), card = $("region-card");
  if (!slug) {
    resetSelect(comm, "Pick a state first", true); resetSelect(fest, "Pick a state first", true);
    card.hidden = true; return;
  }
  const r = await region(slug);
  resetSelect(comm, "Any", false);
  const used = new Set(ROWS.filter((x) => x.region === slug).map((x) => x.community));
  for (const c of r.communities) if (used.has(c.id)) opt(comm, c.id, c.culture && c.culture !== c.name ? `${c.name} (${c.culture})` : c.name);
  resetSelect(fest, "Any", false);
  for (const [id, name] of Object.entries(INDEX.festivals[slug] || {})) opt(fest, id, name);
  if (keep.community) comm.value = keep.community;
  if (keep.festival) fest.value = keep.festival;
  const mix = Object.entries(r.religion_mix?.shares || {}).sort((a, b) => b[1] - a[1]);
  card.innerHTML = `<h2>${esc(r.name)}</h2>
    <p>${esc(cap(r.type))} · capital ${esc(r.capital || "—")} · ${esc(r.languages.slice(0, 6).join(", "))}</p>
    <div class="mix" role="img" aria-label="Religion shares, Census 2011">${mix.map(([k, v]) =>
      `<span style="width:${num(v)}%;background:${REL_COLORS[k] || REL_COLORS.other}" title="${esc(cap(k))} ${num(v).toFixed(1)}%"></span>`).join("")}</div>
    <p class="note">Census 2011: ${mix.filter(([, v]) => num(v) >= 1).map(([k, v]) => `${esc(cap(k))} ${num(v).toFixed(1)}%`).join(" · ")}</p>`;
  card.hidden = false;
}

function apply() {
  const q = $("q").value.trim().toLowerCase();
  const f = { region: $("region").value, group: $("group").value, religion: $("religion").value, xstate: $("xstate").value,
    community: $("community").value, festival: $("festival").value, setting: $("setting").value, origin: $("origin").value };
  filtered = ROWS.filter((r) =>
    (!q || r.name.toLowerCase().includes(q) || r.id.toLowerCase().includes(q)) &&
    (!f.region || r.region === f.region) && (!f.group || r.group === f.group) &&
    (!f.religion || (r.religion || "unspecified") === f.religion) && (!f.xstate || r.groups.includes(f.xstate)) &&
    (!f.community || r.community === f.community) && (!f.festival || r.festivals.includes(f.festival)) &&
    (!f.setting || r.setting === f.setting) && (!f.origin || r.origin === f.origin));
  shown = 0; $("grid").innerHTML = "";
  $("count").textContent = `${filtered.length.toLocaleString("en-IN")} of ${ROWS.length.toLocaleString("en-IN")} characters`;
  more(); writeHash();
}

function more() {
  const grid = $("grid"), regionName = Object.fromEntries(INDEX.regions.map((r) => [r.slug, r.name]));
  const frag = document.createDocumentFragment();
  for (const r of filtered.slice(shown, shown + PAGE)) {
    const li = document.createElement("li"); li.className = "card";
    li.innerHTML = `<button type="button" data-id="${esc(r.id)}" data-region="${esc(r.region)}">
      <span class="swatch" style="background:${MST[num(r.skin) - 1] || MST[4]}" aria-hidden="true"></span>
      <span><span class="name">${esc(r.name)}</span><br>
      <span class="meta">${esc(INDEX.groups[r.group])}, ${num(r.age)} · ${esc(r.culture || r.community_name)}</span><br>
      <span class="meta">${esc(regionName[r.region])}</span><br>
      <span class="chip">${esc(r.community_name)}</span> ${r.origin === "generated" ? '<span class="chip">generated</span>' : ""}</span>
    </button>`;
    frag.appendChild(li);
  }
  grid.appendChild(frag);
  shown = Math.min(shown + PAGE, filtered.length);
  $("more").hidden = shown >= filtered.length;
}

async function openCharacter(slug, id) {
  const r = await region(slug);
  const c = r.characters.find((x) => x.id === id);
  if (!c) return;
  const items = (slot) => c.wardrobe.filter((w) => slot(w.slot));
  const main = items((s) => ["full", "lower", "upper"].includes(s)), rest = items((s) => !["full", "lower", "upper"].includes(s));
  const issue = new URL(`https://github.com/${REPO}/issues/new`);
  issue.searchParams.set("template", "character-report.md");
  issue.searchParams.set("title", `Report: ${c.id} ${c.name} (${r.name})`);
  $("detail-body").innerHTML = `
    <h2 id="d-name">${esc(c.name)}</h2>
    <p class="note">${esc(c.id)} · ${esc(INDEX.groups[c.group])}, ${num(c.age)} · ${esc(r.name)}${c.sub_region ? `, ${esc(c.sub_region)}` : ""} ·
      ${c.origin === "generated" ? "generated draft" : "hand-made"}</p>
    <dl class="kv">
      <dt>Community</dt><dd>${esc(c.community_name)}${c.culture && c.culture !== c.community_name ? ` · ${esc(c.culture)}` : ""}</dd>
      <dt>Setting</dt><dd>${esc(SETTINGS[c.setting] || c.setting)}${c.occupation ? ` · ${esc(c.occupation)}` : ""}</dd>
      <dt>Marital status</dt><dd>${esc(c.marital_status)}</dd>
      <dt>Languages</dt><dd>${esc(c.language.join(", "))}</dd>
    </dl>
    <h3>Look</h3>
    <dl class="kv">
      <dt>Skin</dt><dd><span class="swatch" style="display:inline-block;width:14px;height:14px;vertical-align:-2px;background:${MST[num(c.look.skin_tone_mst) - 1] || MST[4]}"></span>
        Monk scale ${num(c.look.skin_tone_mst)} (${esc(c.look.skin_words)})</dd>
      <dt>Face</dt><dd>${esc(c.look.face)}, ${esc(c.look.eyes || "")}</dd>
      <dt>Hair</dt><dd>${esc(c.look.hair)}${c.look.facial_hair ? `, ${esc(c.look.facial_hair)}` : ""}</dd>
      <dt>Build</dt><dd>${esc(c.look.build)}</dd>
      <dt>Mark</dt><dd>${esc(c.look.signature_mark)}</dd>
    </dl>
    <h3>Clothes</h3>
    <ul>${main.map((w) => `<li>${esc(w.name)} <span class="note">(${esc(w.occasion.join(", ").replaceAll("_", " "))})</span></li>`).join("")}</ul>
    ${rest.length ? `<h3>Accessories and layers</h3><ul>${rest.map((w) => `<li>${esc(w.name)}</li>`).join("")}</ul>` : ""}
    ${c.festivals.length ? `<h3>Festivals and rites</h3><ul>${c.festivals.map((f) =>
      `<li><strong>${esc(f.name)}</strong>${f.when ? ` <span class="note">${esc(f.when)}</span>` : ""}<br><span class="note">wears ${esc(f.outfit.join(", "))}</span></li>`).join("")}</ul>` : ""}
    ${c.prompt ? `<h3>Portrait prompt (long-text models)</h3>
      <pre class="prompt" id="p-text">${esc(c.prompt)}</pre>
      <details><summary class="note">Negative prompt</summary><pre class="prompt">${esc(c.negative_prompt)}</pre></details>
      <div class="row"><button class="btn" type="button" id="copy">Copy prompt</button>
      <span class="note">Other model families (SDXL, SD 1.5, FLUX…): run <code>scripts/compile_prompts.py --profile …</code></span></div>` : ""}
    <h3>Something wrong?</h3>
    <p class="row"><a class="btn ghost" href="${issue}" rel="noopener" target="_blank">Report a problem</a>
      <span class="note">Wrong dress, a stereotype, a name that marks caste, or anything disrespectful.</span></p>`;
  const copy = $("copy");
  if (copy) copy.onclick = async () => {
    try { await navigator.clipboard.writeText(c.prompt); copy.textContent = "Copied"; } catch { copy.textContent = "Select and copy the text"; }
  };
  const d = $("detail");
  if (!d.open) d.showModal();
  writeHash({ c: `${slug}/${id}` });
}

async function main() {
  $("repo-link").href = `https://github.com/${REPO}`;
  try { INDEX = await getJSON("data/index.json"); } catch (e) {
    $("count").textContent = "Could not load the catalogue data. Run scripts/build_site.py first."; return;
  }
  ROWS = INDEX.rows.map((row) => Object.fromEntries(INDEX.fields.map((k, i) => [k, row[i]])));
  for (const r of INDEX.regions) opt($("region"), r.slug, r.name);
  for (const [k, v] of Object.entries(INDEX.groups)) if (ROWS.some((r) => r.group === k)) opt($("group"), k, v);
  const rels = [...new Set(ROWS.map((r) => r.religion || "unspecified"))].sort();
  for (const k of rels) opt($("religion"), k, k === "unspecified" ? "Not one religion (many tribal communities)" : cap(k));
  for (const g of INDEX.cross_state) opt($("xstate"), g.id, g.name);

  const p = readHash();
  await onRegionChange({ community: p.get("community"), festival: p.get("festival") }).catch(() => { $("region").value = ""; });
  apply();
  if (p.get("c")) { const [s, id] = p.get("c").split("/"); openCharacter(s, id).catch(() => {}); }

  for (const id of ["group", "religion", "xstate", "community", "festival", "setting", "origin"]) $(id).addEventListener("change", apply);
  $("region").addEventListener("change", async () => { await onRegionChange().catch(() => {}); apply(); });
  let t; $("q").addEventListener("input", () => { clearTimeout(t); t = setTimeout(apply, 150); });
  $("more").addEventListener("click", more);
  $("reset").addEventListener("click", async () => {
    for (const id of ["q", "region", "group", "religion", "xstate", "setting", "origin"]) $(id).value = "";
    await onRegionChange(); apply();
  });
  $("grid").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-id]"); if (b) openCharacter(b.dataset.region, b.dataset.id).catch(() => {});
  });
  $("detail").addEventListener("close", () => writeHash());
}
main();
