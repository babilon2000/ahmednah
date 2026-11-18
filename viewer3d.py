"""
viewer3d.py
-----------
عارض ثلاثي الأبعاد مبني على Three.js، يُعرض داخل Streamlit عبر components.html.

Streamlit (بايثون) يملك "حالة المشهد": قائمة المجسمات وأبعادها ومواقعها.
في كل تحديث نرسل هذه الحالة كـ JSON إلى صفحة HTML صغيرة، وهي تبني المشهد بـ Three.js.
موقع الكاميرا يُحفظ في المتصفح (localStorage) حتى لا يقفز العرض عند كل تعديل.

المرحلة 1: الأشكال الأساسية + ملفات OBJ / GLB / GLTF / STL + التحكم بالماوس.
المرحلة 2: الخامات (ألوان، خشونة، معدنية، شفافية، صور، Normal Map، مكتبة جاهزة) + عناصر الموقع.
"""

from __future__ import annotations

import json

import streamlit as st

THREE_VERSION = "0.170.0"
CDN = f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}"

_HTML = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<style>
  html, body { margin:0; height:100%; overflow:hidden; background:#f4f1ec;
               font-family: "Segoe UI", Tahoma, sans-serif; }
  #wrap { position:relative; width:100%; height:100%; }
  canvas { display:block; }
  #bar { position:absolute; top:10px; left:10px; display:flex; gap:6px; z-index:5; direction:rtl; }
  #bar button { border:1px solid #d8d2c8; background:#fff; border-radius:8px; padding:6px 10px;
                font-size:13px; cursor:pointer; color:#1f2a37; }
  #bar button:hover { background:#fbeee9; border-color:#c8553d; }
  #msg { position:absolute; inset:0; display:none; align-items:center; justify-content:center;
         text-align:center; padding:24px; color:#7a271a; background:#fff5f2; font-size:15px; z-index:9; }
  #hint { position:absolute; bottom:8px; right:12px; font-size:12px; color:#6b7280; direction:rtl;
          background:rgba(255,255,255,.75); padding:3px 8px; border-radius:6px; }
  #info { position:absolute; top:10px; right:12px; font-size:12px; color:#374151; direction:rtl;
          background:rgba(255,255,255,.85); padding:5px 9px; border-radius:6px; }
</style>
<script type="importmap">
{ "imports": { "three": "__CDN__/build/three.module.js",
               "three/addons/": "__CDN__/examples/jsm/" } }
</script>
</head>
<body>
<div id="wrap">
  <div id="bar">
    <button id="fit" title="إظهار كل المجسمات">⤢ ملاءمة العرض</button>
    <button id="top" title="منظر علوي">⬒ علوي</button>
    <button id="iso" title="منظر منظوري">◩ منظوري</button>
    <button id="grid" title="إظهار/إخفاء الشبكة">▦ الشبكة</button>
  </div>
  <div id="info"></div>
  <div id="hint">يسار: تدوير · يمين: تحريك · العجلة: تكبير</div>
  <div id="msg"></div>
</div>

<script id="scene-data" type="application/json">__DATA__</script>
<script type="module">
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const DATA = JSON.parse(document.getElementById("scene-data").textContent);
const CAM_KEY = "ahmednah3d_camera";
const IDS_KEY = "ahmednah3d_ids";
const store = {  // localStorage قد لا يكون متاحاً في بعض المتصفحات
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
};

const wrap = document.getElementById("wrap");
const info = document.getElementById("info");

// ---------- المشهد والكاميرا والتحكم ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(wrap.clientWidth, wrap.clientHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
wrap.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf4f1ec);

const camera = new THREE.PerspectiveCamera(45, wrap.clientWidth / wrap.clientHeight, 0.01, 5000);
camera.position.set(6, 5, 8);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.screenSpacePanning = true;

// بيئة انعكاس مدمجة (بدون ملفات خارجية): تعطي المعدن والزجاج انعكاسات واقعية
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.55;

// إضاءة مؤقتة بسيطة (إعدادات الإضاءة الكاملة في المرحلة 3)
scene.add(new THREE.HemisphereLight(0xffffff, 0x8d8a85, 1.0));
const sun = new THREE.DirectionalLight(0xffffff, 1.6);
sun.position.set(5, 10, 7);
scene.add(sun);

const grid = new THREE.GridHelper(20, 20, 0x9a948a, 0xd8d2c8);
grid.position.y = -0.02;   // تحت الطرق والعشب قليلاً حتى لا تظهر خطوطها فوقها
scene.add(grid);
const axes = new THREE.AxesHelper(1.2);
axes.position.y = 0.001;
scene.add(axes);

// ---------- بناء المجسمات ----------
const deg = THREE.MathUtils.degToRad;
const root = new THREE.Group();
scene.add(root);
const byId = {};

function applyTransform(obj, o) {
  obj.position.set(o.px, o.py, o.pz);
  obj.rotation.set(deg(o.rx), deg(o.ry), deg(o.rz));
  const s = o.scale ?? 1;
  obj.scale.set(s, s, s);
}

// ---------- الخامات (المرحلة 2) ----------
// مولّد أرقام عشوائية ثابت: نفس الخامة تُرسم بنفس الشكل في كل مرة
function rng(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// خامات جاهزة تُرسم برمجياً على Canvas (بدون أي صور خارجية)
const TEX = {};
function canvasTex(kind) {
  if (TEX[kind]) return TEX[kind];
  const S = 512, c = document.createElement("canvas");
  c.width = c.height = S;
  const g = c.getContext("2d");
  const r = rng(kind.length * 977 + kind.charCodeAt(0));
  if (kind === "wood") {
    g.fillStyle = "#a8733f"; g.fillRect(0, 0, S, S);
    for (let i = 0; i < 90; i++) {
      const y = r() * S, amp = 2 + r() * 8, f = 40 + r() * 80;
      g.strokeStyle = `rgba(${60 + r() * 50 | 0},${32 + r() * 25 | 0},${14 + r() * 14 | 0},${0.18 + r() * 0.4})`;
      g.lineWidth = 0.6 + r() * 3.5;
      g.beginPath(); g.moveTo(0, y);
      for (let x = 0; x <= S; x += 16) g.lineTo(x, y + Math.sin(x / f + i) * amp);
      g.stroke();
    }
  } else if (kind === "marble") {
    g.fillStyle = "#f3f1ec"; g.fillRect(0, 0, S, S);
    g.shadowColor = "rgba(90,90,100,0.5)"; g.shadowBlur = 6;
    for (let i = 0; i < 16; i++) {
      let x = r() * S, y = r() * S;
      g.strokeStyle = `rgba(${80 + r() * 40 | 0},${80 + r() * 40 | 0},${92 + r() * 40 | 0},${0.45 + r() * 0.4})`;
      g.lineWidth = 0.6 + r() * 2.2;
      g.beginPath(); g.moveTo(x, y);
      for (let k = 0; k < 40; k++) { x += (r() - 0.35) * 30; y += (r() - 0.5) * 30; g.lineTo(x, y); }
      g.stroke();
    }
  } else if (kind === "metal") {
    g.fillStyle = "#b4b8be"; g.fillRect(0, 0, S, S);
    for (let i = 0; i < 1400; i++) {
      const v = r() > 0.5 ? 255 : 0;
      g.strokeStyle = `rgba(${v},${v},${v},${0.03 + r() * 0.09})`;
      g.lineWidth = 0.5 + r();
      const y = r() * S, x = r() * S;
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + 40 + r() * 200, y); g.stroke();
    }
  } else if (kind === "fabric") {
    g.fillStyle = "#7a8aa3"; g.fillRect(0, 0, S, S);
    const st = 8;
    for (let y = 0; y < S; y += st) for (let x = 0; x < S; x += st) {
      const odd = ((x + y) / st) % 2;
      g.fillStyle = odd ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.12)";
      g.fillRect(x, y, odd ? st : st / 2, odd ? st / 2 : st);
    }
    for (let i = 0; i < 2500; i++) {
      g.fillStyle = `rgba(255,255,255,${r() * 0.06})`;
      g.fillRect(r() * S, r() * S, 1, 1);
    }
  } else if (kind === "asphalt") {
    g.fillStyle = "#3d3f43"; g.fillRect(0, 0, S, S);
    for (let i = 0; i < 14000; i++) {
      const v = 40 + r() * 70 | 0;
      g.fillStyle = `rgba(${v},${v},${v + 4},${0.5 + r() * 0.5})`;
      g.fillRect(r() * S, r() * S, 1 + r() * 2, 1 + r() * 2);
    }
  } else if (kind === "grass") {
    g.fillStyle = "#4e8a37"; g.fillRect(0, 0, S, S);
    for (let i = 0; i < 16000; i++) {
      const x = r() * S, y = r() * S;
      g.strokeStyle = `rgba(${40 + r() * 60 | 0},${100 + r() * 80 | 0},${25 + r() * 35 | 0},${0.5 + r() * 0.5})`;
      g.lineWidth = 1;
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + (r() - 0.5) * 3, y - 2 - r() * 5); g.stroke();
    }
  } else if (kind === "paving") {
    g.fillStyle = "#c9c4ba"; g.fillRect(0, 0, S, S);
    g.strokeStyle = "rgba(110,105,95,0.6)"; g.lineWidth = 3;
    for (let k = 0; k <= S; k += S / 4) {
      g.beginPath(); g.moveTo(0, k); g.lineTo(S, k); g.stroke();
      g.beginPath(); g.moveTo(k, 0); g.lineTo(k, S); g.stroke();
    }
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  TEX[kind] = t;
  return t;
}

function tiled(tex, rx, ry) {
  const t = tex.clone();
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(rx, ry ?? rx);
  t.needsUpdate = true;
  return t;
}

const texLoader = new THREE.TextureLoader();
const PRESET_TEX = { wood: "wood", marble: "marble", metal: "metal", fabric: "fabric" };

function makeMaterial(o) {
  const m = o.mat || {};
  const opacity = m.opacity ?? 1;
  const mat = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(m.color || o.color || "#c8553d"),
    roughness: m.roughness ?? 0.55,
    metalness: m.metalness ?? 0.05,
    transparent: opacity < 1,
    opacity,
    side: o.type === "plane" ? THREE.DoubleSide : THREE.FrontSide,
  });
  if (opacity < 1) mat.depthWrite = false;
  if (m.preset === "glass") { mat.clearcoat = 1; mat.clearcoatRoughness = 0.03; mat.ior = 1.5; }
  const rep = m.repeat || 1;
  let map = null;
  if (m.tex) map = texLoader.load(m.tex);
  else if (PRESET_TEX[m.preset]) map = canvasTex(PRESET_TEX[m.preset]).clone();
  if (map) {
    map.wrapS = map.wrapT = THREE.RepeatWrapping;
    map.repeat.set(rep, rep);
    map.colorSpace = THREE.SRGBColorSpace;
    map.anisotropy = 8;
    map.needsUpdate = true;
    mat.map = map;
  }
  if (m.normal) {
    const n = texLoader.load(m.normal);
    n.wrapS = n.wrapT = THREE.RepeatWrapping;
    n.repeat.set(rep, rep);
    mat.normalMap = n;
    const k = m.normal_strength ?? 1;
    mat.normalScale.set(k, k);
  }
  return mat;
}

function primitive(o) {
  let g;
  if (o.type === "box") g = new THREE.BoxGeometry(o.w, o.h, o.d);
  else if (o.type === "sphere") g = new THREE.SphereGeometry(o.r, 48, 32);
  else if (o.type === "cylinder") g = new THREE.CylinderGeometry(o.rt, o.rb, o.h, 48);
  else if (o.type === "plane") { g = new THREE.PlaneGeometry(o.w, o.d); g.rotateX(-Math.PI / 2); }
  const m = new THREE.Mesh(g, makeMaterial(o));
  const holder = new THREE.Group();
  holder.add(m);
  return holder;
}

// ---------- عناصر الموقع (المرحلة 2): أشخاص، سيارات، نباتات، طرق ----------
const SKIN = 0xc9a27e;
function part(geo, color, extra) {
  return new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color, roughness: 0.75, ...(extra || {}) }));
}
function capsule(r, total) {   // كبسولة بطولها الكلي (وليس الجزء الأوسط فقط)
  return new THREE.CapsuleGeometry(r, Math.max(total - 2 * r, 0.001), 6, 14);
}

// شخص مبسّط بأسلوب المجسمات المعمارية. الواجهة نحو +X والكتفان على محور Z
function person(kind, color) {
  const g = new THREE.Group();
  const cloth = new THREE.Color(color);
  const H = kind === "man" ? 1.78 : kind === "woman" ? 1.65 : 1.15;
  const headR = kind === "child" ? 0.105 : 0.1;
  const legH = H * (kind === "child" ? 0.42 : 0.47);
  const torsoH = H * 0.30;
  const sw = kind === "man" ? 0.2 : kind === "woman" ? 0.17 : 0.13;  // نصف عرض الكتفين
  const trousers = new THREE.Color(0x3b4252);

  if (kind === "woman") {
    const skirtH = legH * 0.62;
    const dress = part(new THREE.CylinderGeometry(sw * 0.85, sw * 1.35, skirtH, 28), cloth);
    dress.position.y = legH - skirtH / 2;
    g.add(dress);
    for (const s of [-1, 1]) {
      const l = part(capsule(0.045, legH - skirtH + 0.05), trousers);
      l.position.set(0, (legH - skirtH) / 2, s * 0.07);
      g.add(l);
    }
  } else {
    for (const s of [-1, 1]) {
      const l = part(capsule(sw * 0.32, legH), kind === "child" ? cloth.clone().offsetHSL(0, 0, -0.2) : trousers);
      l.position.set(0, legH / 2, s * sw * 0.45);
      g.add(l);
    }
  }
  const torso = part(capsule(sw * 0.8, torsoH + sw * 0.4), cloth);
  torso.scale.set(0.6, 1, 1);
  torso.position.y = legH + torsoH / 2;
  g.add(torso);
  const armL = H * 0.33;
  for (const s of [-1, 1]) {
    const a = part(capsule(0.04 * (H / 1.7), armL), cloth);
    a.position.set(0, legH + torsoH + sw * 0.1 - armL / 2, s * (sw * 0.8 + 0.05));
    a.rotation.x = s * 0.06;
    g.add(a);
  }
  const head = part(new THREE.SphereGeometry(headR, 24, 18), SKIN);
  head.position.y = legH + torsoH + sw * 0.3 + headR;
  g.add(head);
  return g;
}

// سيارة سيدان مبسّطة: الطول على محور X
function car(color) {
  const g = new THREE.Group();
  const paint = new THREE.MeshPhysicalMaterial({ color, metalness: 0.5, roughness: 0.32, clearcoat: 1, clearcoatRoughness: 0.08 });
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x1d2733, metalness: 0.2, roughness: 0.05, clearcoat: 1 });
  const body = new THREE.Mesh(new THREE.BoxGeometry(4.4, 0.62, 1.8), paint);
  body.position.y = 0.62; g.add(body);
  const cabin = new THREE.Mesh(new THREE.BoxGeometry(2.3, 0.52, 1.6), glass);
  cabin.position.set(-0.25, 1.19, 0); g.add(cabin);
  const roof = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.06, 1.55), paint);
  roof.position.set(-0.3, 1.47, 0); g.add(roof);
  const tyre = new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.9 });
  const rim = new THREE.MeshStandardMaterial({ color: 0xb8bcc2, metalness: 0.8, roughness: 0.3 });
  for (const x of [-1.4, 1.4]) for (const z of [-0.82, 0.82]) {
    const w = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.24, 28), tyre);
    w.rotation.x = Math.PI / 2; w.position.set(x, 0.34, z); g.add(w);
    const h = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.26, 20), rim);
    h.rotation.x = Math.PI / 2; h.position.set(x, 0.34, z); g.add(h);
  }
  for (const z of [-0.6, 0.6]) {
    const f = part(new THREE.BoxGeometry(0.05, 0.12, 0.35), 0xfff6d5, { emissive: 0xfff2c0, emissiveIntensity: 0.4 });
    f.position.set(2.2, 0.72, z); g.add(f);
    const b = part(new THREE.BoxGeometry(0.05, 0.12, 0.35), 0xb3261e, { emissive: 0x7a120c, emissiveIntensity: 0.4 });
    b.position.set(-2.2, 0.72, z); g.add(b);
  }
  return g;
}

function tree(h, color) {
  const g = new THREE.Group();
  const trunkH = h * 0.42;
  const trunk = part(new THREE.CylinderGeometry(h * 0.025, h * 0.035, trunkH, 12), 0x6b4a2f);
  trunk.position.y = trunkH / 2; g.add(trunk);
  const leaf = new THREE.MeshStandardMaterial({ color, roughness: 0.85, flatShading: true });
  const r = h * 0.26;
  const blobs = [[0, trunkH + r * 0.8, 0, 1], [r * 0.45, trunkH + r * 0.5, r * 0.2, 0.7],
                 [-r * 0.4, trunkH + r * 0.6, -r * 0.25, 0.72], [0, trunkH + r * 1.35, 0, 0.6]];
  for (const [x, y, z, k] of blobs) {
    const b = new THREE.Mesh(new THREE.IcosahedronGeometry(r * k, 1), leaf);
    b.position.set(x, y, z); g.add(b);
  }
  return g;
}

function bush(color) {
  const g = new THREE.Group();
  const leaf = new THREE.MeshStandardMaterial({ color, roughness: 0.9, flatShading: true });
  for (const [x, z, r] of [[0, 0, 0.45], [0.4, 0.15, 0.33], [-0.35, -0.1, 0.36], [0.05, -0.35, 0.3]]) {
    const b = new THREE.Mesh(new THREE.IcosahedronGeometry(r, 1), leaf);
    b.position.set(x, r * 0.8, z); g.add(b);
  }
  return g;
}

function flat(w, d, kind, rep, y) {   // سطح أفقي بخامة جاهزة
  const m = new THREE.MeshStandardMaterial({ map: tiled(canvasTex(kind), rep[0], rep[1]), roughness: 0.95 });
  const p = new THREE.Mesh(new THREE.PlaneGeometry(w, d), m);
  p.rotation.x = -Math.PI / 2; p.position.y = y;
  return p;
}

function grass(w, d) {   // داخل مجموعة حتى لا يلغي الدورانُ الذي يختاره المستخدم وضعَه الأفقي
  const g = new THREE.Group();
  g.add(flat(w, d, "grass", [Math.max(w / 3, 1), Math.max(d / 3, 1)], 0.006));
  return g;
}

// طريق: الطول على محور X، مع خط وسط متقطع وخطوط جانبية، وأرصفة اختيارية
function road(L, W, sidewalk) {
  const g = new THREE.Group();
  g.add(flat(L, W, "asphalt", [Math.max(L / 6, 1), Math.max(W / 6, 1)], 0.01));
  const paint = new THREE.MeshStandardMaterial({ color: 0xf2f2ee, roughness: 0.6 });
  for (let x = -L / 2 + 1.5; x < L / 2 - 1.5; x += 6) {
    const dash = new THREE.Mesh(new THREE.PlaneGeometry(3, 0.15), paint);
    dash.rotation.x = -Math.PI / 2; dash.position.set(x + 1.5, 0.014, 0); g.add(dash);
  }
  for (const s of [-1, 1]) {
    const edge = new THREE.Mesh(new THREE.PlaneGeometry(L, 0.12), paint);
    edge.rotation.x = -Math.PI / 2; edge.position.set(0, 0.014, s * (W / 2 - 0.3)); g.add(edge);
    if (sidewalk) {
      const sw = new THREE.Mesh(new THREE.BoxGeometry(L, 0.15, 2),
        new THREE.MeshStandardMaterial({ map: tiled(canvasTex("paving"), L / 2, 1), roughness: 0.9 }));
      sw.position.set(0, 0.075, s * (W / 2 + 1)); g.add(sw);
    }
  }
  return g;
}

function entourage(o) {
  const k = o.kind;
  if (k === "man" || k === "woman" || k === "child") return person(k, o.color);
  if (k === "car") return car(o.color);
  if (k === "tree") return tree(o.h, o.color);
  if (k === "bush") return bush(o.color);
  if (k === "grass") return grass(o.w, o.d);
  if (k === "road") return road(o.l, o.w, o.sidewalk);
  throw new Error("عنصر غير معروف: " + k);
}

function b64ToBuffer(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

function loadModel(o) {
  return new Promise((resolve, reject) => {
    const buf = b64ToBuffer(o.data);
    const fallback = new THREE.MeshStandardMaterial({ color: 0xb8b2a7, roughness: 0.6 });
    try {
      if (o.fmt === "glb" || o.fmt === "gltf") {
        new GLTFLoader().parse(buf, "", (gltf) => resolve(gltf.scene), reject);
      } else if (o.fmt === "obj") {
        const grp = new OBJLoader().parse(new TextDecoder().decode(buf));
        grp.traverse((c) => { if (c.isMesh && !c.material?.map) c.material = fallback; });
        resolve(grp);
      } else if (o.fmt === "stl") {
        const geo = new STLLoader().parse(buf);
        geo.computeVertexNormals();
        resolve(new THREE.Mesh(geo, fallback));
      } else reject(new Error("صيغة غير مدعومة: " + o.fmt));
    } catch (e) { reject(e); }
  });
}

async function build() {
  const errors = [];
  for (const o of DATA.objects) {
    try {
      let obj;
      if (o.type === "model") {
        const inner = await loadModel(o);
        // نجعل نقطة الارتكاز في منتصف قاعدة المجسم: يجلس على الأرض بدل أن يغوص فيها
        const b = new THREE.Box3().setFromObject(inner);
        if (!b.isEmpty()) {
          const c = b.getCenter(new THREE.Vector3());
          inner.position.set(-c.x, -b.min.y, -c.z);
        }
        if (o.override && o.mat) {      // استبدال خامات الملف بخامة من اختيارنا
          const mm = makeMaterial(o);
          inner.traverse((c) => { if (c.isMesh) c.material = mm; });
        }
        obj = new THREE.Group();
        obj.add(inner);
      } else if (o.type === "ent") obj = entourage(o);
      else obj = primitive(o);
      applyTransform(obj, o);
      obj.userData.id = o.id;
      root.add(obj);
      byId[o.id] = obj;
    } catch (e) {
      console.error(e);
      errors.push(o.name + ": " + (e.message || e));
    }
  }
  if (errors.length) {
    info.textContent = "⚠️ تعذّر تحميل: " + errors.join(" | ");
    info.style.color = "#b42318";
  } else {
    info.textContent = DATA.objects.length ? `المجسمات: ${DATA.objects.length}` : "المشهد فارغ — أضف شكلاً من القائمة الجانبية";
  }

  // إطار حول المجسم المحدد
  const sel = byId[DATA.selected];
  if (sel) {
    const box = new THREE.BoxHelper(sel, 0xe8a317);
    scene.add(box);
  }
}

// ---------- الكاميرا: الملاءمة والحفظ ----------
function sceneBox() {
  const box = new THREE.Box3().setFromObject(root);
  if (box.isEmpty()) box.set(new THREE.Vector3(-2, 0, -2), new THREE.Vector3(2, 2, 2));
  return box;
}

function fit(direction) {
  const box = sceneBox();
  const size = box.getSize(new THREE.Vector3()).length() || 4;
  const center = box.getCenter(new THREE.Vector3());
  const dir = (direction || new THREE.Vector3(0.6, 0.5, 0.8)).clone().normalize();
  const dist = size / (2 * Math.tan(deg(camera.fov / 2))) * 1.15;
  camera.position.copy(center).addScaledVector(dir, dist);
  camera.near = Math.max(dist / 1000, 0.001);
  camera.far = dist * 100;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
  saveCam();
}

function saveCam() {
  store.set(CAM_KEY, { p: camera.position.toArray(), t: controls.target.toArray() });
}

controls.addEventListener("end", saveCam);
document.getElementById("fit").onclick = () => fit();
document.getElementById("top").onclick = () => fit(new THREE.Vector3(0, 1, 0.0001));
document.getElementById("iso").onclick = () => fit(new THREE.Vector3(1, 0.8, 1));
document.getElementById("grid").onclick = () => { grid.visible = !grid.visible; axes.visible = grid.visible; };

function onResize() {
  const w = wrap.clientWidth, h = wrap.clientHeight;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener("resize", onResize);

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

build().then(() => {
  // نعيد الكاميرا لآخر موقع، إلا إذا أُضيف ملف ثلاثي الأبعاد جديد فنلائم العرض عليه
  const ids = DATA.objects.map((o) => o.id);
  const oldIds = store.get(IDS_KEY) || [];
  const newModel = DATA.objects.some((o) => o.type === "model" && !oldIds.includes(o.id));
  store.set(IDS_KEY, ids);
  const cam = store.get(CAM_KEY);
  if (cam && !newModel) {
    camera.position.fromArray(cam.p);
    controls.target.fromArray(cam.t);
    controls.update();
  } else fit();
  window.__ready = true;
});
animate();
</script>
<script>
  // إن فشل تحميل Three.js (انقطاع الإنترنت أو حجب الموقع) نعرض رسالة واضحة
  setTimeout(() => {
    if (!window.__ready) {
      const m = document.getElementById("msg");
      m.style.display = "flex";
      m.textContent = "تعذّر تحميل محرك العرض ثلاثي الأبعاد. تأكد من الاتصال بالإنترنت ثم أعد تحميل الصفحة.";
    }
  }, 15000);
</script>
</body>
</html>
"""


def render_viewer(objects: list[dict], selected: str | None = None, height: int = 620,
                  cdn: str = CDN) -> None:
    """يعرض المشهد. objects: قائمة المجسمات كما في session_state."""
    html = build_html(objects, selected, cdn)
    if hasattr(st, "iframe"):            # Streamlit الحديث
        st.iframe(html, height=height)
    else:                                # إصدارات أقدم
        import streamlit.components.v1 as components
        components.html(html, height=height, scrolling=False)


def build_html(objects: list[dict], selected: str | None = None, cdn: str = CDN) -> str:
    """نفس الصفحة كنص (للاختبار)."""
    payload = json.dumps({"objects": objects, "selected": selected}, ensure_ascii=False)
    payload = payload.replace("</", "<\\/")
    return _HTML.replace("__CDN__", cdn).replace("__DATA__", payload)
