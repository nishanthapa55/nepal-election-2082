/* ═══════════════════════ Nepal Election Live — Main JS ═══════════════════════ */

const REFRESH_INTERVAL = 10000;
const TOTAL_SEATS = 165;
const MAJORITY = 83;

// ─────────────── State ───────────────
let allConstituencies = [];
let allParties = [];
let provinces = [];
let currentProvince = "";
let currentDistrict = "";
let currentStatus = "";
let searchQuery = "";
let leadingData = [];
let summaryData = null;

// ─────────────── Party Colors ───────────────
const PARTY_COLORS = {
    "NC": "#0066CC", "UML": "#FF0000", "MC": "#CC0000",
    "RSP": "#FF6600", "RPP": "#FFD700", "JSP": "#008000",
    "US": "#990000", "LSP": "#336699", "JP": "#9933FF",
    "NUP": "#00CC99", "NWPP": "#663300", "IND": "#999999",
};

// ─────────────── Nepali Numerals ───────────────
function toNepali(n) {
    const digits = ['०', '१', '२', '३', '४', '५', '६', '७', '८', '९'];
    return String(n).replace(/\d/g, d => digits[d]);
}

// ─────────────── Hemicycle Configuration ───────────────
const HEMI_ROWS = [11, 15, 19, 24, 28, 32, 36]; // 165 total
const HEMI_RADII = [55, 73, 91, 109, 127, 145, 163];
const HEMI_CX = 180, HEMI_CY = 195;
const HEMI_DOT_R = 3.8;

// ═══════════════════════ INIT ═══════════════════════
document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initModal();
    initStatusPills();
    initSearch();
    loadInitialData();

    // Auto-refresh
    setInterval(() => {
        loadSummary();
        loadLeading();
        if (document.getElementById("tab-constituency").style.display !== "none") {
            loadConstituenciesData();
        }
    }, REFRESH_INTERVAL);
});

// ═══════════════════════ TAB NAVIGATION ═══════════════════════
function initTabs() {
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            const tab = btn.dataset.tab;
            ["party", "constituency", "candidates", "hot-seat"].forEach(t => {
                const el = document.getElementById(`tab-${t}`);
                if (el) el.style.display = t === tab ? "block" : "none";
            });

            if (tab === "constituency" && allConstituencies.length === 0) {
                loadConstituenciesData();
            }
        });
    });
}

// ═══════════════════════ LOAD INITIAL DATA ═══════════════════════
async function loadInitialData() {
    await Promise.all([
        loadAllParties(),
        loadSummary(),
        loadLeading(),
        loadProvinces(),
    ]);
    renderHemicycle();
}

// ═══════════════════════ SUMMARY ═══════════════════════
async function loadSummary() {
    try {
        const res = await fetch("/api/summary");
        summaryData = await res.json();

        document.getElementById("statTotal").textContent = summaryData.total_constituencies;
        document.getElementById("statDeclared").textContent = summaryData.declared;
        document.getElementById("statCounting").textContent = summaryData.counting;
        document.getElementById("statPending").textContent = summaryData.pending;
        document.getElementById("statVotes").textContent = formatNumber(summaryData.total_votes_cast);
        document.getElementById("lastUpdated").textContent = `Updated: ${new Date().toLocaleTimeString()}`;

        renderPartyTable();
        renderSidebarBars();
        renderHemicycle();
    } catch (err) {
        console.error("Failed to load summary:", err);
    }
}

// ═══════════════════════ LEADING DATA ═══════════════════════
async function loadLeading() {
    try {
        const res = await fetch("/api/leading");
        leadingData = await res.json();
    } catch (err) {
        console.error("Failed to load leading data:", err);
    }
}

// ═══════════════════════ ALL PARTIES ═══════════════════════
async function loadAllParties() {
    try {
        const res = await fetch("/api/parties");
        allParties = await res.json();
    } catch (err) {
        console.error("Failed to load parties:", err);
    }
}

// ═══════════════════════ COMPUTE PARTY STATS ═══════════════════════
function getPartyStats() {
    // Compute leading & won per party from leadingData
    const leadStats = {};
    leadingData.forEach(l => {
        const party = l.leading_party || "IND";
        if (!leadStats[party]) leadStats[party] = { leading: 0, won: 0 };
        if (l.is_winner) leadStats[party].won++;
        else leadStats[party].leading++;
    });

    // Merge with party info and votes
    const partyVotesMap = {};
    if (summaryData && summaryData.party_votes) {
        summaryData.party_votes.forEach(v => {
            partyVotesMap[v.short_name] = v.total_votes;
        });
    }

    const seatsMap = {};
    if (summaryData && summaryData.party_seats) {
        summaryData.party_seats.forEach(s => {
            seatsMap[s.short_name] = s.seats;
        });
    }

    // Build merged array
    const merged = allParties.map(p => {
        const ls = leadStats[p.short_name] || { leading: 0, won: 0 };
        const won = seatsMap[p.short_name] || ls.won;
        const leading = ls.leading;
        return {
            id: p.id,
            name: p.name,
            name_np: p.name_np || p.name,
            short_name: p.short_name,
            short_name_np: p.short_name_np || p.short_name,
            color: p.color,
            leading: leading,
            won: won,
            total_seats: leading + won,
            total_votes: partyVotesMap[p.short_name] || 0,
        };
    });

    // Sort by total_seats desc, then total_votes desc
    merged.sort((a, b) => b.total_seats - a.total_seats || b.total_votes - a.total_votes || a.name.localeCompare(b.name));
    return merged;
}

// ═══════════════════════ PARTY TABLE ═══════════════════════
function renderPartyTable() {
    const tbody = document.getElementById("partyTableBody");
    const stats = getPartyStats();
    const maxSeats = Math.max(1, ...stats.map(p => p.total_seats));

    tbody.innerHTML = stats.map(p => {
        const barWidth = maxSeats > 0 ? (p.total_seats / maxSeats) * 100 : 0;
        const leadingDisplay = p.leading > 0 ? p.leading : "-";
        const winDisplay = p.won > 0 ? p.won : "-";
        const totalDisplay = p.total_seats;
        const votesDisplay = p.total_votes > 0 ? formatNumber(p.total_votes) : "0";
        const logoText = p.short_name_np || p.short_name;
        const logoHtml = p.logo_url
            ? `<img class="party-logo-img" src="${p.logo_url}" alt="${p.short_name}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="party-logo" style="background:${p.color};display:none">${logoText.substring(0, 3)}</div>`
            : `<div class="party-logo" style="background:${p.color};">${logoText.substring(0, 3)}</div>`;

        return `<tr onclick="showPartyConstituencies(${p.id})">
            <td class="td-party">
                <div class="party-cell">
                    ${logoHtml}
                    <div class="party-cell-info">
                        <div class="party-cell-name">${p.name_np}</div>
                        <div class="party-cell-bar">
                            <div class="party-cell-bar-fill" style="width:${barWidth}%;background:${p.color};"></div>
                        </div>
                    </div>
                </div>
            </td>
            <td class="td-leading">${leadingDisplay}</td>
            <td class="td-win">${winDisplay}</td>
            <td class="td-total">${totalDisplay}</td>
            <td class="td-pr-votes">${votesDisplay}</td>
        </tr>`;
    }).join("");
}

// ═══════════════════════ SIDEBAR PARTY BARS ═══════════════════════
function renderSidebarBars() {
    const container = document.getElementById("partyBars");
    const stats = getPartyStats();

    container.innerHTML = stats.map(p => {
        return `<div class="party-bar-row">
            <div class="party-bar-label" style="background:${p.color};">${p.name_np}</div>
            <span class="party-bar-seats">${p.total_seats} सिट</span>
        </div>`;
    }).join("");
}

// ═══════════════════════ HEMICYCLE VISUALIZATION ═══════════════════════
function renderHemicycle() {
    const svg = document.getElementById("hemicycleSvg");
    if (!svg) return;

    const stats = getPartyStats();

    // Build seat-to-color mapping
    // Seats are filled in order: party1's total_seats, party2's total_seats, ...
    const seatColors = [];
    stats.forEach(p => {
        for (let i = 0; i < p.total_seats; i++) {
            seatColors.push(p.color);
        }
    });
    // Fill remaining with gray
    while (seatColors.length < TOTAL_SEATS) {
        seatColors.push("#ddd");
    }

    let seatIndex = 0;
    let circles = '';

    // Add a subtle building dome outline
    circles += `<path d="M 60 ${HEMI_CY} Q 60 15, 180 15 Q 300 15, 300 ${HEMI_CY}" 
        fill="none" stroke="#e0e4e8" stroke-width="1.5" stroke-dasharray="4,3" />`;

    // Draw hemicycle rows
    for (let row = 0; row < HEMI_ROWS.length; row++) {
        const n = HEMI_ROWS[row];
        const r = HEMI_RADII[row];
        const padding = 0.06; // radians padding at edges

        for (let i = 0; i < n; i++) {
            const angle = padding + (Math.PI - 2 * padding) * (n > 1 ? i / (n - 1) : 0.5);
            const x = HEMI_CX - r * Math.cos(angle);
            const y = HEMI_CY - r * Math.sin(angle);
            const color = seatColors[seatIndex] || "#ddd";

            circles += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${HEMI_DOT_R}" fill="${color}" opacity="${color === '#ddd' ? 0.5 : 0.85}" />`;
            seatIndex++;
        }
    }

    // Bottom line (podium)
    circles += `<line x1="50" y1="${HEMI_CY + 2}" x2="310" y2="${HEMI_CY + 2}" stroke="#d1d5db" stroke-width="2" />`;

    svg.innerHTML = circles;

    // Update center number
    const totalWon = stats.reduce((s, p) => s + p.total_seats, 0);
    const hemiNum = document.getElementById("hemiNumber");
    if (hemiNum) {
        hemiNum.textContent = toNepali(totalWon > 0 ? totalWon : 165);
    }
}

// ═══════════════════════ PROVINCES ═══════════════════════
async function loadProvinces() {
    try {
        const res = await fetch("/api/provinces");
        provinces = await res.json();
        renderProvinceTabs();
    } catch (err) {
        console.error("Failed to load provinces:", err);
    }
}

function renderProvinceTabs() {
    const container = document.getElementById("provinceTabs");
    const allBtn = `<button class="province-tab active" data-province="">All</button>`;
    const tabs = provinces.map(p =>
        `<button class="province-tab" data-province="${p.id}">${p.name}</button>`
    ).join("");

    container.innerHTML = allBtn + tabs;

    container.querySelectorAll(".province-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            container.querySelectorAll(".province-tab").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            currentProvince = tab.dataset.province;
            currentDistrict = "";

            if (currentProvince) {
                loadDistricts(currentProvince);
            } else {
                document.getElementById("districtBar").innerHTML = "";
            }
            loadConstituenciesData();
        });
    });
}

async function loadDistricts(provinceId) {
    try {
        const res = await fetch(`/api/districts?province_id=${provinceId}`);
        const districts = await res.json();
        renderDistrictChips(districts);
    } catch (err) {
        console.error("Failed to load districts:", err);
    }
}

function renderDistrictChips(districts) {
    const bar = document.getElementById("districtBar");
    const allChip = `<button class="district-chip active" data-district="">All Districts</button>`;
    const chips = districts.map(d =>
        `<button class="district-chip" data-district="${d.id}">${d.name}</button>`
    ).join("");

    bar.innerHTML = allChip + chips;

    bar.querySelectorAll(".district-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            bar.querySelectorAll(".district-chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            currentDistrict = chip.dataset.district;
            loadConstituenciesData();
        });
    });
}

// ═══════════════════════ STATUS PILLS ═══════════════════════
function initStatusPills() {
    document.querySelectorAll(".status-pill").forEach(pill => {
        pill.addEventListener("click", () => {
            document.querySelectorAll(".status-pill").forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            currentStatus = pill.dataset.status;
            loadConstituenciesData();
        });
    });
}

// ═══════════════════════ SEARCH ═══════════════════════
function initSearch() {
    let timeout;
    const input = document.getElementById("searchInput");
    if (!input) return;
    input.addEventListener("input", (e) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            searchQuery = e.target.value;
            loadConstituenciesData();
        }, 300);
    });
}

// ═══════════════════════ CONSTITUENCIES ═══════════════════════
async function loadConstituenciesData() {
    try {
        const params = new URLSearchParams();
        if (currentProvince) params.set("province_id", currentProvince);
        if (currentDistrict) params.set("district_id", currentDistrict);
        if (currentStatus) params.set("status", currentStatus);
        if (searchQuery) params.set("search", searchQuery);

        const res = await fetch(`/api/constituencies?${params}`);
        allConstituencies = await res.json();
        renderConstituencyList();
    } catch (err) {
        console.error("Failed to load constituencies:", err);
    }
}

function renderConstituencyList() {
    const list = document.getElementById("constituencyList");

    if (allConstituencies.length === 0) {
        list.innerHTML = `<div class="no-results-msg">
            <div class="icon">🔍</div>
            <div>No constituencies match your filters</div>
        </div>`;
        return;
    }

    list.innerHTML = allConstituencies.map(c => {
        const leaders = getConstituencyLeaders(c.id);
        return `<div class="c-card" onclick="showConstituencyModal(${c.id})">
            <div class="c-card-header">
                <div>
                    <div class="c-card-name">${c.name}</div>
                    <div class="c-card-district">${c.province_name} • ${c.district_name}</div>
                </div>
                <span class="c-status ${c.status}">${c.status}</span>
            </div>
            <div class="c-card-body">
                ${leaders.length > 0 ? leaders.map((l, i) =>
                    `<div class="c-candidate-row">
                        <div class="c-candidate-left">
                            <span class="c-party-dot" style="background:${l.party_color}"></span>
                            <span class="c-candidate-name">${l.candidate_name}</span>
                        </div>
                        <span class="c-candidate-party">${l.party_short}</span>
                        <span class="c-candidate-votes ${i === 0 ? 'leading' : ''}">${formatNumber(l.votes)}</span>
                    </div>`
                ).join("") : `<div style="padding:8px 0;color:var(--text-dim);font-size:0.82rem;">
                    Waiting for results...
                </div>`}
            </div>
            <div class="c-card-footer">
                <span>Votes counted: ${formatNumber(c.votes_counted)}</span>
                <span class="view-detail">View Details →</span>
            </div>
        </div>`;
    }).join("");
}

function getConstituencyLeaders(constituencyId) {
    const leaders = leadingData.filter(l => l.constituency && l.constituency.id === constituencyId);
    return leaders.map(l => ({
        candidate_name: l.leading_candidate || "Unknown",
        party_short: l.leading_party || "IND",
        party_color: l.leading_party_color || "#999",
        votes: l.votes || 0,
        is_winner: l.is_winner || false,
    }));
}

// ═══════════════════════ MODAL ═══════════════════════
function initModal() {
    document.getElementById("modalClose").addEventListener("click", closeModal);
    document.getElementById("modalOverlay").addEventListener("click", (e) => {
        if (e.target === e.currentTarget) closeModal();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeModal();
    });
}

async function showConstituencyModal(id) {
    const overlay = document.getElementById("modalOverlay");
    const body = document.getElementById("modalBody");

    overlay.classList.add("active");
    body.innerHTML = `<div class="loading-spinner"><div class="spinner"></div></div>`;

    try {
        const res = await fetch(`/api/constituency/${id}`);
        const data = await res.json();

        document.getElementById("modalTitle").textContent = data.constituency.name;
        document.getElementById("modalSub").innerHTML =
            `${data.constituency.district_name} • ${data.constituency.province_name}
             <span class="c-status ${data.constituency.status}" style="margin-left:8px;">${data.constituency.status}</span>`;

        if (data.results.length === 0) {
            body.innerHTML = `<div class="no-results-msg" style="margin:0;">
                <div class="icon">📭</div>
                <div>No results available yet</div>
            </div>`;
            return;
        }

        const totalVotes = data.results.reduce((sum, r) => sum + r.votes, 0);
        const maxVotes = Math.max(...data.results.map(r => r.votes));

        body.innerHTML = data.results.map((r, i) => {
            const pct = totalVotes > 0 ? ((r.votes / totalVotes) * 100).toFixed(1) : 0;
            const barWidth = maxVotes > 0 ? ((r.votes / maxVotes) * 100) : 0;
            const isFirst = i === 0;

            return `<div class="modal-result-row">
                <div class="modal-rank ${isFirst ? 'first' : ''}">${i + 1}</div>
                <div class="modal-candidate-info">
                    <div class="modal-candidate-name">
                        ${r.candidate_name}
                        ${r.is_winner ? '<span class="winner-badge">✓ WINNER</span>' : ''}
                    </div>
                    <div class="modal-candidate-party">
                        <span class="c-party-dot" style="background:${r.party_color}"></span>
                        ${r.party_name} (${r.party_short})
                    </div>
                    <div class="modal-vote-bar">
                        <div class="modal-vote-bar-fill" style="width:${barWidth}%;background:${r.party_color}"></div>
                    </div>
                </div>
                <div class="modal-votes">
                    <div class="vote-num">${formatNumber(r.votes)}</div>
                    <div class="vote-pct">${pct}%</div>
                </div>
            </div>`;
        }).join("");
    } catch (err) {
        console.error("Failed to load constituency detail:", err);
        body.innerHTML = `<div class="no-results-msg"><div>Failed to load details</div></div>`;
    }
}

function closeModal() {
    document.getElementById("modalOverlay").classList.remove("active");
}

// ═══════════════════════ PARTY CLICK → CONSTITUENCY TAB ═══════════════════════
function showPartyConstituencies(partyId) {
    document.querySelectorAll(".tab-btn").forEach(b => {
        b.classList.remove("active");
        if (b.dataset.tab === "constituency") b.classList.add("active");
    });
    ["party", "constituency", "candidates", "hot-seat"].forEach(t => {
        const el = document.getElementById(`tab-${t}`);
        if (el) el.style.display = t === "constituency" ? "block" : "none";
    });
    loadConstituenciesData();
}

// ═══════════════════════ SCRAPER STATUS ═══════════════════════
async function loadScraperStatus() {
    try {
        const resp = await fetch("/api/scraper-status");
        if (!resp.ok) return;
        const data = await resp.json();

        const sources = data.sources || {};
        let activeCount = 0;

        document.querySelectorAll(".src-ind").forEach(el => {
            const key = el.dataset.source;
            const info = sources[key];
            el.classList.remove("active", "error", "no-data");
            if (info) {
                if (info.status === "ok") {
                    el.classList.add("active");
                    el.title = `${info.display_name}: ${info.results_count} results`;
                    activeCount++;
                } else if (info.status === "error") {
                    el.classList.add("error");
                    el.title = `${info.display_name}: Error`;
                } else {
                    el.classList.add("no-data");
                    el.title = `${info.display_name}: No data yet`;
                }
            }
        });

        const sourceCountEl = document.getElementById("activeSourceCount");
        if (sourceCountEl) sourceCountEl.textContent = activeCount || data.scraper_count || 6;

        const infoEl = document.getElementById("scraperInfo");
        if (infoEl && data.last_run) {
            const ago = Math.round((Date.now() - new Date(data.last_run + "Z").getTime()) / 1000);
            infoEl.textContent = `Last scrape: ${ago}s ago | Run #${data.total_runs || 0} | ${data.total_updates || 0} updates`;
        }
    } catch (err) {
        // Non-critical
    }
}

setInterval(loadScraperStatus, 15000);
setTimeout(loadScraperStatus, 2000);

// ═══════════════════════ HELPERS ═══════════════════════
function formatNumber(n) {
    if (n === null || n === undefined) return "0";
    return Number(n).toLocaleString("en-IN");
}
