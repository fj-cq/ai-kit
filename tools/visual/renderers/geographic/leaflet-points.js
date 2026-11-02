/* Visual Kit: offline administrative boundaries + sample points.
 * Requires Leaflet 1.9.4. No tiles, network requests, or inferred locations. */
(function (global) {
  'use strict';
  // Leaflet renders attribution strings as HTML. This API accepts plain text.
  function escapeText(value) {
    return String(value).replace(/[&<>"']/g, c => ({
      '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
    })[c]);
  }
  function mount(container, spec, onSelect) {
    if (!global.L) throw new Error('Load pinned Leaflet before geographic-visuals.');
    if (!container || !spec.geometry || !Array.isArray(spec.points) || !spec.points.length)
      throw new Error('A container, published GeoJSON and explicit points are required.');
    const ids = new Set();
    spec.points.forEach(p => {
      if (!p.id || ids.has(p.id) || !Number.isFinite(p.latitude) || !Number.isFinite(p.longitude) || Math.abs(p.latitude)>85 || Math.abs(p.longitude)>180)
        throw new Error('Points need unique IDs and finite latitude/longitude; this renderer excludes polar latitudes.');
      ids.add(p.id);
    });
    const L = global.L;
    const colors = Object.assign({accent:'#1E2878',focus:'#E8EBF4',land:'#F8F9FC',border:'#AEB6C9'},spec.colors);
    const focus = spec.geometry.features.find(f=>String(f.properties[spec.featureKey])===String(spec.focusId));
    if (!focus) throw new Error('focusId must resolve to a published geographic feature.');
    const map = L.map(container,{scrollWheelZoom:false,zoomSnap:.25,zoomDelta:.5,minZoom:3,maxZoom:11,attributionControl:true,keyboard:true,zoomAnimation:false,fadeAnimation:false});
    map.attributionControl.setPrefix('Leaflet 1.9.4');
    map.attributionControl.addAttribution(escapeText(spec.attribution || 'Boundary source required'));
    L.geoJSON(spec.geometry,{interactive:false,style:f=>({color:colors.border,weight:1,fillColor:f===focus?colors.focus:colors.land,fillOpacity:1})}).addTo(map);
    const regionBounds=L.geoJSON(focus).getBounds();
    const pointBounds=L.latLngBounds(spec.points.map(p=>[p.latitude,p.longitude]));
    if (spec.grid) L.geoJSON(spec.grid,{interactive:false,style:{color:colors.accent,weight:1,opacity:.2}}).addTo(map);
    (spec.labels||[]).forEach(label=>{
      const text=document.createElement('span');text.className='vk-region-label';text.textContent=label.text;
      L.marker([label.latitude,label.longitude],{icon:L.divIcon({html:text,className:'vk-region-host',iconSize:[130,24],iconAnchor:[65,12]}),interactive:false,keyboard:false}).addTo(map);
    });
    const buttons=new Map();
    spec.points.forEach(p=>{
      const button=document.createElement('button');button.type='button';button.className='vk-geo-point '+(p.outside?'vk-outside':'vk-inside');
      button.textContent=p.label || p.id;
      button.setAttribute('aria-label',p.description || p.id);
      button.setAttribute('aria-pressed','false');
      button.dataset.pointId=p.id;
      L.DomEvent.disableClickPropagation(button);
      button.addEventListener('click',()=>select(p.id,true));
      L.marker([p.latitude,p.longitude],{icon:L.divIcon({html:button,className:'vk-point-host',iconSize:[36,36],iconAnchor:[18,18]}),keyboard:false,riseOnHover:false}).addTo(map);
      buttons.set(p.id,button);
    });
    L.control.scale({imperial:false,position:'bottomleft',maxWidth:100}).addTo(map);
    function fit(view) {
      map.invalidateSize({pan:false});
      map.fitBounds(view==='region'?regionBounds:pointBounds,{padding:[45,45],maxZoom:view==='region'?6.5:8,animate:false});
    }
    function select(id,notify=false) {
      if (!ids.has(id)) throw new Error('Unknown point: '+id);
      buttons.forEach((button,key)=>{button.classList.toggle('is-selected',key===id);button.setAttribute('aria-pressed',String(key===id));});
      if(notify && onSelect) onSelect(id);
    }
    function compactMarkers() {
      let spacing=Infinity;
      const positions=spec.points.map(p=>map.latLngToContainerPoint([p.latitude,p.longitude]));
      positions.forEach((p,i)=>positions.slice(i+1).forEach(q=>{spacing=Math.min(spacing,p.distanceTo(q));}));
      container.classList.toggle('vk-compact-points',spacing<39);
    }
    map.on('zoomend moveend',compactMarkers);
    const resize = new ResizeObserver(()=>{map.invalidateSize({pan:false});compactMarkers();});
    resize.observe(container);
    fit(spec.initialView || 'points');
    select(spec.selectedId || spec.points[0].id);
    return {fit,select,destroy(){resize.disconnect();map.remove();}};
  }
  global.VisualKitGeo={mount};
})(window);
