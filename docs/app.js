/**
 * ¿Cómo Votó? - Interactive Frontend
 * ====================================
 * Features:
 *   - Search legislators by name, bloc, province
 *   - Filter by chamber, coalition, year, law name
 *   - Waffle/grid visualization grouped by law
 *   - Law search with per-coalition vote breakdown
 *   - Alignment charts (line + bar)
 *   - Vote history table with pagination
 *   - Copy image / Share to Twitter
 */

// ===========================================================================
//  GLOBALS
// ===========================================================================

let legislatorsData = [];
let lawsData = [];           // loaded from laws_detail.json
let currentSelectedLaw = null;  // currently displayed law in the detail card
let currentDetail = null;
let currentLegKey = null; // The data-key used to load current legislator
let chartAlignment = null;
let chartYearly = null;
let currentVotesPage = 1;
let currentWafflePage = 1;
let loadRequestId = 0; // Guard against stale async loads
const VOTES_PER_PAGE = 25;
const LAWS_PER_PAGE = 10;

const DATA_PATH = "data";

// ===========================================================================
//  SEARCH
// ===========================================================================

function onSearchInput({ requireQuery = true } = {}) {
    const query = document.getElementById("search-input").value.trim().toLowerCase();
    const chamber = document.getElementById("filter-chamber").value;
    const coalition = document.getElementById("filter-coalition").value;
    const province = (document.getElementById("filter-province")?.value || "").trim();

    // Filters alone (no text query) should not open the results dropdown
    // unless explicitly requested (e.g. on focus).
    if (!query && requireQuery) {
        hideSearchResults();
        return;
    }

    let results = legislatorsData;

    if (chamber) {
        results = results.filter((l) => l.c.includes(chamber));
    }
    if (coalition) {
        results = results.filter((l) => l.co === coalition);
    }
    if (province) {
        const pv = province.toLowerCase();
        results = results.filter((l) => (l.p || "").toLowerCase() === pv);
    }
    if (query) {
        const terms = query.split(/\s+/);
        results = results.filter((l) => {
            const searchable = `${l.n} ${l.b} ${l.p}`.toLowerCase();
            return terms.every((t) => searchable.includes(t));
        });
    }

    results.sort((a, b) => (b.tv || 0) - (a.tv || 0));
    results = results.slice(0, 50);

    renderSearchResults(results);
}

function renderSearchResults(results) {
    const container = document.getElementById("search-results");
    container.classList.remove("hidden");

    if (results.length === 0) {
        container.innerHTML = `<div class="search-result-item" style="justify-content:center; cursor:default; color: var(--color-text-secondary);">No se encontraron resultados</div>`;
        return;
    }

    container.innerHTML = results
        .map(
            (l) => `
        <div class="search-result-item" data-key="${l.k}">
            <div class="search-result-name">${highlightMatch(l.n)}</div>
            <div class="search-result-meta">
                ${chamberBadges(l.c)}
                <span class="badge badge-${l.co.toLowerCase()}">${l.co}</span>
                <span class="badge" style="background:#f1f5f9">${l.p || ""}</span>
            </div>
        </div>`
        )
        .join("");

    container.querySelectorAll(".search-result-item[data-key]").forEach((el) => {
        el.addEventListener("click", () => loadLegislatorDetail(el.dataset.key));
    });
}

function chamberBadges(chamberStr) {
    if (!chamberStr) return "";
    const parts = chamberStr.split("+");
    return parts.map((c) => {
        const label = c === "diputados" ? "Dip." : "Sen.";
        return `<span class="badge badge-${c}">${label}</span>`;
    }).join("");
}

function highlightMatch(name) {
    const query = document.getElementById("search-input").value.trim();
    if (!query) return escapeHtml(name);
    const regex = new RegExp(`(${escapeRegex(query)})`, "gi");
    return escapeHtml(name).replace(regex, "<strong>$1</strong>");
}

function hideSearchResults() {
    document.getElementById("search-results").classList.add("hidden");
}

// ===========================================================================
//  LAW SEARCH SECTION (homepage)
// ===========================================================================

function onLawSearchInput() {
    const query = document.getElementById("law-search").value.trim().toLowerCase();
    const yearVal = document.getElementById("law-year-filter").value;
    const chamberVal = document.getElementById("law-chamber-filter").value;
    const dropdown = document.getElementById("law-search-results");

    let results = lawsData;

    // When no filters and no query, show notable laws on focus
    const hasFilter = yearVal || chamberVal;
    if (!query && !hasFilter) {
        // Show notable (common_name) laws by default
        results = results.filter((l) => l.cn);
    }

    if (yearVal) {
        results = results.filter((l) => String(l.y) === yearVal);
    }
    if (chamberVal) {
        results = results.filter((l) => l.ch === chamberVal);
    }
    if (query) {
        const terms = query.split(/\s+/);
        results = results.filter((l) => {
            const searchable = (l.n || "").toLowerCase();
            return terms.every((t) => searchable.includes(t));
        });
    }

    results = results.slice(0, 40);

    if (results.length === 0) {
        dropdown.innerHTML = `<div class="law-dropdown-item" style="cursor:default; color:var(--color-text-secondary); text-align:center;">Sin resultados</div>`;
        dropdown.classList.remove("hidden");
        return;
    }

    dropdown.innerHTML = results.map((l, idx) => {
        const notable = l.cn ? `<span class="law-dropdown-notable">⭐</span>` : "";
        const chamberBadge = l.ch === "diputados"
            ? `<span class="badge badge-diputados">Dip.</span>`
            : l.ch === "senadores"
            ? `<span class="badge badge-senadores">Sen.</span>`
            : "";
        const yearBadge = l.y ? `<span class="law-dropdown-year">${l.y}</span>` : "";
        return `
        <div class="law-dropdown-item" data-law-idx="${idx}">
            <span class="law-dropdown-name">${notable}${escapeHtml(l.n)}</span>
            <span class="law-dropdown-meta">${yearBadge} ${chamberBadge}</span>
        </div>`;
    }).join("");

    dropdown.classList.remove("hidden");

    // Store filtered results in a closure for click handlers
    const filteredResults = results;
    dropdown.querySelectorAll(".law-dropdown-item[data-law-idx]").forEach((el) => {
        el.addEventListener("click", () => {
            const law = filteredResults[parseInt(el.dataset.lawIdx)];
            if (law) selectLaw(law);
            dropdown.classList.add("hidden");
        });
    });
}

function selectLaw(law) {
    currentSelectedLaw = law;
    const wrapper = document.getElementById("law-detail-wrapper");
    wrapper.classList.remove("hidden");

    // Title
    const titleEl = document.getElementById("law-detail-title");
    titleEl.textContent = law.n || "Ley";

    // Meta: year, chamber, # votaciones
    const metaEl = document.getElementById("law-detail-meta");
    const chamberLabel = law.ch === "diputados" ? "Diputados" : law.ch === "senadores" ? "Senadores" : "";
    const parts = [];
    if (law.y) parts.push(`<span class="badge">${law.y}</span>`);
    if (chamberLabel) {
        const cls = law.ch === "diputados" ? "badge-diputados" : "badge-senadores";
        parts.push(`<span class="badge ${cls}">${chamberLabel}</span>`);
    }
    if (law.vs && law.vs.length > 1) parts.push(`<span class="badge">${law.vs.length} votaciones</span>`);
    metaEl.innerHTML = parts.join(" ");

    // Body: per-votación coalition breakdown
    const body = document.getElementById("law-detail-body");
    const vs = law.vs || [];

    if (vs.length === 0) {
        body.innerHTML = `<div class="law-detail-empty">No hay datos de votación disponibles.</div>`;
    } else {
        body.innerHTML = vs.map((v, vi) => renderLawVotacion(v, vi, vs.length)).join("");
    }

    // Scroll into view
    wrapper.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderLawVotacion(v, idx, totalCount) {
    const coalitions = [
        { key: "pj",  label: "PJ / UxP",  cls: "bar-pj" },
        { key: "ucr", label: "UCR",       cls: "bar-ucr" },
        { key: "pro", label: "PRO",       cls: "bar-pro" },
        { key: "lla", label: "LLA",       cls: "bar-lla" },
        { key: "cc",  label: "CC - ARI",  cls: "bar-cc" },
        { key: "oth", label: "Otros",     cls: "bar-oth" },
    ];

    // Header: section label + full title
    const sectionLabel = v.tp || "";
    const fullTitle = v.t || "";
    const dateStr = v.d || "";
    const result = (v.r || "").toUpperCase();
    let resultBadge = "";
    if (result.includes("AFIRMATIV")) {
        resultBadge = `<span class="law-result law-result-afirm">Aprobado</span>`;
    } else if (result.includes("NEGATIV")) {
        resultBadge = `<span class="law-result law-result-neg">Rechazado</span>`;
    } else if (result) {
        resultBadge = `<span class="law-result">${escapeHtml(v.r)}</span>`;
    }

    // Source link
    let linkHtml = "";
    const href = v.url || "";
    if (href) {
        linkHtml = `<a class="law-votacion-link" href="${escapeAttr(href)}" target="_blank" title="Ver votación original">🔗</a>`;
    }

    // Build bars for each coalition
    const tot = v.tot || [0, 0, 0, 0];
    const totalVotes = tot[0] + tot[1] + tot[2] + tot[3];

    const barsHtml = coalitions.map((c) => {
        const counts = v[c.key] || [0, 0, 0, 0];
        const a = counts[0], n = counts[1], b = counts[2], u = counts[3];
        const coalTotal = a + n + b + u;

        if (coalTotal === 0) return ""; // skip empty coalitions

        const maxBar = Math.max(totalVotes, 1);
        const pctA = (a / maxBar) * 100;
        const pctN = (n / maxBar) * 100;
        const pctB = (b / maxBar) * 100;
        const pctU = (u / maxBar) * 100;

        // Summary text
        const summaryParts = [];
        if (a) summaryParts.push(`${a} ✓`);
        if (n) summaryParts.push(`${n} ✗`);
        if (b) summaryParts.push(`${b} ○`);
        if (u) summaryParts.push(`${u} —`);
        const summary = summaryParts.join("  ");

        return `
        <div class="law-bar-row" data-party="${c.key}">
            <div class="law-bar-label">${c.label}</div>
            <div class="law-bar-track">
                <div class="law-bar-seg bar-afirm" style="width:${pctA}%"></div>
                <div class="law-bar-seg bar-neg" style="width:${pctN}%"></div>
                <div class="law-bar-seg bar-abst" style="width:${pctB}%"></div>
                <div class="law-bar-seg bar-aus" style="width:${pctU}%"></div>
            </div>
            <div class="law-bar-counts">${summary}</div>
        </div>`;
    }).join("");

    // Total row
    const totA = tot[0], totN = tot[1], totB = tot[2], totU = tot[3];
    const totParts = [];
    if (totA) totParts.push(`${totA} ✓`);
    if (totN) totParts.push(`${totN} ✗`);
    if (totB) totParts.push(`${totB} ○`);
    if (totU) totParts.push(`${totU} —`);

    const totalRow = `
    <div class="law-bar-row law-bar-total">
        <div class="law-bar-label">Total</div>
        <div class="law-bar-track">
            <div class="law-bar-seg bar-afirm" style="width:${(totA / Math.max(totalVotes,1)) * 100}%"></div>
            <div class="law-bar-seg bar-neg" style="width:${(totN / Math.max(totalVotes,1)) * 100}%"></div>
            <div class="law-bar-seg bar-abst" style="width:${(totB / Math.max(totalVotes,1)) * 100}%"></div>
            <div class="law-bar-seg bar-aus" style="width:${(totU / Math.max(totalVotes,1)) * 100}%"></div>
        </div>
        <div class="law-bar-counts">${totParts.join("  ")}</div>
    </div>`;

    // Show separator if multiple votaciones
    const showTitle = totalCount > 1;

    return `
    <div class="law-votacion-block${!showTitle ? " law-votacion-single" : ""}" data-vi="${v.vi != null ? v.vi : ''}">
        ${showTitle ? `
        <div class="law-votacion-header">
            <div class="law-votacion-topline">
                ${sectionLabel ? `<span class="law-votacion-type">${escapeHtml(sectionLabel)}</span>` : ""}
                <span class="law-votacion-date">${escapeHtml(dateStr)}</span>
                ${resultBadge}
                ${linkHtml}
            </div>
            ${fullTitle ? `<div class="law-votacion-fullname">${escapeHtml(fullTitle)}</div>` : ""}
        </div>` : `
        <div class="law-votacion-header law-votacion-header-single">
            <span class="law-votacion-date">${escapeHtml(dateStr)}</span>
            ${resultBadge}
            ${linkHtml}
        </div>`}
        <div class="law-bars-container">
            ${barsHtml}
            ${totalRow}
        </div>
        <div class="law-voter-list" style="display:none"></div>
    </div>`;
}

function shareTwitterLaw() {
    if (!currentSelectedLaw) return;
    const name = currentSelectedLaw.n || "una ley";
    const text = `Mirá cómo votó cada bloque "${name}" en el Congreso Argentino 🗳️`;
    const base = window.location.origin + window.location.pathname;
    const url = encodeURIComponent(base);
    const tweetUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${url}`;
    window.open(tweetUrl, "_blank", "width=600,height=400");
}

// ===========================================================================
//  VOTE DETAIL (per-bar click drill-down)
// ===========================================================================

const _votesYearCache = {};   // { year: { n: [...], v: {...} } }
const _votesYearPromise = {}; // { year: Promise }

const PARTY_LABELS = {
    pj: "PJ / UxP", ucr: "UCR", pro: "PRO",
    lla: "LLA", cc: "CC - ARI", oth: "Otros",
};
const VOTE_TYPE_LABELS = ["Afirmativo", "Negativo", "Abstención", "Ausente"];
const VOTE_TYPE_CLASSES = ["voter-afirm", "voter-neg", "voter-abst", "voter-aus"];
const ALL_PARTY_KEYS = ["pj", "ucr", "pro", "lla", "cc", "oth"];

function loadVotesYear(year) {
    if (_votesYearCache[year]) return Promise.resolve(_votesYearCache[year]);
    if (_votesYearPromise[year]) return _votesYearPromise[year];
    _votesYearPromise[year] = fetch(`${DATA_PATH}/votes/votes_${year}.json`)
        .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(data => { _votesYearCache[year] = data; return data; })
        .catch(e => { console.warn(`Failed to load votes for ${year}`, e); delete _votesYearPromise[year]; return null; });
    return _votesYearPromise[year];
}

function resolveVoterNames(yearData, vi) {
    if (!yearData) return null;
    const entry = yearData.v[String(vi)];
    if (!entry) return null;
    const names = yearData.n;
    const resolved = {};
    for (const pk of ALL_PARTY_KEYS) {
        if (!entry[pk]) continue;
        resolved[pk] = entry[pk].map(arr => arr.map(idx => names[idx]));
    }
    return resolved;
}

function onBarSegmentClick(e) {
    const seg = e.target.closest(".law-bar-seg");
    if (!seg) return;
    if (parseFloat(seg.style.width) < 0.01) return;

    const row = seg.closest(".law-bar-row");
    const block = seg.closest(".law-votacion-block");
    if (!block) return;
    const vi = block.dataset.vi;
    if (vi === "" || vi == null) return;

    const listEl = block.querySelector(".law-voter-list");
    if (!listEl) return;

    const year = currentSelectedLaw && currentSelectedLaw.y;
    if (!year) return;

    const party = row.dataset.party || "all";

    let voteIdx = -1;
    if (seg.classList.contains("bar-afirm")) voteIdx = 0;
    else if (seg.classList.contains("bar-neg")) voteIdx = 1;
    else if (seg.classList.contains("bar-abst")) voteIdx = 2;
    else if (seg.classList.contains("bar-aus")) voteIdx = 3;
    if (voteIdx < 0) return;

    const filterKey = `${party}_${voteIdx}`;
    if (listEl.style.display !== "none" && listEl.dataset.filter === filterKey) {
        listEl.style.display = "none";
        listEl.innerHTML = "";
        listEl.dataset.filter = "";
        return;
    }

    listEl.style.display = "block";
    listEl.dataset.filter = filterKey;
    listEl.innerHTML = `<div class="voter-loading">Cargando…</div>`;

    loadVotesYear(year).then(yearData => {
        if (listEl.dataset.filter !== filterKey) return;
        const detail = resolveVoterNames(yearData, vi);
        if (!detail) {
            listEl.innerHTML = `<div class="voter-loading">No hay datos disponibles.</div>`;
            return;
        }
        renderVoterList(listEl, detail, party, voteIdx);
    });
}

function renderVoterList(listEl, detail, party, voteIdx) {
    const parties = party === "all" ? ALL_PARTY_KEYS : [party];
    const voteLabel = VOTE_TYPE_LABELS[voteIdx];
    const voteCls = VOTE_TYPE_CLASSES[voteIdx];

    // Collect voters grouped by party
    let totalCount = 0;
    const groups = [];
    for (const pk of parties) {
        const names = (detail[pk] && detail[pk][voteIdx]) || [];
        if (names.length === 0) continue;
        const sorted = names.slice().sort((a, b) => a.localeCompare(b, "es"));
        totalCount += sorted.length;
        groups.push({ pk, label: PARTY_LABELS[pk] || pk, names: sorted });
    }

    if (totalCount === 0) {
        listEl.innerHTML = `<div class="voter-loading">Sin legisladores.</div>`;
        return;
    }

    // Header
    const partyTitle = party === "all" ? "Todos" : (PARTY_LABELS[party] || party);
    let html = `<div class="voter-header ${voteCls}">
        <span class="voter-header-label">${escapeHtml(partyTitle)} — ${escapeHtml(voteLabel)}</span>
        <span class="voter-header-count">${totalCount}</span>
        <button class="voter-close" onclick="this.closest('.law-voter-list').style.display='none'" title="Cerrar">✕</button>
    </div>`;

    // Body
    html += `<div class="voter-body">`;
    for (const g of groups) {
        if (parties.length > 1) {
            html += `<div class="voter-group-header" data-party="${g.pk}">${escapeHtml(g.label)} <span class="voter-group-count">(${g.names.length})</span></div>`;
        }
        for (const name of g.names) {
            html += `<div class="voter-item ${voteCls}">${escapeHtml(name)}</div>`;
        }
    }
    html += `</div>`;

    listEl.innerHTML = html;
}

// Attach bar-click listener via delegation on the law detail body
document.addEventListener("click", function (e) {
    if (e.target.closest(".law-bar-seg")) {
        onBarSegmentClick(e);
    }
});

// ===========================================================================
//  LEGISLATOR DETAIL
// ===========================================================================

async function loadLegislatorDetail(nameKey, urlParams) {
    hideSearchResults();

    // Increment request ID to invalidate any in-flight loads
    const thisRequest = ++loadRequestId;

    // Clean up previous detail state before showing new one
    cleanupLegislatorDetail();

    currentLegKey = nameKey;

    const detailSection = document.getElementById("legislator-detail");
    detailSection.classList.remove("hidden");
    document.querySelector(".search-section").classList.add("hidden");
    document.getElementById("stats-bar").classList.add("hidden");
    document.getElementById("law-search-section").classList.add("hidden");

    // Show loading state
    document.getElementById("leg-name").textContent = "Cargando...";
    document.getElementById("leg-photo").style.display = "none";

    const safeKey = nameKey.replace(/[^A-Z0-9_]/g, "_").substring(0, 80);
    const url = `${DATA_PATH}/legislators/${safeKey}.json`;

    try {
        const resp = await fetch(url);
        // Check if this request is still the latest one
        if (thisRequest !== loadRequestId) return;
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        currentDetail = await resp.json();
        // Check again after parsing
        if (thisRequest !== loadRequestId) return;
        renderLegislatorDetail(currentDetail);

        // Apply URL-provided filters if this was loaded from a shared link
        if (urlParams) {
            if (urlParams.wy) {
                const wyfEl = document.getElementById("waffle-year-filter");
                if (wyfEl) { wyfEl.value = urlParams.wy; }
            }
            if (urlParams.wq) {
                const wlfEl = document.getElementById("waffle-law-filter");
                if (wlfEl) { wlfEl.value = urlParams.wq; }
            }
            if (urlParams.wy || urlParams.wq) {
                currentWafflePage = 1;
                renderWaffle();
            }
        }
    } catch (err) {
        if (thisRequest !== loadRequestId) return;
        console.error("Error loading legislator:", err);
        document.getElementById("leg-name").textContent = "Error al cargar datos";
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
}

/**
 * Thoroughly clean up all legislator detail state to prevent data leaks
 * between different legislator views.
 */
function cleanupLegislatorDetail() {
    // Destroy charts
    if (chartAlignment) { chartAlignment.destroy(); chartAlignment = null; }
    if (chartYearly) { chartYearly.destroy(); chartYearly = null; }

    // Clear global data reference
    currentDetail = null;
    currentLegKey = null;

    // Reset pagination
    currentVotesPage = 1;
    currentWafflePage = 1;

    // Clear DOM elements to prevent stale data from showing
    document.getElementById("leg-name").textContent = "";
    document.getElementById("leg-photo").style.display = "none";
    document.getElementById("leg-chamber").textContent = "";
    document.getElementById("leg-bloc").textContent = "";
    document.getElementById("leg-province").textContent = "";
    document.getElementById("leg-alignment-summary").innerHTML = "";
    document.getElementById("waffle-card-name").innerHTML = "";
    document.getElementById("waffle-card-meta").innerHTML = "";
    document.getElementById("waffle-card-body").innerHTML = "";

    const wafflePag = document.getElementById("waffle-pagination");
    if (wafflePag) wafflePag.innerHTML = "";

    document.getElementById("votes-tbody").innerHTML = "";
    const votesPag = document.getElementById("votes-pagination");
    if (votesPag) votesPag.innerHTML = "";

    // Reset all filters
    const waffleYearFilter = document.getElementById("waffle-year-filter");
    if (waffleYearFilter) waffleYearFilter.innerHTML = '<option value="">Todos</option>';
    const waffleLawFilter = document.getElementById("waffle-law-filter");
    if (waffleLawFilter) waffleLawFilter.value = "";
    const votesYearFilter = document.getElementById("votes-year-filter");
    if (votesYearFilter) votesYearFilter.innerHTML = '<option value="">Todos los años</option>';
    const votesTypeFilter = document.getElementById("votes-type-filter");
    if (votesTypeFilter) votesTypeFilter.value = "";
    const votesLawFilter = document.getElementById("votes-law-filter");
    if (votesLawFilter) votesLawFilter.value = "";
}

function renderLegislatorDetail(data) {
    // Header with photo
    document.getElementById("leg-name").textContent = data.name;

    // Photo
    const photoEl = document.getElementById("leg-photo");
    if (data.photo) {
        photoEl.src = data.photo;
        photoEl.alt = data.name;
        photoEl.style.display = "block";
        photoEl.onerror = () => { photoEl.style.display = "none"; };
    } else {
        photoEl.style.display = "none";
    }

    const chamberBadge = document.getElementById("leg-chamber");
    const chambers = data.chambers || [data.chamber];
    if (chambers.length > 1) {
        chamberBadge.textContent = "Dip. + Sen.";
        chamberBadge.className = "leg-chamber badge badge-both";
    } else {
        chamberBadge.textContent = chambers[0] === "diputados" ? "Diputado/a" : "Senador/a";
        chamberBadge.className = `leg-chamber badge badge-${chambers[0]}`;
    }

    const blocBadge = document.getElementById("leg-bloc");
    blocBadge.textContent = shortPartyName(data.bloc);
    blocBadge.className = `leg-bloc badge badge-${data.coalition.toLowerCase()}`;

    document.getElementById("leg-province").textContent = data.province;

    // Alignment summary cards
    const alignSummary = document.getElementById("leg-alignment-summary");
    alignSummary.innerHTML = "";

    const coalitions = [
        { key: "PJ", label: "PJ / UxP / FdT", cls: "alignment-pj" },
        { key: "UCR", label: "UCR / ARI", cls: "alignment-ucr" },
        { key: "PRO", label: "JxC / PRO / UCR", cls: "alignment-pro" },
        { key: "LLA", label: "LLA / PRO", cls: "alignment-lla" },
    ];

    for (const c of coalitions) {
        const val = data.alignment[c.key];
        const card = document.createElement("div");
        card.className = `alignment-card ${c.cls}`;
        card.innerHTML = `
            <div class="alignment-label">${c.label}</div>
            <div class="alignment-value">${val !== null ? val + "%" : "N/A"}</div>
        `;
        alignSummary.appendChild(card);
    }

    // Waffle card header — include small portrait next to the politician name
    const waffleNameEl = document.getElementById("waffle-card-name");
    const smallPhoto = data.photo
        ? `<img class="waffle-header-photo" src="${escapeAttr(data.photo)}" alt="">`
        : `<span class="waffle-header-photo no-photo">👤</span>`;
    waffleNameEl.innerHTML = `
        <div class="waffle-header-left">
            ${smallPhoto}
            <div class="waffle-card-name-text">${escapeHtml(data.name)}</div>
        </div>`;

    const chamberLabel = chambers.length > 1 ? "HCD + HCS" : (chambers[0] === "diputados" ? "HCD" : "HCS");
    document.getElementById("waffle-card-meta").innerHTML = `
        <span class="badge badge-${chambers[0]}">${chamberLabel}</span>
        <span class="badge badge-${data.coalition.toLowerCase()}">${shortPartyName(data.bloc)}</span>
    `;

    // Populate waffle year filter (only years that have notable laws)
    const waffleYearFilter = document.getElementById("waffle-year-filter");
    waffleYearFilter.innerHTML = '<option value="">Todos</option>';
    const notableLawYears = [...new Set(
        (data.laws || []).filter((l) => l.notable).map((l) => String(l.year))
    )].sort();
    for (const y of notableLawYears) {
        waffleYearFilter.innerHTML += `<option value="${y}">${y}</option>`;
    }

    // Reset waffle law filter
    document.getElementById("waffle-law-filter").value = "";

    // Reset waffle page
    currentWafflePage = 1;

    // Render waffle
    renderWaffle();

    // Charts
    const years = Object.keys(data.yearly_stats).sort();
    renderAlignmentChart(data);
    renderYearlyChart(data);

    // Populate votes year filter
    const yearFilter = document.getElementById("votes-year-filter");
    yearFilter.innerHTML = '<option value="">Todos los años</option>';
    for (const y of years) {
        yearFilter.innerHTML += `<option value="${y}">${y}</option>`;
    }
    document.getElementById("votes-type-filter").value = "";
    document.getElementById("votes-law-filter").value = "";

    currentVotesPage = 1;
    renderVotesTable();
}

function showSearchView() {
    document.getElementById("legislator-detail").classList.add("hidden");
    document.querySelector(".search-section").classList.remove("hidden");
    document.getElementById("stats-bar").classList.remove("hidden");
    document.getElementById("law-search-section").classList.remove("hidden");

    // Clear deep-link params from URL without reload
    if (window.location.search) {
        history.replaceState(null, "", window.location.pathname);
    }

    // Invalidate any in-flight loads
    loadRequestId++;

    // Clean up all detail state
    cleanupLegislatorDetail();
}

// ===========================================================================
//  WAFFLE VISUALIZATION
// ===========================================================================

function renderWaffle() {
    if (!currentDetail) return;

    const yearFilter = document.getElementById("waffle-year-filter").value;
    const lawFilter = document.getElementById("waffle-law-filter").value.trim().toLowerCase();

    let laws = currentDetail.laws || [];

    // Always filter to notable laws first
    laws = laws.filter((l) => l.notable === true);

    // Apply text filter
    if (lawFilter) {
        laws = laws.filter((l) => l.name.toLowerCase().includes(lawFilter));
    }

    // Apply year filter
    if (yearFilter) {
        laws = laws.filter((l) => String(l.year) === yearFilter);
    }

    const body = document.getElementById("waffle-card-body");
    const paginationContainer = document.getElementById("waffle-pagination");

    if (laws.length === 0) {
        body.innerHTML = '<div class="waffle-empty">No hay leyes destacadas para los filtros seleccionados</div>';
        if (paginationContainer) paginationContainer.innerHTML = "";
        return;
    }

    // Pagination
    const totalPages = Math.max(1, Math.ceil(laws.length / LAWS_PER_PAGE));
    if (currentWafflePage > totalPages) currentWafflePage = totalPages;
    const start = (currentWafflePage - 1) * LAWS_PER_PAGE;
    const pageLaws = laws.slice(start, start + LAWS_PER_PAGE);

    // Render law rows
    let html = "";
    for (let lawIdx = 0; lawIdx < pageLaws.length; lawIdx++) {
        const law = pageLaws[lawIdx];
        const tiles = law.votes.map((vote, voteIdx) => {
            const isGeneral = vote.g === true;
            const cls = `waffle-tile tile-${vote.v}${isGeneral ? " tile-general" : ""} tile-clickable`;
            const icon = voteIcon(vote.v);
            const label = vote.al || (isGeneral ? "En General" : "");
            const tooltip = label ? `${label}: ${formatVoteShort(vote.v)}` : formatVoteShort(vote.v);
            return `<div class="${cls}" title="${escapeAttr(tooltip)}" data-law-idx="${lawIdx}" data-vote-idx="${voteIdx}">${icon}</div>`;
        }).join("");

        const displayName = escapeHtml(truncate(law.name, 60));
        const yearLabel = law.year ? `<span class="waffle-law-year">${law.year}</span>` : "";

        html += `
        <div class="waffle-law-row">
            <div class="waffle-law-label">
                <span class="waffle-law-name">${displayName}</span>
                ${yearLabel}
            </div>
            <div class="waffle-tiles">${tiles}</div>
        </div>`;
    }

    body.innerHTML = html;

    // Attach click handlers to waffle tiles for popup
    body.querySelectorAll(".tile-clickable").forEach((tile) => {
        tile.addEventListener("click", () => {
            const lIdx = parseInt(tile.dataset.lawIdx);
            const vIdx = parseInt(tile.dataset.voteIdx);
            const law = pageLaws[lIdx];
            if (law && law.votes[vIdx]) {
                showVotePopup(law.name, law.votes[vIdx], law.year);
            }
        });
    });

    // Render waffle pagination
    if (paginationContainer) {
            if (totalPages <= 1) {
            paginationContainer.innerHTML = `<span style="font-size:0.8rem;color:var(--color-text-secondary)">${laws.length} leyes</span>`;
        } else {
            let pHtml = "";
            if (currentWafflePage > 1) {
                pHtml += `<button data-page="${currentWafflePage - 1}">← Ant.</button>`;
            }
            for (let p = 1; p <= totalPages; p++) {
                if (p === 1 || p === totalPages || Math.abs(p - currentWafflePage) <= 2) {
                    pHtml += `<button data-page="${p}" class="${p === currentWafflePage ? "active" : ""}">${p}</button>`;
                } else if (Math.abs(p - currentWafflePage) === 3) {
                    pHtml += `<span style="padding:0.4rem;color:var(--color-text-secondary)">…</span>`;
                }
            }
            if (currentWafflePage < totalPages) {
                pHtml += `<button data-page="${currentWafflePage + 1}">Sig. →</button>`;
            }
            pHtml += `<span style="font-size:0.75rem;color:var(--color-text-secondary);margin-left:0.5rem">${laws.length} leyes</span>`;
            paginationContainer.innerHTML = pHtml;

            paginationContainer.querySelectorAll("button[data-page]").forEach((btn) => {
                btn.addEventListener("click", () => {
                    currentWafflePage = parseInt(btn.dataset.page);
                    renderWaffle();
                    document.getElementById("waffle-section").scrollIntoView({ behavior: "smooth" });
                });
            });
        }
    }
}

function voteIcon(vote) {
    switch (vote) {
        case "AFIRMATIVO": return "✓";
        case "NEGATIVO": return "✗";
        case "ABSTENCION": return "○";
        case "AUSENTE": return "—";
        case "PRESIDENTE": return "⚑";
        default: return "?";
    }
}

// ===========================================================================
//  VOTE INFO POPUP
// ===========================================================================

function showVotePopup(lawName, vote, lawYear) {
    const overlay = document.getElementById("vote-popup-overlay");
    document.getElementById("vote-popup-title").textContent = lawName || "Votación";
    document.getElementById("vote-popup-fullname").textContent = vote.t || vote.al || "—";

    // Try to find the date from the top-level votes if not in law-level vote
    let dateStr = vote.d || "";
    if (!dateStr && vote.vid && vote.ch) {
        const detailData = currentDetail;
        if (detailData) {
            const match = (detailData.votes || []).find(
                (v) => String(v.vid) === String(vote.vid) && v.ch === vote.ch
            );
            if (match) dateStr = match.d || "";
        }
    }
    if (!dateStr && lawYear) dateStr = String(lawYear);
    document.getElementById("vote-popup-date").textContent = dateStr || "—";

    document.getElementById("vote-popup-article").textContent = vote.al || "—";

    const voteEl = document.getElementById("vote-popup-vote");
    voteEl.innerHTML = `<span class="vote-chip vote-${vote.v}">${formatVote(vote.v)}</span>`;

    const linkRow = document.getElementById("vote-popup-link-row");
    const linkEl = document.getElementById("vote-popup-link");
    let href = vote.url || "";
    if (!href && vote.ch === "diputados" && vote.vid) {
        href = `https://votaciones.hcdn.gob.ar/votacion/${vote.vid}`;
    } else if (!href && vote.ch === "senadores" && vote.vid) {
        href = `https://www.senado.gob.ar/votaciones/detalleActa/${vote.vid}`;
    }
    if (href) {
        linkEl.href = href;
        linkRow.style.display = "";
    } else {
        linkRow.style.display = "none";
    }

    overlay.classList.remove("hidden");
}

function hideVotePopup() {
    document.getElementById("vote-popup-overlay").classList.add("hidden");
}

// ===========================================================================
//  SHARE / EXPORT
// ===========================================================================

async function copyCardImage(cardId, btnId) {
    const card = document.getElementById(cardId);
    const btn = document.getElementById(btnId);
    const originalText = btn.innerHTML;

    // Clamp the card to 480 CSS-px (→ 960px at 2× scale) so the exported
    // image is roughly square/4:3 regardless of the desktop viewport width.
    const EXPORT_MAX_W = 480;
    const prevWidth    = card.style.width;
    const prevMaxWidth = card.style.maxWidth;
    card.style.width    = EXPORT_MAX_W + "px";
    card.style.maxWidth = EXPORT_MAX_W + "px";
    card.classList.add("exporting");
    void card.offsetHeight; // force reflow before capture

    try {
        btn.innerHTML = "⏳ Generando...";
        btn.disabled = true;
        // Try html2canvas with CORS first (best fidelity). If it fails (tainted images
        // or CORS errors), fall back to a less strict render (allowTaint) and then
        // finally to a download fallback.
        try {
            const canvas = await html2canvas(card, {
                backgroundColor: "#ffffff",
                scale: 2,
                useCORS: true,
                logging: false,
            });

            const blob = await new Promise((resolve, reject) => {
                canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob failed"))), "image/png");
            });

            try {
                await navigator.clipboard.write([
                    new ClipboardItem({ "image/png": blob }),
                ]);
                btn.innerHTML = "✓ Copiado!";
                setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 2000);
            } catch (e) {
                console.warn("Clipboard write failed, falling back to download:", e);
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `como_voto_${cardId}.png`;
                a.click();
                URL.revokeObjectURL(url);
                btn.innerHTML = "✓ Descargado!";
                setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 2000);
            }
        } catch (err) {
            console.warn("html2canvas with CORS failed, retrying with allowTaint:", err);
            // Retry with allowTaint so html2canvas renders even with cross-origin images.
            try {
                const canvas2 = await html2canvas(card, {
                    backgroundColor: "#ffffff",
                    scale: 2,
                    useCORS: false,
                    allowTaint: true,
                    logging: false,
                });

                const blob2 = await new Promise((resolve, reject) => {
                    canvas2.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob failed"))), "image/png");
                });

                // When using allowTaint the clipboard may still fail due to tainted canvas,
                // so we go directly to download fallback.
                const url = URL.createObjectURL(blob2);
                const a = document.createElement("a");
                a.href = url;
                a.download = `como_voto_${cardId}.png`;
                a.click();
                URL.revokeObjectURL(url);
                btn.innerHTML = "✓ Descargado!";
                setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 2000);
            } catch (err2) {
                console.error("All attempts to generate/export image failed:", err2);
                btn.innerHTML = "Error :(";
                setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 2000);
            }
        }
    } catch (err) {
        console.error("Unexpected error in copyCardImage:", err);
        btn.innerHTML = "Error :(";
        setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 2000);
    } finally {
        // Always restore the card's original dimensions after export.
        card.style.width    = prevWidth;
        card.style.maxWidth = prevMaxWidth;
        card.classList.remove("exporting");
    }
}

async function copyWaffleImage() {
    await copyCardImage("waffle-card", "btn-copy-image");
}

/**
 * Build a shareable URL pointing to the current legislator view,
 * optionally including the active waffle year / text filters.
 */
function buildShareUrl() {
    const base = window.location.origin + window.location.pathname;
    const params = new URLSearchParams();
    if (currentLegKey) params.set("leg", currentLegKey);
    const wy = document.getElementById("waffle-year-filter");
    if (wy && wy.value) params.set("wy", wy.value);
    const wq = document.getElementById("waffle-law-filter");
    if (wq && wq.value.trim()) params.set("wq", wq.value.trim());
    const qs = params.toString();
    return qs ? `${base}?${qs}` : base;
}

function shareTwitter() {
    if (!currentDetail) return;
    const name = currentDetail.name;
    const text = `Mirá cómo votó ${name} en el Congreso Argentino 🗳️`;
    const url = encodeURIComponent(buildShareUrl());
    const tweetUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${url}`;
    window.open(tweetUrl, "_blank", "width=600,height=400");
}

// ===========================================================================
//  CHARTS
// ===========================================================================

function renderAlignmentChart(data) {
    if (chartAlignment) chartAlignment.destroy();

    const ctx = document.getElementById("chart-alignment").getContext("2d");
    const years = Object.keys(data.yearly_alignment).sort();

    if (years.length === 0) {
        ctx.font = "14px Inter";
        ctx.fillStyle = "#6b7280";
        ctx.textAlign = "center";
        ctx.fillText("Sin datos de alineamiento", ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }

    const pjData = years.map((y) => data.yearly_alignment[y]?.PJ ?? null);
    const ucrData = years.map((y) => data.yearly_alignment[y]?.UCR ?? null);
    const proData = years.map((y) => data.yearly_alignment[y]?.PRO ?? null);
    const llaData = years.map((y) => data.yearly_alignment[y]?.LLA ?? null);

    // Centralized point sizing so legend markers match plotted points
    const POINT_RADIUS = 4;
    const POINT_HOVER_RADIUS = 6;
    const DATASET_BORDER_WIDTH = 2.5;
    // Legend box should roughly match the visual point size; keep it small.
    const legendBox = Math.max(6, Math.round(POINT_RADIUS * 1.6));

    chartAlignment = new Chart(ctx, {
        type: "line",
        data: {
            labels: years,
            datasets: [
                {
                    label: "PJ / UxP / FdT",
                    data: pjData,
                    borderColor: "#1e88e5",
                    backgroundColor: "rgba(30, 136, 229, 0.08)",
                    borderWidth: 2.5,
                    pointStyle: 'circle',
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.3,
                    fill: false,
                    spanGaps: true,
                    clip: false,
                },
                    {
                        label: "UCR / ARI",
                        data: ucrData,
                        borderColor: "#ef4444",
                        backgroundColor: "rgba(239,68,68,0.06)",
                        borderWidth: 2.5,
                        pointStyle: 'circle',
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        tension: 0.3,
                        fill: false,
                        spanGaps: true,
                        clip: false,
                    },
                {
                    label: "JxC / PRO / UCR",
                    data: proData,
                    borderColor: "#f9a825",
                    backgroundColor: "rgba(249, 168, 37, 0.08)",
                    borderWidth: 2.5,
                    pointStyle: 'circle',
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.3,
                    fill: false,
                    spanGaps: true,
                    clip: false,
                },
                {
                    label: "LLA / PRO",
                    data: llaData,
                    borderColor: "#7b1fa2",
                    backgroundColor: "rgba(123, 31, 162, 0.08)",
                    borderWidth: 2.5,
                    pointStyle: 'circle',
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.3,
                    fill: false,
                    spanGaps: true,
                    clip: false,
                },
            ],
        },
            options: {
                layout: { padding: { top: 14 } },
            responsive: true,
            maintainAspectRatio: false,
                plugins: {
                legend: {
                    position: "bottom",
                    labels: { usePointStyle: true, padding: 15, boxWidth: 6, boxHeight: 6, font: { size: 12 } },
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y !== null ? ctx.parsed.y + "%" : "N/A"}`,
                    },
                },
            },
                scales: {
                y: {
                    min: 0,
                    max: 100,
                    ticks: {
                        stepSize: 10,
                        callback: (v) => (typeof v === "number" && v % 10 === 0 ? v + "%" : ""),
                        font: { size: 11 },
                    },
                    grid: { color: "rgba(0,0,0,0.05)" },
                },
                x: {
                    ticks: { font: { size: 11 } },
                    grid: { display: false },
                },
            },
            interaction: { mode: "index", intersect: false },
        },
    });
}

function renderYearlyChart(data) {
    if (chartYearly) chartYearly.destroy();

    const ctx = document.getElementById("chart-yearly").getContext("2d");
    const years = Object.keys(data.yearly_stats).sort();

    if (years.length === 0) {
        ctx.font = "14px Inter";
        ctx.fillStyle = "#6b7280";
        ctx.textAlign = "center";
        ctx.fillText("Sin datos", ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }

    chartYearly = new Chart(ctx, {
        type: "bar",
        data: {
            labels: years,
            datasets: [
                {
                    label: "Afirmativo",
                    data: years.map((y) => data.yearly_stats[y]?.AFIRMATIVO || 0),
                    backgroundColor: "#22c55e",
                },
                {
                    label: "Negativo",
                    data: years.map((y) => data.yearly_stats[y]?.NEGATIVO || 0),
                    backgroundColor: "#ef4444",
                },
                {
                    label: "Abstención",
                    data: years.map((y) => data.yearly_stats[y]?.ABSTENCION || 0),
                    backgroundColor: "#f59e0b",
                },
                {
                    label: "Ausente",
                    data: years.map((y) => data.yearly_stats[y]?.AUSENTE || 0),
                    backgroundColor: "#94a3b8",
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "bottom",
                    labels: { usePointStyle: true, padding: 15, font: { size: 12 } },
                },
            },
            scales: {
                x: {
                    stacked: true,
                    grid: { display: false },
                    ticks: { font: { size: 11 } },
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    ticks: { font: { size: 11 } },
                    grid: { color: "rgba(0,0,0,0.05)" },
                },
            },
        },
    });
}

// ===========================================================================
//  VOTES TABLE
// ===========================================================================

function renderVotesTable() {
    if (!currentDetail) return;

    const yearFilter = document.getElementById("votes-year-filter").value;
    const typeFilter = document.getElementById("votes-type-filter").value;
    const lawFilter = document.getElementById("votes-law-filter").value.trim().toLowerCase();

    let votes = currentDetail.votes || [];

    if (yearFilter) {
        votes = votes.filter((v) => String(v.yr) === yearFilter);
    }
    if (typeFilter) {
        votes = votes.filter((v) => v.v === typeFilter);
    }
    if (lawFilter) {
        votes = votes.filter((v) => {
            const searchable = `${v.ln || ""} ${v.t || ""}`.toLowerCase();
            return searchable.includes(lawFilter);
        });
    }

    // Sort by date descending
    votes.sort((a, b) => {
        const da = parseArgDate(a.d);
        const db = parseArgDate(b.d);
        return db - da;
    });

    // Pagination
    const totalPages = Math.max(1, Math.ceil(votes.length / VOTES_PER_PAGE));
    if (currentVotesPage > totalPages) currentVotesPage = totalPages;
    const start = (currentVotesPage - 1) * VOTES_PER_PAGE;
    const pageVotes = votes.slice(start, start + VOTES_PER_PAGE);

    const tbody = document.getElementById("votes-tbody");
    tbody.innerHTML = pageVotes
        .map(
            (v) => {
                // compute source link if available
                let linkHtml = "";
                const href = v.url || (v.ch === "diputados" && v.vid ? `https://votaciones.hcdn.gob.ar/votacion/${v.vid}` : null);
                if (href) {
                    linkHtml = `<a class="vote-link" href="${escapeAttr(href)}" target="_blank" title="Ver votación original">🔗</a>`;
                }
                // determine which opposition coalition applies for this vote's year
                const yr = v.yr || null;
                const oppKey = yr === null ? null : (yr <= 2014 ? 'UCR' : (yr <= 2023 ? 'JxC' : 'LLA'));

                const pjCell = `<span class="vote-chip vote-${v.pj}">${formatVote(v.pj)}</span>`;
                const ucrCell = (oppKey === 'UCR' && v.ucr) ? `<span class="vote-chip vote-${v.ucr}">${formatVote(v.ucr)}</span>` : `<span class="vote-chip vote-na">-</span>`;
                const jxcCell = (oppKey === 'JxC' && v.pro) ? `<span class="vote-chip vote-${v.pro}">${formatVote(v.pro)}</span>` : `<span class="vote-chip vote-na">-</span>`;
                const llaCell = (oppKey === 'LLA' && v.lla) ? `<span class="vote-chip vote-${v.lla}">${formatVote(v.lla)}</span>` : `<span class="vote-chip vote-na">-</span>`;

                return `
        <tr>
            <td style="white-space:nowrap">${escapeHtml(v.d || "")}</td>
            <td>
                <div class="vote-title">${escapeHtml(v.ln || v.t || "")}</div>
                ${v.al ? `<div class="vote-article">${escapeHtml(v.al)}</div>` : ""}
            </td>
            <td class="vote-source-cell">${linkHtml}</td>
            <td><span class="vote-chip vote-${v.v}">${formatVote(v.v)}</span></td>
            <td>${pjCell}</td>
            <td>${ucrCell}</td>
            <td>${jxcCell}</td>
            <td>${llaCell}</td>
        </tr>`;
            }
        )
        .join("");

    renderPagination(totalPages, votes.length);
}

function renderPagination(totalPages, totalItems) {
    const container = document.getElementById("votes-pagination");
    if (totalPages <= 1) {
        container.innerHTML = `<span style="font-size:0.8rem;color:var(--color-text-secondary)">${totalItems} votaciones</span>`;
        return;
    }

    let html = "";

    if (currentVotesPage > 1) {
        html += `<button data-page="${currentVotesPage - 1}">← Ant.</button>`;
    }

    for (let p = 1; p <= totalPages; p++) {
        if (p === 1 || p === totalPages || Math.abs(p - currentVotesPage) <= 2) {
            html += `<button data-page="${p}" class="${p === currentVotesPage ? "active" : ""}">${p}</button>`;
        } else if (Math.abs(p - currentVotesPage) === 3) {
            html += `<span style="padding:0.4rem;color:var(--color-text-secondary)">…</span>`;
        }
    }

    if (currentVotesPage < totalPages) {
        html += `<button data-page="${currentVotesPage + 1}">Sig. →</button>`;
    }

    html += `<span style="font-size:0.75rem;color:var(--color-text-secondary);margin-left:0.5rem">${totalItems} votaciones</span>`;

    container.innerHTML = html;

    container.querySelectorAll("button[data-page]").forEach((btn) => {
        btn.addEventListener("click", () => {
            currentVotesPage = parseInt(btn.dataset.page);
            renderVotesTable();
            document.querySelector(".votes-section").scrollIntoView({ behavior: "smooth" });
        });
    });
}

// ===========================================================================
//  UTILITIES
// ===========================================================================

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/"/g, "&quot;").replace(/'/g, "&#39;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function truncate(str, maxLen) {
    if (!str) return "";
    return str.length > maxLen ? str.substring(0, maxLen - 1) + "…" : str;
}

// Shorten long party/bloc names for display (e.g. "Frente de Izquierda..." -> "FIT-U")
function shortPartyName(name) {
    if (!name) return "";
    const n = name.trim();

    const aliases = [
        { re: /frente\s+de\s+izquierda.*unidad/i, short: "FIT-U" },
        { re: /frente\s+de\s+izquierda/i, short: "FIT" },
        { re: /frente\s+de\s+todos/i, short: "FdT" },
    ];

    for (const a of aliases) {
        if (a.re.test(n)) return a.short;
    }

    // If the name is short already, return as-is
    if (n.length <= 18) return n;

    // Build an acronym from significant words
    const stopwords = new Set(["y", "de", "la", "los", "del", "el", "para", "por", "en", "con"]);
    const parts = n.split(/\s+/).filter(Boolean);
    const significant = parts.filter((w) => !stopwords.has(w.toLowerCase()));
    let acronym = significant.slice(0, 3).map((w) => w[0].toUpperCase()).join("");

    // If last word contains 'unidad', append -U (common in FIT-U)
    const last = parts[parts.length - 1].toLowerCase();
    if (last.includes("unidad") && !acronym.endsWith("U")) acronym = acronym + "-U";

    return acronym || n.substring(0, 12).toUpperCase();
}

function debounce(fn, ms) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn.apply(this, args), ms);
    };
}

function formatVote(v) {
    const map = {
        AFIRMATIVO: "✓ Afirm.",
        NEGATIVO: "✗ Neg.",
        ABSTENCION: "○ Abst.",
        AUSENTE: "— Aus.",
        PRESIDENTE: "⚑ Pres.",
        "N/A": "—",
    };
    return map[v] || v || "—";
}

function formatVoteShort(v) {
    const map = {
        AFIRMATIVO: "Afirmativo",
        NEGATIVO: "Negativo",
        ABSTENCION: "Abstención",
        AUSENTE: "Ausente",
        PRESIDENTE: "Presidente",
    };
    return map[v] || v || "";
}

function parseArgDate(dateStr) {
    if (!dateStr) return 0;
    const match = dateStr.match(/(\d{2})\/(\d{2})\/(\d{4})/);
    if (match) {
        return new Date(
            parseInt(match[3]),
            parseInt(match[2]) - 1,
            parseInt(match[1])
        ).getTime();
    }
    return new Date(dateStr).getTime() || 0;
}


// -------------------------------------------------------------------------
// Initialization: load stats and legislators index, wire basic UI events
// -------------------------------------------------------------------------
(async function initApp() {
    try {
        const sresp = await fetch(`${DATA_PATH}/stats.json`);
        if (sresp.ok) {
            const stats = await sresp.json();
            const legsEl = document.getElementById("stat-legislators");
            const votEl = document.getElementById("stat-votaciones");
            const yrsEl = document.getElementById("stat-years");
            const updEl = document.getElementById("stat-updated");

            if (legsEl) legsEl.textContent = stats.total_legislators ?? "-";
            const totalVot = (stats.total_votaciones_diputados || 0) + (stats.total_votaciones_senadores || 0);
            if (votEl) votEl.textContent = totalVot || "-";
            const years = stats.years_covered || [];
            if (yrsEl) yrsEl.textContent = years.length ? `${years[0]}–${years[years.length - 1]}` : "-";
            if (updEl) updEl.textContent = stats.last_updated ? new Date(stats.last_updated).toLocaleString() : "-";
        } else {
            console.warn("Could not load stats.json", sresp.status);
        }
    } catch (err) {
        console.error("Error loading stats.json:", err);
    }

    try {
        const lresp = await fetch(`${DATA_PATH}/legislators.json`);
        if (lresp.ok) {
            legislatorsData = await lresp.json();
        } else {
            console.warn("Could not load legislators.json", lresp.status);
        }
    } catch (err) {
        console.error("Error loading legislators.json:", err);
    }

    // Load laws detail data for the law search section
    try {
        const lawResp = await fetch(`${DATA_PATH}/laws_detail.json`);
        if (lawResp.ok) {
            lawsData = await lawResp.json();
            // Populate year filter
            const years = [...new Set(lawsData.map((l) => l.y).filter(Boolean))].sort();
            const lawYearFilter = document.getElementById("law-year-filter");
            if (lawYearFilter) {
                for (const y of years) {
                    lawYearFilter.innerHTML += `<option value="${y}">${y}</option>`;
                }
            }
        } else {
            console.warn("Could not load laws_detail.json", lawResp.status);
        }
    } catch (err) {
        console.error("Error loading laws_detail.json:", err);
    }

    // Wire search and basic controls
    const sin = document.getElementById("search-input");
    if (sin) sin.addEventListener("input", debounce(onSearchInput, 250));
    if (sin) sin.addEventListener("focus", () => onSearchInput({ requireQuery: false }));

    // Hide results on Escape or when focus leaves the search box.
    // Use a mousedown guard so clicking a result item isn't swallowed by blur.
    const searchResults = document.getElementById("search-results");
    let searchResultsMousedown = false;
    if (searchResults) {
        searchResults.addEventListener("mousedown", () => { searchResultsMousedown = true; });
        searchResults.addEventListener("mouseup",   () => { searchResultsMousedown = false; });
    }
    if (sin) {
        sin.addEventListener("blur", () => {
            if (!searchResultsMousedown) hideSearchResults();
        });
        sin.addEventListener("keydown", (e) => {
            if (e.key === "Escape") { hideSearchResults(); sin.blur(); }
        });
    }
    const clearBtn = document.getElementById("clear-search");
    if (clearBtn) clearBtn.addEventListener("click", () => { document.getElementById("search-input").value = ""; hideSearchResults(); });
    const chamberSel = document.getElementById("filter-chamber");
    if (chamberSel) chamberSel.addEventListener("change", onSearchInput);
    const coalitionSel = document.getElementById("filter-coalition");
    if (coalitionSel) coalitionSel.addEventListener("change", onSearchInput);

    const backBtn = document.getElementById("back-btn");
    if (backBtn) backBtn.addEventListener("click", showSearchView);

    // Wire law search controls
    const lawSearchInput = document.getElementById("law-search");
    if (lawSearchInput) lawSearchInput.addEventListener("input", debounce(onLawSearchInput, 200));
    if (lawSearchInput) lawSearchInput.addEventListener("focus", () => {
        // On focus, show filtered results (even without text, if filters are set)
        onLawSearchInput();
    });

    // Dismiss law dropdown on Escape / click-outside
    const lawDropdown = document.getElementById("law-search-results");
    let lawDropdownMousedown = false;
    if (lawDropdown) {
        lawDropdown.addEventListener("mousedown", () => { lawDropdownMousedown = true; });
        lawDropdown.addEventListener("mouseup",   () => { lawDropdownMousedown = false; });
    }
    if (lawSearchInput) {
        lawSearchInput.addEventListener("blur", () => {
            if (!lawDropdownMousedown && lawDropdown) lawDropdown.classList.add("hidden");
        });
        lawSearchInput.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && lawDropdown) { lawDropdown.classList.add("hidden"); lawSearchInput.blur(); }
        });
    }

    const lawYearFilterEl = document.getElementById("law-year-filter");
    if (lawYearFilterEl) lawYearFilterEl.addEventListener("change", onLawSearchInput);
    const lawChamberFilterEl = document.getElementById("law-chamber-filter");
    if (lawChamberFilterEl) lawChamberFilterEl.addEventListener("change", onLawSearchInput);

    // Wire law card share / copy buttons
    const btnCopyLaw = document.getElementById("btn-copy-law");
    if (btnCopyLaw) btnCopyLaw.addEventListener("click", () => copyCardImage("law-detail-card", "btn-copy-law"));
    const btnShareLaw = document.getElementById("btn-share-law-tw");
    if (btnShareLaw) btnShareLaw.addEventListener("click", shareTwitterLaw);

    // Wire waffle filters
    const waffleLawFilter = document.getElementById("waffle-law-filter");
    if (waffleLawFilter) waffleLawFilter.addEventListener("input", debounce(() => { currentWafflePage = 1; renderWaffle(); }, 200));
    const waffleYearFilter = document.getElementById("waffle-year-filter");
    if (waffleYearFilter) waffleYearFilter.addEventListener("change", () => { currentWafflePage = 1; renderWaffle(); });

    // Wire province filter (was missing)
    const provinceSel = document.getElementById("filter-province");
    if (provinceSel) provinceSel.addEventListener("change", onSearchInput);

    // Wire votes table filters (were missing)
    const votesYearFilter = document.getElementById("votes-year-filter");
    if (votesYearFilter) votesYearFilter.addEventListener("change", () => { currentVotesPage = 1; renderVotesTable(); });
    const votesTypeFilter = document.getElementById("votes-type-filter");
    if (votesTypeFilter) votesTypeFilter.addEventListener("change", () => { currentVotesPage = 1; renderVotesTable(); });
    const votesLawFilter = document.getElementById("votes-law-filter");
    if (votesLawFilter) votesLawFilter.addEventListener("input", debounce(() => { currentVotesPage = 1; renderVotesTable(); }, 250));

    // Populate initial small search result if desired (empty/hidden)
    hideSearchResults();

    // Deep-link: if URL contains ?leg=KEY, auto-load that legislator
    const urlParams = new URLSearchParams(window.location.search);
    const legParam = urlParams.get("leg");
    if (legParam) {
        loadLegislatorDetail(legParam, {
            wy: urlParams.get("wy") || "",
            wq: urlParams.get("wq") || "",
        });
    }
    // Wire waffle/legislator detail share + copy buttons
    const btnCopyWaffle = document.getElementById("btn-copy-image");
    if (btnCopyWaffle) btnCopyWaffle.addEventListener("click", copyWaffleImage);
    const btnShareWaffle = document.getElementById("btn-share-tw");
    if (btnShareWaffle) btnShareWaffle.addEventListener("click", shareTwitter);

    // Wire vote popup close handlers
    const popupOverlay = document.getElementById("vote-popup-overlay");
    const popupClose = document.getElementById("vote-popup-close");
    if (popupClose) popupClose.addEventListener("click", hideVotePopup);
    if (popupOverlay) popupOverlay.addEventListener("click", (e) => {
        if (e.target === popupOverlay) hideVotePopup();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") hideVotePopup();
    });
})();
