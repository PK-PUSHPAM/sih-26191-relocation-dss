import React, { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";

function asFeatureCollection(data) {
  if (data?.type === "FeatureCollection") return data;
  if (data?.data?.type === "FeatureCollection") return data.data;
  return null;
}

export default function MapView({data}) {
  const ref=useRef(null);
  useEffect(()=>{
    if(!ref.current)return;
    const map=new maplibregl.Map({
      container:ref.current,
      style:"https://demotiles.maplibre.org/style.json",
      center:[79.6,30.4],
      zoom:7,
      attributionControl:true,
    });
    map.addControl(new maplibregl.NavigationControl(),"top-right");
    map.on("load",()=>{
      const geojson=asFeatureCollection(data);
      if(!geojson)return;
      map.addSource("backend-geojson",{type:"geojson",data:geojson});
      map.addLayer({
        id:"backend-fill",
        type:"fill",
        source:"backend-geojson",
        filter:["==",["geometry-type"],"Polygon"],
        paint:{"fill-opacity":0.28},
      });
      map.addLayer({
        id:"backend-line",
        type:"line",
        source:"backend-geojson",
        filter:["==",["geometry-type"],"LineString"],
        paint:{"line-width":2},
      });
      map.addLayer({
        id:"backend-point",
        type:"circle",
        source:"backend-geojson",
        filter:["==",["geometry-type"],"Point"],
        paint:{"circle-radius":5,"circle-opacity":0.85},
      });
    });
    return()=>map.remove();
  },[data]);
  return <div className="map" ref={ref} aria-label="MapLibre spatial view"/>;
}
