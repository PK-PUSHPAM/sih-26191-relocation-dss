import React, { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";

function asFeatureCollection(data) {
  if (data?.type === "FeatureCollection") return data;
  if (data?.data?.type === "FeatureCollection") return data.data;
  return null;
}

function getBounds(geojson) {
  const bounds = new maplibregl.LngLatBounds();
  let found = false;
  const visit = (coordinates) => {
    if (!Array.isArray(coordinates)) return;
    if (coordinates.length >= 2 && typeof coordinates[0] === "number" && typeof coordinates[1] === "number") {
      bounds.extend([coordinates[0], coordinates[1]]);
      found = true;
      return;
    }
    coordinates.forEach(visit);
  };
  (geojson?.features || []).forEach((feature) => visit(feature.geometry?.coordinates));
  return found ? bounds : null;
}

function popupHtml(properties = {}) {
  const entries = Object.entries(properties)
    .filter(([key, value]) => value !== null && value !== undefined && typeof value !== "object")
    .slice(0, 8);
  if (!entries.length) return "<strong>Spatial feature</strong>";
  return `<div style="font-family:Arial,sans-serif;min-width:170px"><strong style="display:block;margin-bottom:7px">Spatial feature</strong>${entries.map(([key,value]) => `<div style="display:flex;justify-content:space-between;gap:12px;border-top:1px solid #ddd;padding:4px 0;font-size:11px"><span>${key.replaceAll("_"," ")}</span><b>${String(value)}</b></div>`).join("")}</div>`;
}

export default function MapView({ data, mode = "hazards" }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return;

    const map = new maplibregl.Map({
      container: ref.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [{
          id: "osm",
          type: "raster",
          source: "osm",
          paint: {
            "raster-opacity": 0.78,
            "raster-saturation": -0.75,
            "raster-contrast": 0.12,
            "raster-brightness-min": 0.08,
            "raster-brightness-max": 0.65,
          },
        }],
      },
      center: [79.6, 30.4],
      zoom: 7,
      attributionControl: true,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", () => {
      const geojson = asFeatureCollection(data);
      if (!geojson) return;

      map.addSource("backend-geojson", { type: "geojson", data: geojson });
      const bounds = getBounds(geojson);
      if (bounds && !bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 55, maxZoom: 13, duration: 600 });
      }

      const riskExpression = [
        "case",
        ["==", ["coalesce", ["get", "risk_tier"], ["get", "tier"]], "Immediate"], "#ff5f67",
        ["==", ["coalesce", ["get", "risk_tier"], ["get", "tier"]], "immediate"], "#ff5f67",
        ["==", ["coalesce", ["get", "risk_tier"], ["get", "tier"]], "Short-term"], "#e8b84e",
        ["==", ["coalesce", ["get", "risk_tier"], ["get", "tier"]], "short-term"], "#e8b84e",
        ["==", ["coalesce", ["get", "risk_tier"], ["get", "tier"]], "Medium-term"], "#66c49b",
        "#48d5bd",
      ];

      map.addLayer({
        id: "backend-fill",
        type: "fill",
        source: "backend-geojson",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: {
          "fill-color": mode === "risk" ? riskExpression : "#48d5bd",
          "fill-opacity": mode === "risk" ? 0.32 : 0.14,
          "fill-outline-color": mode === "risk" ? "#d7eeee" : "#48d5bd",
        },
      });

      map.addLayer({
        id: "backend-line",
        type: "line",
        source: "backend-geojson",
        filter: ["==", ["geometry-type"], "LineString"],
        paint: {
          "line-color": mode === "risk" ? "#ffb45c" : "#48d5bd",
          "line-width": 2,
          "line-opacity": 0.9,
        },
      });

      map.addLayer({
        id: "backend-point",
        type: "circle",
        source: "backend-geojson",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-radius": mode === "risk" ? 6 : 5,
          "circle-color": mode === "risk" ? riskExpression : "#48d5bd",
          "circle-stroke-color": "#071115",
          "circle-stroke-width": 2,
          "circle-opacity": 0.95,
        },
      });

      const interactive = ["backend-fill", "backend-line", "backend-point"];
      interactive.forEach(layer => {
        map.on("mouseenter", layer, () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", layer, () => { map.getCanvas().style.cursor = ""; });
        map.on("click", layer, (event) => {
          const feature = event.features?.[0];
          if (!feature) return;
          new maplibregl.Popup({ closeButton: true, maxWidth: "300px" })
            .setLngLat(event.lngLat)
            .setHTML(popupHtml(feature.properties))
            .addTo(map);
        });
      });
    });

    return () => map.remove();
  }, [data, mode]);

  return <div className="map" ref={ref} aria-label="Interactive MapLibre spatial decision map" />;
}
