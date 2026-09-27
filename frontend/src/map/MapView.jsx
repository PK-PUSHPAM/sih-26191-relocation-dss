import React, { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";

function asFeatureCollection(data) {
  if (data?.type === "FeatureCollection") return data;
  if (data?.data?.type === "FeatureCollection") return data.data;
  return null;
}

export default function MapView({ data, mode = "hazards" }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return;

    const map = new maplibregl.Map({
      container: ref.current,
      style: "https://demotiles.maplibre.org/style.json",
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
              "#45aeb0",
            ],
            "fill-opacity": 0.38,
          },
        });
      } else {
        map.addLayer({
          id: "backend-fill",
          type: "fill",
          source: "backend-geojson",
          filter: ["==", ["geometry-type"], "Polygon"],
          paint: {
            "fill-color": "#43cfc0",
            "fill-opacity": 0.24,
          },
        });
      }

      map.addLayer({
        id: "backend-line",
        type: "line",
        source: "backend-geojson",
        filter: ["==", ["geometry-type"], "LineString"],
        paint: {
          "line-color": mode === "risk" ? "#e8b84e" : "#43cfc0",
          "line-width": 2,
          "line-opacity": 0.8,
        },
      });

      map.addLayer({
        id: "backend-point",
        type: "circle",
        source: "backend-geojson",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-radius": 5,
          "circle-color": mode === "risk" ? "#ff6b6b" : "#43cfc0",
          "circle-stroke-color": "#071115",
          "circle-stroke-width": 1.5,
          "circle-opacity": 0.9,
        },
      });
    });

    return () => map.remove();
  }, [data, mode]);

  return <div className="map" ref={ref} aria-label="MapLibre spatial view" />;
}
