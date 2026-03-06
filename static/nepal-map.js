/* ═══════════════════════ Nepal Map (Simplified SVG) ═══════════════════════ */
/*
 * This renders a simplified map of Nepal's 7 provinces.
 * Each province is a clickable region colored by the leading party.
 * For a production site, you'd use a full GeoJSON with district boundaries.
 */

const NepalMap = {
    // Simplified province SVG paths (approximate shapes)
    provincePaths: {
        1: { // Koshi
            name: "Koshi",
            d: "M 520,80 L 580,60 L 620,90 L 640,140 L 630,190 L 600,230 L 560,240 L 520,220 L 500,180 L 490,130 Z",
        },
        2: { // Madhesh
            name: "Madhesh",
            d: "M 330,230 L 400,220 L 480,225 L 520,220 L 560,240 L 600,230 L 600,280 L 560,300 L 480,310 L 400,300 L 330,280 Z",
        },
        3: { // Bagmati
            name: "Bagmati",
            d: "M 330,120 L 380,100 L 430,90 L 490,100 L 500,130 L 500,180 L 520,220 L 480,225 L 400,220 L 350,200 L 330,160 Z",
        },
        4: { // Gandaki
            name: "Gandaki",
            d: "M 230,90 L 290,70 L 330,80 L 330,120 L 330,160 L 350,200 L 320,220 L 270,210 L 230,180 L 220,130 Z",
        },
        5: { // Lumbini
            name: "Lumbini",
            d: "M 170,160 L 230,130 L 230,180 L 270,210 L 320,220 L 330,230 L 330,280 L 280,290 L 220,280 L 170,250 L 160,200 Z",
        },
        6: { // Karnali
            name: "Karnali",
            d: "M 100,80 L 160,60 L 210,70 L 230,90 L 220,130 L 170,160 L 160,200 L 130,180 L 90,150 L 80,110 Z",
        },
        7: { // Sudurpashchim
            name: "Sudurpashchim",
            d: "M 20,100 L 60,50 L 100,40 L 100,80 L 80,110 L 90,150 L 130,180 L 160,200 L 170,250 L 140,270 L 90,260 L 50,230 L 20,180 Z",
        },
    },

    render(container, mapData, tooltipEl) {
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("viewBox", "0 0 660 320");
        svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

        // Map province data to colors
        const provinceColors = {};
        const provinceInfo = {};
        
        mapData.forEach(d => {
            const pid = d.province_id;
            if (!provinceColors[pid] || d.total_votes > (provinceInfo[pid]?.maxVotes || 0)) {
                provinceColors[pid] = d.leading_color || "#2a2e3b";
                if (!provinceInfo[pid]) {
                    provinceInfo[pid] = {
                        districts: 0,
                        declared: 0,
                        counting: 0,
                        maxVotes: 0,
                        leadingParty: null,
                    };
                }
                provinceInfo[pid].maxVotes = d.total_votes;
                provinceInfo[pid].leadingParty = d.leading_party;
            }
            if (provinceInfo[pid]) {
                provinceInfo[pid].districts += 1;
                provinceInfo[pid].declared += d.declared;
                provinceInfo[pid].counting += d.counting;
            }
        });

        Object.entries(this.provincePaths).forEach(([id, province]) => {
            const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
            path.setAttribute("d", province.d);
            path.setAttribute("fill", provinceColors[id] || "#2a2e3b");
            path.setAttribute("data-province", id);
            path.setAttribute("data-name", province.name);

            // Tooltip events
            path.addEventListener("mouseenter", (e) => {
                const info = provinceInfo[id] || {};
                tooltipEl.innerHTML = `
                    <strong>${province.name} Province</strong><br>
                    <span style="color:var(--text-dim)">
                        Districts: ${info.districts || "-"}<br>
                        Declared: ${info.declared || 0}<br>
                        Counting: ${info.counting || 0}<br>
                        Leading: ${info.leadingParty || "N/A"}
                    </span>
                `;
                tooltipEl.style.opacity = "1";
            });

            path.addEventListener("mousemove", (e) => {
                const rect = container.getBoundingClientRect();
                tooltipEl.style.left = (e.clientX - rect.left + 15) + "px";
                tooltipEl.style.top = (e.clientY - rect.top - 10) + "px";
            });

            path.addEventListener("mouseleave", () => {
                tooltipEl.style.opacity = "0";
            });

            svg.appendChild(path);

            // Province labels
            const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
            const bbox = getPathCenter(province.d);
            text.setAttribute("x", bbox.x);
            text.setAttribute("y", bbox.y);
            text.setAttribute("text-anchor", "middle");
            text.setAttribute("fill", "#ffffff");
            text.setAttribute("font-size", "11");
            text.setAttribute("font-weight", "600");
            text.setAttribute("pointer-events", "none");
            text.setAttribute("font-family", "Inter, sans-serif");
            text.textContent = province.name;
            svg.appendChild(text);
        });

        container.innerHTML = "";
        container.appendChild(svg);
    }
};

function getPathCenter(d) {
    // Simple center calculation from path coordinates
    const nums = d.match(/[\d.]+/g).map(Number);
    let sumX = 0, sumY = 0, count = 0;
    for (let i = 0; i < nums.length; i += 2) {
        sumX += nums[i];
        sumY += nums[i + 1];
        count++;
    }
    return { x: sumX / count, y: sumY / count };
}
