import React, { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";

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
    return()=>map.remove();
  },[]);
  return <div className="map" ref={ref} aria-label="MapLibre spatial view"><div className="map-data-badge">{Array.isArray(data)?"Rows":"GeoJSON/API payload"} loaded</div></div>;
}
