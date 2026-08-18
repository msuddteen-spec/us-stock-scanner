"""Interactive, mobile-first stock card deck powered by Three.js."""

from __future__ import annotations

from typing import Any

import streamlit as st


_HTML = """
<div class="deck-root" role="region" aria-label="รายการหุ้นแบบปัดซ้ายขวา">
  <div class="deck-ui"></div>
</div>
"""


_CSS = """
:host { display: block; width: 100%; }
.deck-root {
  position: relative; height: 540px; overflow: hidden; border-radius: 28px;
  background: linear-gradient(145deg, #0b1428 0%, #14213d 56%, #0e7490 150%);
  touch-action: pan-y; user-select: none; -webkit-user-select: none; -webkit-touch-callout: none; isolation: isolate;
  box-shadow: 0 20px 55px rgba(15, 23, 42, .23);
}
.three-canvas { position:absolute; inset:0; width:100%; height:100%; opacity:.82; pointer-events:none; }
.deck-ui { position:absolute; inset:0; z-index:1; padding:20px; color:#f8fafc; }
.deck-label { font: 700 11px/1.2 var(--st-font, Inter, sans-serif); letter-spacing:.12em; color:#93c5fd; }
.deck-count { float:right; font: 600 12px/1.2 var(--st-font, Inter, sans-serif); color:#cbd5e1; letter-spacing:0; }
.stock-card, .stock-card * {
  user-select:none; -webkit-user-select:none; -webkit-touch-callout:none;
}
.stock-card {
  position:absolute; left:20px; right:20px; top:62px; height:398px; box-sizing:border-box;
  padding:22px; border-radius:24px; background:rgba(255,255,255,.96); color:#14213d;
  box-shadow:0 18px 42px rgba(0,0,0,.28); border:1px solid rgba(255,255,255,.65);
  display:flex; flex-direction:column; gap:13px; will-change:transform,opacity; transition:transform .32s cubic-bezier(.2,.8,.2,1), opacity .24s ease;
}
.stock-top { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
.rank { font:700 13px/1.1 var(--st-font, Inter, sans-serif); color:#64748b; }
.ticker { margin-top:3px; font:800 30px/1 var(--st-font, Inter, sans-serif); letter-spacing:-.045em; }
.company { margin-top:6px; max-width:240px; font:500 12px/1.35 var(--st-font, Inter, sans-serif); color:#64748b; }
.signal { padding:7px 10px; border-radius:999px; font:700 12px/1 var(--st-font, Inter, sans-serif); white-space:nowrap; }
.signal.buy { background:#dcfce7; color:#166534; }.signal.hold { background:#fef3c7; color:#92400e; }.signal.sell { background:#fee2e2; color:#991b1b; }
.price-label, .mini-label { font:600 11px/1.15 var(--st-font, Inter, sans-serif); color:#64748b; }
.price { margin-top:2px; font:800 42px/1 var(--st-font, Inter, sans-serif); letter-spacing:-.06em; color:#0f766e; }
.base { padding:10px 12px; border-radius:14px; background:#f1f5f9; font:600 12px/1.35 var(--st-font, Inter, sans-serif); color:#475569; }
.levels { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.level { padding:12px; border:1px solid #e2e8f0; border-radius:16px; background:#fff; }
.level-value { margin-top:4px; font:800 18px/1 var(--st-font, Inter, sans-serif); letter-spacing:-.035em; }
.reason { margin-top:auto; font:500 12px/1.4 var(--st-font, Inter, sans-serif); color:#475569; }
.gesture { position:absolute; left:20px; right:20px; bottom:19px; display:flex; align-items:center; justify-content:space-between; font:600 12px/1.2 var(--st-font, Inter, sans-serif); color:#dbeafe; }
.dots { display:flex; gap:5px; }.dot { width:6px; height:6px; border-radius:999px; background:rgba(255,255,255,.32); }.dot.active { width:20px; background:#5eead4; }
@media (max-width: 420px) { .deck-root { height:520px; } .stock-card { height:384px; top:59px; padding:20px; } .price { font-size:38px; } }
"""


_JS = """
const deckInstances = new WeakMap();

function text(tag, className, value) {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = value ?? "—";
  return node;
}

async function startThreeBackground(root, state) {
  try {
    const THREE = await import("https://cdn.jsdelivr.net/npm/three@0.164.1/build/three.module.js");
    if (state.destroyed) return;
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.domElement.className = "three-canvas";
    root.prepend(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.z = 5;
    const group = new THREE.Group(); scene.add(group);
    const material = new THREE.MeshBasicMaterial({ color: 0x2dd4bf, transparent: true, opacity: 0.16, wireframe: true });
    group.add(new THREE.Mesh(new THREE.IcosahedronGeometry(1.65, 2), material));
    const orb = new THREE.Mesh(new THREE.SphereGeometry(.82, 36, 24), new THREE.MeshBasicMaterial({ color: 0x60a5fa, transparent:true, opacity:.16 }));
    orb.position.set(1.9, -1.3, -1); group.add(orb);
    const resize = () => { const w = root.clientWidth || 1; const h = root.clientHeight || 1; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); };
    resize();
    const observer = new ResizeObserver(resize); observer.observe(root);
    let frame;
    const animate = () => { group.rotation.y += .0025; group.rotation.x += .0012; orb.position.y = -1.3 + Math.sin(performance.now() / 1400) * .18; renderer.render(scene, camera); frame = requestAnimationFrame(animate); };
    animate();
    state.cleanupThree = () => { cancelAnimationFrame(frame); observer.disconnect(); renderer.dispose(); renderer.domElement.remove(); };
  } catch (_) {
    // The deck remains fully usable if the CDN is unavailable.
  }
}

function createCard(item, index) {
  const card = document.createElement("article");
  card.className = "stock-card";
  const top = document.createElement("div"); top.className = "stock-top";
  const identity = document.createElement("div");
  identity.append(text("div", "rank", `อันดับ ${index + 1}`), text("div", "ticker", item.symbol), text("div", "company", item.company));
  const signal = text("div", `signal ${item.actionClass}`, item.action); top.append(identity, signal);
  const priceBlock = document.createElement("div"); priceBlock.append(text("div", "price-label", "ราคาปัจจุบัน"), text("div", "price", item.price));
  const base = text("div", "base", `ฐานใหม่ที่รอ: ${item.base}`);
  const levels = document.createElement("div"); levels.className = "levels";
  for (const [label, value] of [["แนวรับ", item.support], ["แนวต้าน", item.resistance]]) {
    const level = document.createElement("div"); level.className = "level";
    level.append(text("div", "mini-label", label), text("div", "level-value", value)); levels.appendChild(level);
  }
  card.append(top, priceBlock, base, levels, text("div", "reason", item.reason));
  return card;
}

export default function(component) {
  const { data, parentElement, setStateValue } = component;
  const root = parentElement.querySelector(".deck-root");
  if (!root) return;
  let state = deckInstances.get(root);
  if (!state) {
    state = { root, index: 0, cards: [], startPoint: null, destroyed: false, cleanupThree: null };
    deckInstances.set(root, state); startThreeBackground(root, state);
    root.addEventListener("pointerdown", event => {
      state.startPoint = { x: event.clientX, y: event.clientY }; root.setPointerCapture?.(event.pointerId);
    }, { passive: false });
    root.addEventListener("pointermove", event => {
      if (!state.startPoint) return;
      const horizontalDistance = Math.abs(event.clientX - state.startPoint.x);
      const verticalDistance = Math.abs(event.clientY - state.startPoint.y);
      if (horizontalDistance > verticalDistance) event.preventDefault();
    }, { passive: false });
    root.addEventListener("pointerup", event => {
      if (!state.startPoint) return;
      const delta = event.clientX - state.startPoint.x;
      const verticalDelta = event.clientY - state.startPoint.y;
      state.startPoint = null;
      if (Math.abs(delta) < 26 || Math.abs(delta) < Math.abs(verticalDelta)) return;
      const next = Math.max(0, Math.min(state.cards.length - 1, state.index + (delta < 0 ? 1 : -1)));
      if (next !== state.index) { state.index = next; state.render(); setStateValue("index", next); }
    });
    root.addEventListener("pointercancel", () => { state.startPoint = null; });
    root.addEventListener("contextmenu", event => event.preventDefault());
    root.addEventListener("selectstart", event => event.preventDefault());
    root.addEventListener("wheel", event => {
      if (Math.abs(event.deltaX) < 12 || Math.abs(event.deltaX) <= Math.abs(event.deltaY)) return;
      const next = Math.max(0, Math.min(state.cards.length - 1, state.index + (event.deltaX > 0 ? 1 : -1)));
      if (next !== state.index) { event.preventDefault(); state.index = next; state.render(); setStateValue("index", next); }
    }, { passive: false });
  }
  const items = data?.items || [];
  const desired = Number.isInteger(data?.index) ? data.index : state.index;
  state.index = Math.max(0, Math.min(Math.max(0, items.length - 1), desired));
  state.cards.forEach(card => card.remove()); state.cards = [];
  const ui = root.querySelector(".deck-ui"); ui.replaceChildren();
  const label = text("div", "deck-label", "STOCK PULSE");
  const count = text("span", "deck-count", `${state.index + 1} / ${items.length}`); label.appendChild(count); ui.appendChild(label);
  state.cards = items.map(createCard);
  state.cards.forEach(card => ui.appendChild(card));
  const gesture = document.createElement("div"); gesture.className = "gesture";
  gesture.append(text("span", "", "ปัดซ้าย–ขวาเพื่อดูหุ้น"));
  const dots = document.createElement("div"); dots.className = "dots";
  items.forEach((_, i) => { const dot = document.createElement("span"); dot.className = `dot ${i === state.index ? "active" : ""}`; dots.appendChild(dot); });
  gesture.appendChild(dots); ui.appendChild(gesture);
  state.render = () => {
    state.cards.forEach((card, i) => {
      const offset = i - state.index;
      card.style.transform = `translateX(${offset * 108}%) scale(${offset === 0 ? 1 : .94}) rotate(${offset * 1.5}deg)`;
      card.style.opacity = Math.abs(offset) > 1 ? "0" : (offset === 0 ? "1" : ".35");
      card.style.pointerEvents = offset === 0 ? "auto" : "none";
    });
    count.textContent = `${state.index + 1} / ${items.length}`;
    dots.querySelectorAll(".dot").forEach((dot, i) => dot.classList.toggle("active", i === state.index));
  };
  state.render();
  return () => { state.destroyed = true; state.cleanupThree?.(); deckInstances.delete(root); };
}
"""


_STOCK_CARD_DECK = st.components.v2.component(
    "threejs_stock_card_deck_horizontal_v2",
    html=_HTML,
    css=_CSS,
    js=_JS,
)


_HERO_HTML = """
<section class="pulse-hero" aria-label="หุ้นเด่นวันนี้">
  <div class="hero-copy">
    <div class="hero-kicker"><span class="status-dot"></span> STOCK PULSE <span class="live-pill">PAPER ONLY</span></div>
    <h1>หุ้นเด่นวันนี้</h1>
    <p>สแกนจังหวะ Swing, ฐานราคา และแนวรับ–แนวต้านของหุ้นสหรัฐ</p>
    <p class="hero-note">เพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำการลงทุน</p>
  </div>
  <div class="hero-actions">
    <button class="refresh-button" type="button" aria-label="รีเฟรชข้อมูลหุ้น">
      <span class="refresh-icon">↻</span> รีเฟรชหุ้น
    </button>
  </div>
</section>
"""


_HERO_CSS = """
:host { display:block; width:100%; }
.pulse-hero { position:relative; min-height:160px; overflow:hidden; isolation:isolate; border:1px solid rgba(45,212,191,.32); border-radius:26px; padding:21px; box-sizing:border-box; color:#effcff; background:linear-gradient(128deg,#071426 0%,#0e2540 54%,#0d766e 160%); box-shadow:0 20px 46px rgba(2,8,23,.34); }
.hero-canvas { position:absolute; inset:0; z-index:-1; width:100%; height:100%; opacity:.82; pointer-events:none; }
.hero-copy { max-width:620px; }
.hero-kicker { display:flex; align-items:center; gap:7px; font:800 11px/1.2 var(--st-font,Inter,sans-serif); letter-spacing:.13em; color:#a5f3fc; }
.status-dot { width:8px; height:8px; border-radius:50%; background:#5eead4; box-shadow:0 0 15px #2dd4bf; }
.live-pill { padding:5px 8px; border:1px solid rgba(255,255,255,.17); border-radius:999px; background:rgba(255,255,255,.08); font:700 10px/1 var(--st-font,Inter,sans-serif); letter-spacing:.06em; }
.pulse-hero h1 { margin:10px 0 5px; font:800 clamp(28px,4.6vw,42px)/1 var(--st-font,Inter,sans-serif); letter-spacing:-.055em; }
.pulse-hero p { margin:0; font:500 13px/1.4 var(--st-font,Inter,sans-serif); color:#cfe4f3; }.hero-note { margin-top:5px!important; color:#93aec2!important; font-size:11px!important; }
.hero-actions { position:absolute; right:20px; top:20px; display:flex; align-items:center; gap:10px; }
.refresh-button { appearance:none; border:1px solid rgba(153,246,228,.55); border-radius:999px; padding:11px 16px; cursor:pointer; color:#052e2b; background:linear-gradient(135deg,#99f6e4,#2dd4bf); box-shadow:0 9px 20px rgba(20,184,166,.28); font:800 13px/1 var(--st-font,Inter,sans-serif); transition:transform .18s ease,box-shadow .18s ease; }.refresh-button:hover { transform:translateY(-2px); box-shadow:0 13px 26px rgba(20,184,166,.38); }.refresh-button:active { transform:translateY(0) scale(.98); }.refresh-button:disabled { opacity:.5; cursor:not-allowed; transform:none; }
.refresh-icon { display:inline-block; margin-right:5px; font-size:18px; line-height:8px; vertical-align:-2px; }
@media (max-width:600px) { .pulse-hero { min-height:174px; padding:14px 18px; border-radius:23px; }.hero-actions { position:static; margin-top:8px; justify-content:flex-end; }.pulse-hero h1 { margin:8px 0 4px; font-size:28px; } }
"""


_HERO_JS = """
const heroInstances = new WeakMap();

async function startHeroScene(root, state) {
  try {
    const THREE = await import("https://cdn.jsdelivr.net/npm/three@0.164.1/build/three.module.js");
    if (state.destroyed) return;
    const renderer = new THREE.WebGLRenderer({ alpha:true, antialias:true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2)); renderer.domElement.className = "hero-canvas"; root.prepend(renderer.domElement);
    const scene = new THREE.Scene(); const camera = new THREE.PerspectiveCamera(45, 1, .1, 100); camera.position.z = 5.4;
    const group = new THREE.Group(); group.position.set(0, -.05, 0); group.scale.set(2.1, 1.42, 1); scene.add(group);
    const gridMaterial = new THREE.LineBasicMaterial({color:0x60a5fa,transparent:true,opacity:.13});
    for (let i = -2; i <= 2; i++) {
      const horizontal = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-2, i * .48, 0), new THREE.Vector3(2, i * .48, 0)]);
      const vertical = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(i * .8, -1.1, 0), new THREE.Vector3(i * .8, 1.1, 0)]);
      group.add(new THREE.Line(horizontal, gridMaterial), new THREE.Line(vertical, gridMaterial));
    }
    const prices = [-.72, -.58, -.68, -.34, -.44, -.08, .15, -.04, .36, .2, .66, .9];
    const pricePoints = prices.map((price, index) => new THREE.Vector3(-1.85 + index * .34, price, .16));
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pricePoints),
      new THREE.LineBasicMaterial({color:0x5eead4,transparent:true,opacity:.96})
    );
    group.add(line);
    const pointGeometry = new THREE.SphereGeometry(.045, 12, 12);
    pricePoints.forEach((point, index) => {
      const dot = new THREE.Mesh(pointGeometry, new THREE.MeshBasicMaterial({color:index === pricePoints.length - 1 ? 0xfbbf24 : 0x5eead4}));
      dot.position.copy(point); group.add(dot);
      const volumeHeight = .12 + Math.abs(prices[index]) * .34 + (index % 3) * .06;
      const volume = new THREE.Mesh(new THREE.BoxGeometry(.16, volumeHeight, .04), new THREE.MeshBasicMaterial({color:0x60a5fa,transparent:true,opacity:.34}));
      volume.position.set(point.x, -1.15 + volumeHeight / 2, 0); group.add(volume);
    });
    const resize = () => { const w=root.clientWidth||1,h=root.clientHeight||1; renderer.setSize(w,h,false); camera.aspect=w/h; camera.updateProjectionMatrix(); };
    resize(); const observer=new ResizeObserver(resize); observer.observe(root); let frame;
    const animate=()=>{ group.position.y=-.05+Math.sin(performance.now()/650)*.06; line.material.opacity=.76+Math.sin(performance.now()/360)*.2; renderer.render(scene,camera); frame=requestAnimationFrame(animate); }; animate();
    state.cleanup=()=>{cancelAnimationFrame(frame);observer.disconnect();renderer.dispose();renderer.domElement.remove();};
  } catch (_) { /* The hero remains usable when a graphics connection is unavailable. */ }
}

export default function(component) {
  const { data, parentElement, setTriggerValue } = component;
  const root=parentElement.querySelector(".pulse-hero"); if(!root) return;
  let state=heroInstances.get(root);
  if(!state) { state={destroyed:false,cleanup:null}; heroInstances.set(root,state); startHeroScene(root,state); }
  const button=root.querySelector(".refresh-button"); button.disabled=!data?.ready;
  button.onclick=()=>{ if(data?.ready) setTriggerValue("refresh", true); };
  return ()=>{state.destroyed=true;state.cleanup?.();heroInstances.delete(root);};
}
"""


_STOCK_PULSE_HERO = st.components.v2.component(
    "threejs_stock_pulse_hero",
    html=_HERO_HTML,
    css=_HERO_CSS,
    js=_HERO_JS,
)


_DAY_TRADE_PICKER_HTML = """
<section class="day-trade-picker" aria-label="เลือกหุ้น Day Trade">
  <div class="picker-title">เลือกหุ้น Day Trade</div>
  <div class="picker-subtitle">รายการนี้บันทึกอัตโนมัติไว้ในเครื่องนี้</div>
  <div class="selected-symbols"></div>
  <input class="picker-search" type="search" autocomplete="off" placeholder="พิมพ์ค้นหา ticker หรือชื่อบริษัท" aria-label="ค้นหาหุ้น Day Trade">
  <div class="picker-suggestions"></div>
</section>
"""


_DAY_TRADE_PICKER_CSS = """
:host { display:block; width:100%; }
.day-trade-picker { padding:16px; border:1px solid var(--st-border-color,#d8e2ec); border-radius:18px; background:var(--st-secondary-background-color,#f1f5f9); color:var(--st-text-color,#122033); font-family:var(--st-font,Inter,sans-serif); }
.picker-title { font-weight:800; font-size:15px; }.picker-subtitle { margin-top:4px; color:var(--st-secondary-text-color,#64748b); font-size:12px; }
.selected-symbols { display:flex; flex-wrap:wrap; gap:6px; margin:12px 0 10px; min-height:24px; }
.selected-chip { display:inline-flex; align-items:center; gap:6px; padding:6px 9px; border-radius:999px; color:#0f3d3a; background:#ccfbf1; font-size:12px; font-weight:800; }.selected-chip button { border:0; padding:0; cursor:pointer; color:#0f766e; background:transparent; font-size:15px; line-height:1; }
.picker-search { width:100%; box-sizing:border-box; padding:10px 12px; border:1px solid var(--st-border-color,#cbd5e1); border-radius:12px; outline:none; color:var(--st-text-color,#122033); background:var(--st-background-color,#fff); font:500 13px var(--st-font,Inter,sans-serif); }.picker-search:focus { border-color:var(--st-primary-color,#0f766e); box-shadow:0 0 0 3px rgba(20,184,166,.14); }
.picker-suggestions { display:grid; gap:5px; margin-top:8px; max-height:132px; overflow:auto; }.suggestion { display:flex; justify-content:space-between; gap:8px; width:100%; padding:9px 10px; border:1px solid transparent; border-radius:10px; cursor:pointer; text-align:left; color:var(--st-text-color,#122033); background:var(--st-background-color,#fff); font:600 12px var(--st-font,Inter,sans-serif); }.suggestion:hover { border-color:var(--st-primary-color,#0f766e); }.suggestion small { color:var(--st-secondary-text-color,#64748b); font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.picker-empty { padding:9px 10px; color:var(--st-secondary-text-color,#64748b); font-size:12px; }
"""


_DAY_TRADE_PICKER_JS = """
const dayTradePickerInstances = new WeakMap();
const dayTradeStorageKey = "us-stock-scanner:day-trade-symbols";

function normaliseSymbols(values) {
  return [...new Set((values || []).map(value => String(value).trim().toUpperCase()).filter(Boolean))];
}

export default function(component) {
  const { data, parentElement, setStateValue } = component;
  const root = parentElement.querySelector(".day-trade-picker");
  if (!root) return;
  let state = dayTradePickerInstances.get(root);
  const options = data?.options || [];
  const optionMap = new Map(options.map(item => [String(item.symbol).toUpperCase(), item]));
  if (!state) {
    state = { selected: normaliseSymbols(data?.selected), query: "" };
    try {
      const saved = JSON.parse(localStorage.getItem(dayTradeStorageKey) || "null");
      if (Array.isArray(saved)) state.selected = normaliseSymbols(saved);
    } catch (_) { /* Use the server-provided default when storage is unavailable. */ }
    state.selected = normaliseSymbols(state.selected);
    dayTradePickerInstances.set(root, state);
  }
  const chips = root.querySelector(".selected-symbols");
  const input = root.querySelector(".picker-search");
  const suggestions = root.querySelector(".picker-suggestions");
  const emit = () => {
    try { localStorage.setItem(dayTradeStorageKey, JSON.stringify(state.selected)); } catch (_) {}
    setStateValue("symbols", state.selected);
    render();
  };
  const toggle = symbol => {
    state.selected = state.selected.includes(symbol)
      ? state.selected.filter(item => item !== symbol)
      : [...state.selected, symbol];
    emit();
  };
  const render = () => {
    chips.replaceChildren();
    state.selected.forEach(symbol => {
      const chip = document.createElement("span"); chip.className = "selected-chip";
      const label = document.createElement("span"); label.textContent = symbol;
      const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "×"; remove.setAttribute("aria-label", `ลบ ${symbol}`); remove.onclick = () => toggle(symbol);
      chip.append(label, remove); chips.appendChild(chip);
    });
    input.value = state.query;
    const query = state.query.toLowerCase().trim();
    const matches = options.filter(item => {
      const symbol = String(item.symbol || "").toLowerCase();
      const name = String(item.name || "").toLowerCase();
      return !query || symbol.includes(query) || name.includes(query);
    }).slice(0, 12);
    suggestions.replaceChildren();
    if (!matches.length) {
      const empty = document.createElement("div"); empty.className = "picker-empty"; empty.textContent = "ไม่พบหุ้นที่ค้นหา"; suggestions.appendChild(empty);
    } else {
      matches.forEach(item => {
        const symbol = String(item.symbol).toUpperCase();
        const button = document.createElement("button"); button.type = "button"; button.className = "suggestion";
        const ticker = document.createElement("strong"); ticker.textContent = state.selected.includes(symbol) ? `✓ ${symbol}` : symbol;
        const company = document.createElement("small"); company.textContent = item.name || "";
        button.append(ticker, company); button.onclick = () => toggle(symbol); suggestions.appendChild(button);
      });
    }
  };
  input.oninput = event => { state.query = event.target.value; render(); };
  input.onkeydown = event => {
    if (event.key !== "Enter") return;
    const custom = state.query.trim().toUpperCase();
    if (/^[A-Z0-9.]{1,10}$/.test(custom) && !optionMap.has(custom)) { state.query = ""; toggle(custom); }
  };
  render();
}
"""


_DAY_TRADE_PICKER = st.components.v2.component(
    "day_trade_local_picker_v1",
    html=_DAY_TRADE_PICKER_HTML,
    css=_DAY_TRADE_PICKER_CSS,
    js=_DAY_TRADE_PICKER_JS,
)


def day_trade_picker(options: list[dict[str, str]], default: tuple[str, ...], *, key: str) -> tuple[str, ...]:
    """Render a browser-local Day Trade picker and return its selected symbols."""
    component_state = st.session_state.get(key, {})
    current = component_state.get("symbols", default) if isinstance(component_state, dict) else default
    result = _DAY_TRADE_PICKER(
        data={"options": options, "selected": list(current)},
        key=key,
        default={"symbols": list(current)},
        on_symbols_change=lambda: None,
        width="stretch",
        height=190,
    )
    selected = getattr(result, "symbols", None)
    if not isinstance(selected, (list, tuple)):
        selected = current
    return tuple(dict.fromkeys(str(symbol).strip().upper() for symbol in selected if str(symbol).strip()))


def stock_card_deck(items: list[dict[str, Any]], *, key: str) -> Any:
    """Render an accessible swipe deck; the selected card index persists per session."""
    component_state = st.session_state.get(key, {})
    current_index = component_state.get("index", 0) if isinstance(component_state, dict) else 0
    return _STOCK_CARD_DECK(
        data={"items": items, "index": current_index},
        key=key,
        default={"index": current_index},
        on_index_change=lambda: None,
        width="stretch",
        height=540,
    )


def stock_pulse_hero(*, ready: bool, key: str = "stock-pulse-hero") -> bool:
    """Render the app-wide Three.js hero and return whether refresh was requested."""
    result = _STOCK_PULSE_HERO(
        data={"ready": ready},
        key=key,
        on_refresh_change=lambda: None,
        width="stretch",
        height=190,
    )
    return bool(getattr(result, "refresh", False))
