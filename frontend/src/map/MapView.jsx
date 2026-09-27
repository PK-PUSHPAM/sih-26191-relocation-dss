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

export default function MapView({ data, mode = "hazards" }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return;

    const map = new maplibregl.Map({
      container: ref.current,
      style: {
        version: 8,
        sources: {
          "carto-dark": {
            type: "raster",
            tiles: [
              "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
              "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
              "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
            ],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors © CARTO",
          },
        },
        layers: [
          {
            id: "carto-dark",
            type: "raster",
            source: "carto-dark",
            paint: { "raster-opacity": 0.92 },
          },
        ],
      },
      center: [79.6, 30.4],
      zoom: 7,
      attributionControl: true,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", () => {
      const geojson = asFeatureCollection(data);
      if (!geojson) return;

      map.addSource("backend-geojson", {
        type: "geojson",
        data: geojson,
      });

      const bounds = getBounds(geojson);
      if (bounds && !bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 70, maxZoom: 11, duration: 700 });
      }

      if (mode === "risk") {
        map.addLayer({
          id: "backend-fill",
          type: "fill",
          source: "backend-geojson",
          filter: ["==", ["geometry-type"], "Polygon"],
          paint: {
            "fill-color": [
              "case",
              ["==", ["get", "risk_tier"], "immediate"], "#ff5f67",
              ["==", ["get", "risk_tier"], "short-term"], "#e8b84e",
              ["==", ["get", "risk_tier"], "medium-term"], "#66c49b",
              "#48d5bd",
            ],
            "fill-opacity": 0.28,
          },
        });
      } else {
        map.addLayer({
          id: "backend-fill",
          type: "fill",
          source: "backend-geojson",
          filter: ["==", ["geometry-type"], "Polygon"],
          paint: {
            "fill-color": "#48d5bd",
            "fill-opacity": 0.12,
          },
        });
      }

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
          "circle-radius": 5,
          "circle-color": mode === "risk" ? "#ff6b6b" : "#48d5bd",
          "circle-stroke-color": "#071115",
          "circle-stroke-width": 2,
          "circle-opacity": 0.95,
          "circle-blur": 0.05,
        },
      });
    });

    return () => map.remove();
  }, [data, mode]);

  return <div className="map" ref={ref} aria-label="MapLibre spatial view" />;
}
