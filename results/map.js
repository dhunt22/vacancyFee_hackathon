// ─────────────────────────────────────────────────────────────
//  Sacramento Vacant-Equity map
//  Leaflet + leaflet.markercluster + leaflet.heat
// ─────────────────────────────────────────────────────────────

(function () {
  const mapEl = document.getElementById("leafmap");
  if (!mapEl) return;

  const SAC_CENTER = [38.575, -121.45];
  const SAC_ZOOM = 11;

  const map = L.map("leafmap", {
    center: SAC_CENTER,
    zoom: SAC_ZOOM,
    minZoom: 9,
    maxZoom: 18,
    scrollWheelZoom: false,
  });
  // Enable scroll-wheel zoom only after user clicks into the map.
  map.once("focus", () => map.scrollWheelZoom.enable());
  map.on("click", () => map.scrollWheelZoom.enable());

  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: '© OpenStreetMap contributors · © CARTO',
    subdomains: "abcd",
    maxZoom: 19,
  }).addTo(map);

  // ── Layer: vacant parcels ────────────────────────────────────
  const tierColor = { 1: "#13587f", 2: "#3f6e55", 3: "#a04a17" };
  const tierName = { 1: "Coded vacant land", 2: "Zero improvement", 3: "Parking/abandoned" };
  const useName = { R: "Residential", C: "Commercial", V: "Vacant land", I: "Industrial", O: "Other" };

  function fmtMoney(n) {
    if (!n) return "—";
    if (n >= 1e6) return "$" + (n / 1e6).toFixed(2) + "M";
    if (n >= 1e3) return "$" + Math.round(n / 1e3) + "K";
    return "$" + n.toLocaleString();
  }
  function fmtNum(n) { return n ? n.toLocaleString() : "—"; }

  const parcelCluster = L.markerClusterGroup({
    chunkedLoading: true,
    maxClusterRadius: 60,
    iconCreateFunction: (cluster) => {
      const c = cluster.getChildCount();
      const size = c < 50 ? 32 : c < 500 ? 40 : c < 2000 ? 48 : 56;
      return L.divIcon({
        html: `<div class="cluster-pin"><span>${c.toLocaleString()}</span></div>`,
        className: "cluster-icon",
        iconSize: [size, size],
      });
    },
  });

  const hsHeat = L.heatLayer([], {
    radius: 18,
    blur: 22,
    maxZoom: 16,
    minOpacity: 0.35,
    gradient: { 0.3: "#fde68a", 0.55: "#f59e0b", 0.8: "#d97706", 1.0: "#9a3412" },
  });

  // ── Load data ────────────────────────────────────────────────
  Promise.all([
    fetch("map_data/vacant_parcels.json").then((r) => r.json()),
    fetch("map_data/hs_311.json").then((r) => r.json()),
    fetch("map_data/hotspots_summary.json").then((r) => r.json()),
  ])
    .then(([parcels, hs, hotspots]) => {
      addParcels(parcels);
      addHs(hs);
      renderHotspots(hotspots);
    })
    .catch((err) => {
      mapEl.innerHTML =
        '<div class="map-error">Map data unavailable. Run <code>python results/build_map_data.py</code> to generate it.</div>';
      console.error(err);
    });

  function addParcels(parcels) {
    const cities = parcels.cities;
    const markers = [];
    for (const p of parcels.points) {
      const [lat, lon, tier, useCode, assessed, market, gap, lot, cityIdx, apn] = p;
      const color = tierColor[tier] || "#5a6068";
      const m = L.circleMarker([lat, lon], {
        radius: 5,
        color: color,
        fillColor: color,
        weight: 1,
        fillOpacity: 0.75,
      });
      const cityName = cityIdx >= 0 ? cities[cityIdx] : "—";
      m.bindPopup(
        `<div class="popup">
          <div class="popup__title">${useName[useCode] || "Parcel"}</div>
          <div class="popup__meta">${cityName} · APN ${apn}</div>
          <table class="popup__table">
            <tr><th>Assessed</th><td>${fmtMoney(assessed)}</td></tr>
            <tr><th>Est. market</th><td>${fmtMoney(market)}</td></tr>
            <tr><th class="popup__gap">Prop 13 gap</th><td class="popup__gap">${fmtMoney(gap)}</td></tr>
            <tr><th>Lot size</th><td>${fmtNum(lot)} sqft</td></tr>
            <tr><th>Vacancy class</th><td>${tierName[tier] || "—"}</td></tr>
          </table>
          <div class="popup__foot">No owner info shown by design.</div>
        </div>`,
        { maxWidth: 280 },
      );
      markers.push(m);
    }
    parcelCluster.addLayers(markers);
    parcelCluster.addTo(map);
  }

  function addHs(hs) {
    const heatPoints = hs.points.map((p) => [p[0], p[1], 0.6]);
    hsHeat.setLatLngs(heatPoints);
    hsHeat.addTo(map);
  }

  function renderHotspots(hotspots) {
    const target = document.getElementById("mapStats");
    if (!target || !hotspots.length) return;
    const rows = hotspots
      .map(
        (h) => `
        <div class="hotspot">
          <div class="hotspot__city">${h.city.replace(/^\w/, (c) => c.toUpperCase()).toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())}</div>
          <div class="hotspot__num">${h.parcels.toLocaleString()}</div>
          <div class="hotspot__lbl">vacant parcels</div>
          <div class="hotspot__money">$${h.market_billions.toFixed(2)}B market value</div>
        </div>`,
      )
      .join("");
    target.innerHTML = `
      <h3 class="map-stats__title">Top 8 cities by vacant‑parcel count</h3>
      <div class="hotspot-grid">${rows}</div>`;
  }

  // ── Toggles ─────────────────────────────────────────────────
  document.querySelectorAll(".map-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      btn.classList.toggle("is-active");
      const layer = btn.dataset.layer;
      const on = btn.classList.contains("is-active");
      if (layer === "parcels") {
        if (on) parcelCluster.addTo(map);
        else map.removeLayer(parcelCluster);
      } else if (layer === "hs") {
        if (on) hsHeat.addTo(map);
        else map.removeLayer(hsHeat);
      }
    });
  });
})();
