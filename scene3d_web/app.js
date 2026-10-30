// Onglet « 3D » de PANDORA — couche propre à PANDORA autour de la vue d'ARKLIGHT.
//
// La vue (Viewport), l'état d'interface (Store) et la bibliothèque (projecteurs, grip, décor)
// sont ceux d'ARKLIGHT, repris tels quels dans arklight_engine/. Ici :
//   - le pont avec Python (QWebChannel, objet « pandora ») : la scène du plan arrive de PANDORA,
//     chaque modification repart vers PANDORA, qui l'enregistre dans le projet ;
//   - l'hydratation : une scène écrite par PANDORA (projecteurs et objets « nus ») reçoit les
//     réglages par défaut de la bibliothèque d'ARKLIGHT ;
//   - l'analyse : ce que seule la bibliothèque connaît (angle du faisceau, éclairement à 1 m,
//     température de couleur, diffusion, gélatine), enregistrée avec la scène pour le prompt.
import * as THREE from 'three';
import { Store } from '/js/store.js';
import { Viewport } from '/js/viewport/viewport.js';
import { CATEGORIES, FIXTURE_TYPES, defaultSettings, defaultState, effectiveType, getFixtureType, isTraditionalType } from '/shared/fixtures/index.js';
import { defaultObjectProps, getObjectType, isProp } from '/shared/objects.js';
import { PROP_CATEGORIES, PROP_TYPES, cameraFov } from '/shared/props.js';
import { GRIP_FAMILIES, GRIP_TYPES } from '/shared/grip.js';
import { getModifier } from '/shared/modifiers.js';
import { getFilter } from '/shared/filters.js';
import { cctToRgb } from '/shared/engine/color.js';
import { Characters, cameraAngles, cameraRotation, isTripod } from '/pandora/characters.js';
// Inspecteur complet d'ARKLIGHT (30/10/2026) : réglages, menus embarqués simulés, console « Canaux »
import { mountInspector } from '/js/ui/inspector.js';
import { OnboardRegistry, createControlPanel } from '/js/ui/control-panel.js';
import { createConsoleControl } from '/js/ui/console-control.js';
import { createActions } from '/js/actions.js';
import { lang, t as translated, translatePage } from '/js/i18n.js';

const r3 = (v) => Math.round(v * 1000) / 1000;
const newId = (p) => `${p}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
const plain = (v) => v && typeof v === 'object' && !Array.isArray(v);
function deepMerge(target, patch) {
  for (const [k, v] of Object.entries(patch || {})) {
    if (plain(v) && plain(target[k])) deepMerge(target[k], v);
    else target[k] = v;
  }
  return target;
}

let bridge = null; // objet « pandora » exposé par Python
const store = new Store();
let saveTimer = null;

// ---------------------------------------------------------------- envoi vers PANDORA
/** Toute modification faite dans la vue : enregistrée par PANDORA (regroupée, 350 ms). */
function edited() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flush, 350);
}
function flush() {
  clearTimeout(saveTimer);
  saveTimer = null;
  if (!bridge || !store.scene) return;
  store.scene.pandora ||= {};
  store.scene.pandora.analysis = analyse(store.scene);
  bridge.sceneEdited(JSON.stringify(store.scene));
}
const emit = (kind, data = {}) => bridge && bridge.emitEvent(JSON.stringify({ kind, ...data }));

/** Ce que la vue d'ARKLIGHT envoie d'habitude à son serveur : appliqué ici, puis enregistré. */
const net = {
  send(msg) {
    applyMessage(msg);
    edited();
  },
  addEventListener() {},
  removeEventListener() {},
};

const poseOnly = (changes) => Object.keys(changes || {}).every((k) => k === 'position' || k === 'rotation');

function applyMessage(msg) {
  const scene = store.scene;
  if (!scene) return;
  switch (msg.t) {
    // Un déplacement fait dans la vue a déjà bougé le modèle ; un réglage (inspecteur, menus
    // embarqués, console) doit le faire reconstruire si besoin (zoom, accessoires, gélatine).
    case 'fixture.update':
      updateFixture(msg.id, msg.changes, poseOnly(msg.changes));
      break;
    case 'fixtures.update':
      for (const it of msg.items || []) updateFixture(it.id, it.changes, poseOnly(it.changes));
      break;
    case 'object.update':
      objectMoved(msg.id, msg.changes || {});
      break;
    // ---- messages des actions et de l'inspecteur d'ARKLIGHT (ce que faisait son serveur)
    case 'fixture.add':
    case 'fixtures.add': {
      const items = msg.t === 'fixture.add' ? [msg] : Array.isArray(msg.items) ? msg.items.slice(0, 256) : [];
      const added = hydrate({ fixtures: items.map(({ t, select, ...f }) => f), objects: [] }).fixtures;
      for (const f of added) store.upsertFixture(f, 'pandora');
      if (added.length && (msg.select || msg.t === 'fixture.add')) {
        store.selectObject(null);
        store.setSelection(added.map((f) => f.id));
      }
      break;
    }
    case 'fixture.remove':
      store.removeFixture(msg.id);
      break;
    case 'fixtures.remove':
      for (const id of Array.isArray(msg.ids) ? msg.ids : []) store.removeFixture(id);
      break;
    case 'object.add': {
      const { t, select, ...o } = msg;
      const added = hydrate({ fixtures: [], objects: [o] }).objects[0];
      if (added) {
        store.upsertObject(added, 'pandora');
        if (select) store.selectObject(added.id);
      }
      break;
    }
    case 'object.remove':
      for (const id of Array.isArray(msg.ids) ? msg.ids : [msg.id]) {
        store.removeObject(id);
        if (scene.pandora?.tracks?.[id]) delete scene.pandora.tracks[id];
      }
      break;
    case 'group.create': {
      const ids = (msg.ids || []).filter((id) => store.fixtures.has(id));
      if (ids.length) store.setGroups([...scene.groups, { id: newId('g'), name: String(msg.name || 'Groupe').slice(0, 40), ids }]);
      break;
    }
    case 'group.update':
      store.setGroups(scene.groups.map((g) => (g.id === msg.id ? { ...g, ...(msg.name ? { name: String(msg.name).slice(0, 40) } : {}), ...(Array.isArray(msg.ids) ? { ids: msg.ids } : {}) } : g)));
      break;
    case 'group.delete':
      store.setGroups(scene.groups.filter((g) => g.id !== msg.id));
      break;
    case 'env.update':
      store.setEnvironment({ ...scene.environment, ...(msg.changes || {}) });
      break;
    case 'dmx.forget':
      store.forgetDmx(Array.isArray(msg.universes) ? msg.universes : [msg.universe]);
      break;
    case 'plot.add':
    case 'plot.update':
      if (msg.item) store.setPlotItem({ ...msg.item, id: msg.item.id || newId('p') });
      break;
    case 'plot.remove':
      store.removePlotItem(msg.id);
      break;
    case 'plot.meta':
      store.setPlotMeta({ ...scene.plot, ...msg });
      break;
    default:
      break;
  }
}

/**
 * Un objet déplacé ou tourné à la poignée. Suivi sur la frise : cela pose (ou corrige) SA KEYFRAME au
 * temps courant, au lieu de changer sa place de départ. Caméra sur pied : monter ou descendre change
 * la hauteur de l'objectif (le pied s'allonge), et l'orientation se lit en lacet, tangage et roulis.
 */
let handleDrag = null; // { id, lens } : hauteur d'objectif au début du geste
const LENS_MIN = 0.15;
const LENS_MAX = 8;
function objectMoved(id, changes) {
  const o = store.object(id);
  if (!o) return;
  const moved = changes.position || changes.rotation;
  const tracked = tracks()[id]?.length && moved;
  const pose = {};
  const ch = { ...changes };
  if (isTripod(o) && ch.position) {
    const base = handleDrag?.id === id ? handleDrag.lens : currentLens(o);
    pose.lens = r3(Math.min(LENS_MAX, Math.max(LENS_MIN, base + Number(ch.position[1] || 0))));
    ch.position = [ch.position[0], 0, ch.position[2]];
  }
  const camera = ['camera', 'dolly'].includes(getObjectType(o.type)?.model);
  if (camera && ch.rotation) Object.assign(pose, cameraAngles(ch.rotation));
  if (tracked) {
    setMark(id, timeline.t, { p: ch.position, yaw: pose.yaw ?? ch.rotation?.[1], lens: pose.lens, pitch: pose.pitch, roll: pose.roll });
    return;
  }
  const dragging = vp.draggingObjectId === id;
  if (pose.lens !== undefined && Math.abs(pose.lens - Number(o.props?.lens || 1.45)) >= 0.005) {
    o.props = { ...(o.props || {}), lens: pose.lens };
    o.position = ch.position;
    updateObject(id, ch, true);
    if (!dragging) store.upsertObject(o, 'pandora'); // fin du geste : le pied prend sa hauteur
    return;
  }
  updateObject(id, ch, true);
  if (isTripod(o) && !dragging) vp.objects.get(id)?.model.setTransform(o.position, o.rotation); // sol
}
const currentLens = (o) => chars?.stateAt(o, timeline.t)?.lens ?? (Number(o.props?.lens) || 1.45);

/** Modifie un projecteur. fromView : la vue a déjà bougé le modèle (pas de reconstruction). */
function updateFixture(id, changes = {}, fromView = false) {
  const f = store.fixtures.get(id);
  if (!f) return;
  const { position, rotation, name, settings, state } = changes;
  if (Array.isArray(position) && position.length === 3) f.position = position.map(Number);
  if (Array.isArray(rotation) && rotation.length === 3) f.rotation = rotation.map(Number);
  if (typeof name === 'string' && name.trim()) f.name = name.trim().slice(0, 60);
  if (plain(settings)) deepMerge(f.settings, settings);
  if (plain(state)) deepMerge(f.state, state);
  if (!fromView) store.upsertFixture(f, 'pandora');
}

function updateObject(id, changes = {}, fromView = false) {
  const o = store.object(id);
  if (!o) return;
  const { position, rotation, name, props, pandora } = changes;
  if (Array.isArray(position) && position.length === 3) o.position = position.map(Number);
  if (Array.isArray(rotation) && rotation.length === 3) o.rotation = rotation.map(Number);
  if (typeof name === 'string' && name.trim()) o.name = name.trim().slice(0, 60);
  if (plain(props)) deepMerge(o.props, props);
  if (plain(pandora)) o.pandora = { ...(o.pandora || {}), ...pandora };
  if (!fromView) store.upsertObject(o, 'pandora');
}

// ---------------------------------------------------------------- hydratation
const pivot = new THREE.Object3D();
/** Orientation d'un projecteur en `from` qui vise `to` (son axe +Z pointe vers la cible). */
function aimRotation(from, to) {
  pivot.position.set(...from);
  pivot.rotation.set(0, 0, 0);
  pivot.lookAt(new THREE.Vector3(...to));
  return [r3(pivot.rotation.x), r3(pivot.rotation.y), r3(pivot.rotation.z)];
}

/** Complète une scène écrite par PANDORA avec les réglages par défaut de la bibliothèque.
 *  Un projecteur sans rotation mais avec une cible (pandora.aim) est orienté vers elle. */
export function hydrate(scene) {
  scene.version ||= 1;
  scene.environment = { floor: true, cyc: false, stands: true, labels: false, labelPatch: false, haze: 0.15, ambient: 0.05, exposure: 1, ...(scene.environment || {}) };
  scene.groups ||= [];
  scene.plot ||= { items: [], underlay: null, background: null, title: {} };
  scene.plot.items ||= [];
  scene.fixtures = (scene.fixtures || []).filter((f) => getFixtureType(f.type)).map((f) => {
    const type = getFixtureType(f.type);
    const position = (f.position || [0, 2, 3]).map(Number);
    const aim = Array.isArray(f.pandora?.aim) && f.pandora.aim.length === 3 ? f.pandora.aim.map(Number) : null;
    const out = {
      id: f.id || newId('f'),
      type: f.type,
      name: f.name || type.name,
      position,
      rotation: (f.rotation || (aim ? aimRotation(position, aim) : [0, 0, 0])).map(Number),
      settings: deepMerge(defaultSettings(type), f.settings || {}),
      state: deepMerge(defaultState(type), f.state || {}),
    };
    if (f.pandora) {
      out.pandora = { ...f.pandora };
      delete out.pandora.aim; // visée appliquée une fois : ensuite, c'est la rotation qui fait foi
    }
    return out;
  });
  scene.objects = (scene.objects || []).filter((o) => getObjectType(o.type)).map((o) => {
    const type = getObjectType(o.type);
    const out = {
      id: o.id || newId('o'),
      type: o.type,
      name: o.name || type.short || type.name,
      position: (o.position || [0, 0, 0]).map(Number),
      rotation: (o.rotation || [0, 0, 0]).map(Number),
      props: deepMerge(defaultObjectProps(type), o.props || {}),
    };
    if (o.pandora) out.pandora = o.pandora;
    return out;
  });
  scene.pandora ||= {};
  return scene;
}

// ---------------------------------------------------------------- analyse pour le prompt
/**
 * Lumière que le projecteur ÉMET VRAIMENT dans la simulation (menus embarqués, console « Canaux »,
 * mode autonome des Astera, DMX), lue dans la sortie calculée par la vue : intensité (0-1) et
 * couleur — température proche pour un blanc, teinte et saturation sinon. null : pas encore calculée.
 */
function emitted(id) {
  const entry = vp?.outputOf?.(id);
  const out = entry?.out;
  if (!out || !out.length) return null;
  const n = out.length / 3;
  let r = 0;
  let g = 0;
  let b = 0;
  for (let i = 0; i < n; i++) {
    r += out[i * 3];
    g += out[i * 3 + 1];
    b += out[i * 3 + 2];
  }
  r /= n;
  g /= n;
  b /= n;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  if (max < 0.005) return { intensity: 0, source: entry.source };
  const sat = (max - min) / max;
  let hue = 0;
  if (max !== min) {
    const d = max - min;
    hue = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    hue = (hue * 60 + 360) % 360;
  }
  const res = { intensity: Math.min(1, max), source: entry.source };
  if (sat > 0.3) return { ...res, mode: 'hsi', hue: Math.round(hue), sat: Math.round(sat * 100) / 100 };
  // blanc : température dont le rapport bleu / rouge est le plus proche
  const ratio = b / Math.max(1e-6, r);
  let best = 5600;
  let bestErr = Infinity;
  for (let k = 1800; k <= 10000; k += 100) {
    const c = cctToRgb(k);
    const err = Math.abs(c[2] / Math.max(1e-6, c[0]) - ratio);
    if (err < bestErr) {
      bestErr = err;
      best = k;
    }
  }
  return { ...res, mode: 'cct', cct: best };
}

/** Données physiques de chaque projecteur et objectif de chaque caméra (lues par core/scene3d). */
export function analyse(scene) {
  const fixtures = scene.fixtures.map((f) => {
    const type = getFixtureType(f.type);
    if (!type) return null;
    const eff = effectiveType(type, f);
    const s = f.settings || {};
    const m = f.state?.manual || {};
    const mod = s.modifier ? getModifier(s.modifier) : null;
    const g = type.geometry || {};
    // surface émettrice (m) : boîte à lumière / dôme, sinon le projecteur lui-même
    const size = mod ? (mod.d || Math.max(mod.w || 0, mod.h || 0)) : Math.max(g.diameter || 0, g.width || 0, g.height || 0, g.length || 0);
    const gel = s.gel ? getFilter(s.gel) : null;
    // Ce qui sort vraiment du projecteur prime sur son réglage manuel (menus, console, Astera)
    const em = emitted(f.id);
    const real = em && em.source !== 'manual'
      ? { power: em.intensity > 0.005 && f.state?.power !== false, intensity: em.intensity, mode: em.mode || 'cct',
          cct: em.mode === 'cct' ? em.cct : null, hue: em.mode === 'hsi' ? em.hue : null, sat: em.mode === 'hsi' ? em.sat : null }
      : null;
    return {
      id: f.id,
      name: f.name,
      type: f.type,
      brand: type.brand || '',
      model: type.name,
      category: type.category || '',
      technology: type.technology || 'led',
      beam_deg: eff.beamAngle || type.beamAngle || null,
      lux_at_1m: eff.output?.luxAt1m || null,
      size_m: r3(size || 0.2),
      modifier: mod ? mod.short || mod.name : '',
      soft: !!(mod || eff.accessories?.soft || ['tube', 'panel', 'brick'].includes(g.kind)),
      gel: gel ? gel.name : '',
      power: f.state?.power !== false,
      mode: m.mode || 'cct',
      intensity: Number(m.intensity ?? 0.6),
      cct: m.mode === 'cct' ? Number(m.cct || type.lamp?.cct || 5600) : null,
      hue: m.mode === 'hsi' ? Number(m.hue || 0) : null,
      sat: m.mode === 'hsi' ? Number(m.sat ?? 1) : null,
      ...(real ? { ...real, source: em.source } : {}),
      position: f.position,
      rotation: f.rotation,
    };
  }).filter(Boolean);
  const cameras = scene.objects.filter((o) => getObjectType(o.type)?.model === 'camera' || getObjectType(o.type)?.model === 'dolly').map((o) => {
    const fov = cameraFov(o.props);
    return { id: o.id, name: o.name, focal: Number(o.props.focal || 35), sensor: o.props.sensor || 's35', hfov_deg: r3((fov.h * 180) / Math.PI), lens_m: Number(o.props.lens || 1.45) };
  });
  // Éléments visibles à l'image (mobilier, décor, animaux, véhicules…) : le prompt les cite. Le
  // matériel de plateau et le grip n'y figurent jamais (ni caméra, ni cadre, ni drapeau).
  const objects = scene.objects.map((o) => {
    const type = getObjectType(o.type);
    if (!type || !isProp(type) || ['people', 'filmset'].includes(type.cat)) return null;
    return { id: o.id, name: o.name || type.short || type.name, category: type.cat };
  }).filter(Boolean);
  return { v: 1, fixtures, cameras, objects };
}

// ---------------------------------------------------------------- catalogue (bibliothèque)
function catalog() {
  const fixtures = FIXTURE_TYPES.filter((t) => t.geometry?.kind !== 'box-device').map((t) => ({
    id: t.id, name: t.name, brand: t.brand || '', category: t.category || '', traditional: isTraditionalType(t),
    beam_deg: t.beamAngle || null, lux_at_1m: t.output?.luxAt1m || null,
  }));
  const objects = PROP_TYPES.map((t) => ({ id: t.id, name: t.name, short: t.short, category: t.cat, model: t.model }));
  const grip = GRIP_TYPES.map((t) => ({ id: t.id, name: t.name, family: t.family || '' }));
  return {
    fixtures, objects, grip,
    fixture_categories: CATEGORIES, object_categories: PROP_CATEGORIES, grip_families: GRIP_FAMILIES,
  };
}

// ---------------------------------------------------------------- frise (mise en scène animée)
let vp = null;
let chars = null;
const timeline = { t: 0, playing: false, raf: 0, last: 0, lastEmit: 0 };
const tracks = () => store.scene?.pandora?.tracks || {};
const duration = () => Math.max(1, Number(store.scene?.pandora?.duration) || 5);

function emitTime(force = false) {
  const now = performance.now();
  if (!force && now - timeline.lastEmit < 100) return; // 10 fois par seconde au plus
  timeline.lastEmit = now;
  emit('time', { t: r3(timeline.t), playing: timeline.playing, duration: duration() });
}

function setTime(t) {
  timeline.t = Math.min(duration(), Math.max(0, Number(t) || 0));
  chars?.evaluate(timeline.t);
  emitTime(!timeline.playing);
}

function play() {
  if (timeline.playing) return;
  if (timeline.t >= duration() - 1e-3) timeline.t = 0;
  timeline.playing = true;
  timeline.last = performance.now();
  const step = (now) => {
    if (!timeline.playing) return;
    timeline.t += (now - timeline.last) / 1000;
    timeline.last = now;
    if (timeline.t >= duration()) {
      timeline.t = duration();
      timeline.playing = false;
    }
    chars?.evaluate(timeline.t);
    emitTime(!timeline.playing);
    if (timeline.playing) timeline.raf = requestAnimationFrame(step);
  };
  timeline.raf = requestAnimationFrame(step);
}

function pause() {
  timeline.playing = false;
  cancelAnimationFrame(timeline.raf);
  emitTime(true);
}

/** La place enregistrée d'un objet suivi est celle de sa première keyframe. */
function syncBase(o, marks) {
  const first = marks[0];
  o.position = first.p.slice();
  if (['camera', 'dolly'].includes(getObjectType(o.type)?.model)) {
    const a = cameraAngles(o.rotation);
    o.rotation = cameraRotation(first.yaw ?? a.yaw, first.pitch ?? a.pitch, first.roll ?? a.roll).map(r3);
    if (first.lens !== undefined && isTripod(o)) o.props = { ...(o.props || {}), lens: first.lens };
  } else o.rotation = [o.rotation?.[0] || 0, first.yaw ?? o.rotation?.[1] ?? 0, o.rotation?.[2] || 0];
}

/** Pose ou corrige la keyframe d'un objet au temps t (la première = sa place de départ). */
function setMark(id, t, { p, yaw, action, lens, pitch, roll } = {}) {
  const o = store.object(id);
  if (!o) return;
  store.scene.pandora ||= {};
  const all = (store.scene.pandora.tracks ||= {});
  const marks = (all[id] ||= []);
  // état au temps t AVANT la modification : une nouvelle keyframe ne fait pas sauter l'objet
  const st = chars.stateAt(o, t);
  const camera = st.lens !== undefined;
  const full = (x) => (camera ? { ...x, lens: r3(st.lens), pitch: r3(st.pitch || 0), roll: r3(st.roll || 0) } : x);
  if (!marks.length) marks.push(full({ t: 0, p: o.position.slice(), yaw: r3(st.yaw) }));
  let m = marks.find((x) => Math.abs(x.t - t) < 0.06);
  if (!m) {
    m = full({ t: r3(t), p: st.p.map(r3), yaw: r3(st.yaw) });
    marks.push(m);
    marks.sort((a, b) => a.t - b.t);
  }
  if (Array.isArray(p) && p.length === 3) m.p = p.map((v) => r3(Number(v)));
  if (yaw !== undefined && yaw !== null) m.yaw = r3(Number(yaw));
  if (lens !== undefined) m.lens = r3(Number(lens));
  if (pitch !== undefined) m.pitch = r3(Number(pitch));
  if (roll !== undefined) m.roll = r3(Number(roll));
  if (action !== undefined) {
    if (action) m.action = action;
    else delete m.action;
  }
  syncBase(o, marks);
  chars.evaluate(timeline.t);
  emit('track', { id, marks });
  edited();
}

function removeMark(id, t) {
  const marks = tracks()[id];
  if (!marks) return;
  const i = marks.findIndex((x) => Math.abs(x.t - t) < 0.06);
  if (i >= 0) marks.splice(i, 1);
  const o = store.object(id);
  if (!marks.length) delete store.scene.pandora.tracks[id]; // plus de keyframe : objet fixe
  else if (o) syncBase(o, marks);
  if (o) store.upsertObject(o, 'pandora'); // remet le modèle à sa place enregistrée
  chars.evaluate(timeline.t);
  emit('track', { id, marks: tracks()[id] || [] });
  edited();
}

/** Glisser une keyframe sur la frise : elle change de temps, son contenu ne change pas. */
function moveKey(id, from, to) {
  const marks = tracks()[id];
  if (!marks) return;
  const m = marks.find((x) => Math.abs(x.t - from) < 0.06);
  const dest = Math.min(duration(), Math.max(0, Number(to) || 0));
  // jamais deux keyframes au même instant : le geste est refusé, la frise se recale
  if (m && !marks.some((x) => x !== m && Math.abs(x.t - dest) < 0.06)) {
    m.t = r3(dest);
    marks.sort((a, b) => a.t - b.t);
    const o = store.object(id);
    if (o) syncBase(o, marks);
    chars.evaluate(timeline.t);
    edited();
  }
  emit('track', { id, marks });
}

/**
 * Prévisualisation : chaque image du plan, vue par la caméra du plan, envoyée à PANDORA qui
 * assemble la vidéo. Rien de sélectionné (ni poignées ni cadre), même évaluation que la lecture.
 */
async function captureFrames({ fps = 24, width = 1280, height = 720 } = {}) {
  pause();
  store.select(null);
  store.selectObject(null);
  const cam = store.scene?.pandora?.shot_camera;
  if (cam && store.object(cam) && vp.lookId !== cam) vp.lookThrough(cam);
  // Seedance ne doit voir AUCUN appareil d'éclairage : corps, lentilles et pieds des
  // projecteurs masqués (leur lumière reste). Vue de capture jetable : rien à restaurer.
  for (const entry of vp.models.values()) {
    entry.model.root.traverse((o) => {
      if (o.isMesh || o.isLine || o.isPoints || o.isSprite) o.visible = false;
    });
    if (entry.stand) entry.stand.visible = false;
    if (entry.label) entry.label.visible = false;
  }
  vp.setBloom?.(false);
  const n = Math.max(1, Math.round(duration() * fps));
  for (let i = 0; i < n; i++) {
    timeline.t = i / fps;
    chars?.evaluate(timeline.t);
    const data = vp.snapshot(width, height); // dessine l'image à l'instant puis la lit
    emit('frame', { i, n, data });
    if (i % 3 === 2) await new Promise((r) => setTimeout(r, 0)); // laisse passer les messages
  }
  emit('capture_done', { n, fps });
}

// ---------------------------------------------------------------- commandes de PANDORA

function onCommand(json) {
  let c;
  try {
    c = JSON.parse(json);
  } catch {
    return;
  }
  try {
    runCommand(c);
  } catch (e) {
    emit('error', { op: c.op, message: String(e?.message || e) });
  }
}

function runCommand(c) {
  switch (c.op) {
    case 'view':
      vp.setView(c.name);
      break;
    case 'tool':
      vp.setTool(c.mode === 'rotate' ? 'rotate' : 'translate');
      break;
    case 'snap':
      vp.setSnap(!!c.on);
      break;
    case 'look': // voir par une caméra de la scène (null : vue libre)
      vp.lookThrough(c.id || null);
      break;
    case 'select':
      if (c.id && store.fixtures.has(c.id)) {
        store.selectObject(null);
        store.select(c.id);
      } else {
        store.select(null);
        store.selectObject(c.id || null);
      }
      if (c.frame) vp.frameSelected();
      break;
    case 'add': {
      if (c.kind === 'fixture') {
        const type = getFixtureType(c.type);
        if (!type) throw new Error(`projecteur inconnu : ${c.type}`);
        const place = c.at ? vp.placementAt(type, c.at[0], c.at[1]) : c.position ? { position: c.position, rotation: c.rotation || [0, 0, 0] } : vp.suggestPlacement(type);
        const f = hydrate({ fixtures: [{ type: c.type, name: c.name, ...place }], objects: [] }).fixtures[0];
        if (c.pandora) f.pandora = c.pandora;
        store.upsertFixture(f, 'pandora'); // ajoute aussi à la scène
        store.selectObject(null);
        store.select(f.id);
      } else {
        const type = getObjectType(c.type);
        if (!type) throw new Error(`objet inconnu : ${c.type}`);
        const place = c.at ? vp.gripPlacementAt(type, c.at[0], c.at[1]) : c.position ? { position: c.position, rotation: c.rotation || [0, 0, 0] } : isProp(type) ? vp.suggestObjectPlacement(type) : vp.gripPlacementAt(type, 0, 2);
        const o = hydrate({ fixtures: [], objects: [{ type: c.type, name: c.name, props: c.props, ...place }] }).objects[0];
        if (c.pandora) o.pandora = c.pandora;
        store.upsertObject(o, 'pandora');
        store.selectObject(o.id);
      }
      edited();
      break;
    }
    case 'remove':
      if (store.fixtures.has(c.id)) store.removeFixture(c.id);
      else store.removeObject(c.id);
      edited();
      break;
    case 'update': {
      if (store.fixtures.has(c.id)) updateFixture(c.id, c.changes);
      else {
        // hauteur d'objectif d'une caméra suivie : c'est sa keyframe au temps courant
        const o = store.object(c.id);
        const lens = c.changes?.props?.lens;
        if (lens !== undefined && o && tracks()[c.id]?.length) {
          setMark(c.id, timeline.t, { lens });
          const { lens: _skip, ...rest } = c.changes.props;
          updateObject(c.id, { ...c.changes, props: rest });
          break;
        }
        updateObject(c.id, c.changes);
      }
      edited();
      break;
    }
    case 'frame.person':
      framePerson(c.id);
      break;
    case 'play.toggle':
      togglePlay();
      break;
    case 'key.delete':
      deleteKeyOrElement();
      break;
    case 'aim': // orienter les projecteurs sélectionnés vers un personnage (défaut : le premier)
      vp.aimSelectedAt(c.target || null); // passe par net.send : enregistré
      break;
    case 'env':
      store.setEnvironment({ ...store.scene.environment, ...(c.changes || {}) });
      edited();
      break;
    case 'snapshot': {
      const data = vp.snapshot(c.width || 480, c.height || 270);
      emit('snapshot', { tag: c.tag || '', data });
      break;
    }
    case 'flush':
      flush();
      break;
    // ---- frise
    case 'time':
      setTime(c.t);
      break;
    case 'play':
      play();
      break;
    case 'pause':
      pause();
      break;
    case 'mark':
      setMark(c.id, c.t ?? timeline.t, { action: c.action });
      break;
    case 'unmark':
      removeMark(c.id, c.t ?? timeline.t);
      break;
    case 'key.move':
      moveKey(c.id, c.from, c.to);
      break;
    case 'track.clear':
      if (tracks()[c.id]) {
        delete store.scene.pandora.tracks[c.id];
        const o = store.object(c.id);
        if (o) store.upsertObject(o, 'pandora');
        emit('track', { id: c.id, marks: [] });
        edited();
      }
      break;
    case 'capture':
      captureFrames(c);
      break;
    case 'tracks.set': {
      // Marques proposées par Claude chorégraphe (déjà vérifiées par PANDORA) : elles
      // remplacent celles des objets cités ; la place de départ suit la première marque.
      store.scene.pandora ||= {};
      const all = (store.scene.pandora.tracks ||= {});
      for (const [id, marks] of Object.entries(c.tracks || {})) {
        const o = store.object(id);
        if (!o) continue;
        if (!Array.isArray(marks) || marks.length < 2) {
          delete all[id];
        } else {
          all[id] = marks.map((m) => ({ t: r3(m.t), p: m.p.map((v) => r3(Number(v))), ...(m.yaw != null ? { yaw: r3(m.yaw) } : {}), ...(m.lens != null ? { lens: r3(m.lens) } : {}), ...(m.pitch != null ? { pitch: r3(m.pitch) } : {}), ...(m.roll != null ? { roll: r3(m.roll) } : {}), ...(m.action ? { action: m.action } : {}) })).sort((a, b) => a.t - b.t);
          syncBase(o, all[id]);
        }
        store.upsertObject(o, 'pandora');
        emit('track', { id, marks: all[id] || [] });
      }
      setTime(0);
      edited();
      break;
    }
    case 'duration':
      store.scene.pandora ||= {};
      store.scene.pandora.duration = Math.max(1, Number(c.d) || 5);
      setTime(Math.min(timeline.t, duration()));
      edited();
      break;
    default:
      emit('error', { op: c.op, message: 'commande inconnue' });
  }
}

const togglePlay = () => (timeline.playing ? pause() : play());

/** Suppr : la keyframe sous la tête de lecture ; sans keyframe du tout, l'élément sélectionné. */
function deleteKeyOrElement() {
  const id = store.selectedObjectId;
  if (id) {
    const marks = tracks()[id];
    if (marks?.length) {
      if (marks.some((m) => Math.abs(m.t - timeline.t) < 0.06)) removeMark(id, timeline.t);
      return; // suivi sur la frise : jamais supprimé par une touche de trop
    }
    store.removeObject(id);
    store.selectObject(null);
    edited();
  } else if (store.selected()) actionsRef?.deleteSelection();
}

/** « Cadrer le personnage » : la caméra se tourne vers le visage du premier personnage. */
function framePerson(id) {
  const o = store.object(id);
  const lens = vp.objects.get(id)?.model.lensWorld?.();
  if (!o || !lens) return;
  const aim = vp.mainAimPoint();
  const dx = aim.x - lens.position.x;
  const dz = aim.z - lens.position.z;
  const yaw = r3(Math.atan2(dx, dz));
  const pitch = r3(Math.atan2(lens.position.y - aim.y, Math.max(0.05, Math.hypot(dx, dz))));
  if (tracks()[id]?.length) return setMark(id, timeline.t, { yaw, pitch, roll: 0 });
  o.rotation = cameraRotation(yaw, pitch, 0).map(r3);
  store.upsertObject(o, 'pandora');
  edited();
}

function selectionInfo() {
  const o = store.selectedObject();
  if (o) return { kind: 'object', id: o.id, data: o, marks: tracks()[o.id] || [] };
  const f = store.selected();
  if (f) return { kind: 'fixture', id: f.id, data: f, ids: store.selectedIds() };
  return { kind: null, id: null };
}

// ---------------------------------------------------------------- inspecteur des projecteurs
/**
 * Sections de l'inspecteur d'ARKLIGHT dans l'ordre voulu par Matthieu (30/10/2026) : commandes du
 * projecteur, ses réglages, état simulé, position, puis accessoires et zoom. Le patch DMX n'a pas
 * sa place dans PANDORA. L'inspecteur reste une copie identique : seul son affichage est rangé.
 */
let actionsRef = null;
const SECTIONS = [
  ['Commandes du projecteur', 10],
  ['Réglages du projecteur', 20],
  ['État simulé', 30],
  ['Position', 40],
  ['Accessoires', 50],
  ['Zoom (bague manuelle)', 60],
  ['Patch DMX', -1],
  ['Liaison CRMX', -1],
];
function arrangeInspector(root) {
  // Bouton toujours là, tubes compris (ARKLIGHT ne le montre pas pour eux, et tout en bas sinon)
  if (store.selected() && !store.selectedObjectId && !root.querySelector(':scope > .p3-aim')) {
    const b = document.createElement('button');
    b.textContent = lang === 'fr' ? 'Cadrer le personnage' : 'Frame the character';
    b.onclick = () => vp.aimSelectedAt(null);
    const row = document.createElement('div');
    row.className = 'btn-row p3-aim';
    row.style.order = '5';
    row.append(b);
    root.append(row);
  }
  for (const g of root.querySelectorAll(':scope > .group')) {
    const title = g.querySelector('h4')?.textContent || '';
    const hit = SECTIONS.find(([fr]) => title.startsWith(fr) || title.startsWith(translated(fr)));
    const rank = hit ? hit[1] : 70;
    g.style.order = String(Math.max(rank, 0));
    g.style.display = rank < 0 ? 'none' : '';
  }
}

// ---------------------------------------------------------------- démarrage
function start(pandora) {
  bridge = pandora;
  // Flashs noirs quand la fenêtre passe à l'arrière-plan ou que la souris la quitte : Chromium peut
  // recomposer la page sans nouvelle image, et un tampon WebGL non conservé est alors noir. On le
  // conserve pour ce contexte (la vue d'ARKLIGHT reste une copie identique).
  const getContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function patched(kind, opts) {
    return getContext.call(this, kind, /^webgl/.test(kind) ? { ...(opts || {}), preserveDrawingBuffer: true } : opts);
  };
  vp = new Viewport(document.getElementById('vp'), store, net);
  // Inspecteur complet d'ARKLIGHT, monté comme dans son application (web/js/app.js) : les menus
  // embarqués simulés pilotent la lumière de la vue (vp.onboard), la console « Canaux » écrit
  // le DMX, les actions de la sélection envoient les mêmes messages que vers son serveur.
  const onboard = new OnboardRegistry({ store, net });
  vp.onboard = onboard;
  const consoleControl = createConsoleControl({ store, net, viewport: vp });
  const actions = createActions({ store, net, viewport: vp, onboard });
  actionsRef = actions;
  mountInspector({ store, net, viewport: vp, onboard, actions, control: consoleControl,
                   controlPanel: createControlPanel({ registry: onboard }) });
  // La colonne reste toujours à sa place (PANDORA pose ses propres réglages par-dessus quand ce
  // n'est pas un projecteur) : la vue 3D ne change donc jamais de taille en sélectionnant.
  const insp = document.getElementById('inspector');
  arrangeInspector(insp);
  new MutationObserver(() => arrangeInspector(insp)).observe(insp, { childList: true });
  document.addEventListener('ark:delete', () => actions.deleteSelection());
  document.addEventListener('ark:duplicate', () => actions.duplicateSelection());
  // Redimensionner un canevas WebGL l'efface : sans image redessinée aussitôt, la vue clignote en
  // noir. Cet observateur passe après celui de la vue (créé avant lui) et dessine dans la foulée.
  new ResizeObserver(() => {
    try {
      vp._frame();
    } catch { /* l'image suivante rattrapera */ }
  }).observe(document.getElementById('vp'));
  translatePage(); // anglais si PANDORA l'est (?lang=en)
  // après la vue : ses écouteurs du magasin passent avant ceux des personnages animés
  chars = new Characters(vp, store);
  chars.ready.then(() => {
    if (chars.error) emit('error', { op: 'characters', message: chars.error });
    else emit('actions', chars.catalogInfo());
  });
  window.__pandora3d = { store, vp, chars, timeline, setTime, setMark, analyse, hydrate, flush };
  const sel = () => bridge.selectionChanged(JSON.stringify(selectionInfo()));
  store.addEventListener('selection', sel);
  store.addEventListener('object-selection', sel);
  vp.addEventListener('look', (e) => emit('look', { id: e.detail }));
  // Clic droit : PANDORA ouvre son menu (ajouter ici, keyframe, cadrer, supprimer…)
  vp.addEventListener('context', (e) => {
    const p = vp._floorPoint({ clientX: e.detail.x, clientY: e.detail.y });
    emit('context', { id: e.detail.id || null, objectId: e.detail.objectId || null, at: p ? [r3(p.x), r3(p.z)] : null });
  });
  window.addEventListener('keydown', (e) => {
    if (e.repeat || e.target.closest?.('input, select, textarea, button')) return;
    if (e.code === 'Space') {
      e.preventDefault();
      togglePlay();
    } else if (e.key === 'Delete') {
      e.preventDefault();
      deleteKeyOrElement();
    }
  });
  vp.transform.addEventListener('dragging-changed', (e) => {
    const id = vp.transform.object?.userData.objectId;
    const o = id && store.object(id);
    handleDrag = e.value && o ? { id, lens: currentLens(o) } : null;
  });
  window.addEventListener('keydown', (e) => {
    // Échap : sortir de la vue caméra (comme dans ARKLIGHT)
    if (e.key === 'Escape' && vp.lookId) vp.lookThrough(null);
  });
  bridge.loadScene.connect((json) => {
    let scene;
    try {
      scene = hydrate(JSON.parse(json));
    } catch (e) {
      emit('error', { op: 'load', message: String(e?.message || e) });
      return;
    }
    pause();
    timeline.t = 0;
    if (chars) chars.t = 0;
    // Le point de vue ne dépend jamais de la scène : on ouvre en perspective, et on reste dans la
    // vue où l'on travaille (seul le bouton « Caméra » ou l'export passent par la caméra du plan).
    store.setScene(scene); // les personnages animés se recréent sur l'événement « scene »
    emit('loaded', { fixtures: scene.fixtures.length, objects: scene.objects.length, duration: duration() });
    emitTime(true);
  });
  bridge.command.connect(onCommand);
  bridge.pageReady(JSON.stringify({ catalog: catalog(), gl: !!vp.renderer?.getContext() }));
}

window.onerror = (m, s, l) => emit('error', { op: 'page', message: `${m} (${s}:${l})` });
// eslint-disable-next-line no-undef
new QWebChannel(qt.webChannelTransport, (ch) => start(ch.objects.pandora));
