// Personnages animés du Plan de feu (Matthieu 29/10/2026 : « des personnages qui marchent,
// courent, jouent, directement dans PANDORA, sans Blender »).
//
// Chaque personnage d'ARKLIGHT (objet « person-* ») reçoit un mannequin articulé de Quaternius
// (CC0, scene3d_web/characters/) accroché au « corps » du modèle d'ARKLIGHT : sélection,
// poignées et visée des projecteurs restent ceux d'ARKLIGHT ; sa silhouette d'origine devient
// invisible (toujours cliquable).
//
// Lecture DÉTERMINISTE pilotée par la tête de lecture (principe de CharacterAnimationManager.ts
// d'ArtCraft, MIT/Apache) : on ne laisse jamais le mixeur avancer seul ; à chaque évaluation
// on fixe le temps de chaque animation d'après la frise puis mixer.update(0). Défiler, lire et
// enregistrer une prévisualisation posent donc le personnage exactement de la même façon.
//
// La frise (scene.pandora.tracks[id]) donne à CHAQUE élément ses keyframes {t, p:[x,y,z], yaw,
// action} ; la caméra y ajoute lens (hauteur d'objectif, m), pitch et roll (radians, pitch > 0 :
// vers le bas). Entre deux keyframes l'élément se déplace en ligne droite ; personnages, animaux
// et véhicules se tournent dans le sens de la marche, la caméra et le décor gardent leur
// orientation (un travelling ne tourne pas l'objectif). L'action d'une keyframe vaut jusqu'à la
// suivante (sans action : marche ou course selon la vitesse, repos à l'arrêt). La cadence d'une
// marche suit la vitesse réelle du trajet.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SU from 'three/addons/utils/SkeletonUtils.js';
import { getObjectType } from '/shared/objects.js';

const FADE = 0.3; // fondu entre deux actions (s)
// Couleurs franches et distinctes : Seedance doit pouvoir dire qui est qui (« le mannequin rouge »)
const PALETTE = ['#d64545', '#3f7fe0', '#e0a92a', '#3aa76d', '#9b5de5', '#ef7d2a', '#2bb3c0', '#d4579b'];

// Squelette du volume 1 (Rigify, « DEF-… ») -> squelette du volume 2 (pelvis, spine_01…).
// GLTFLoader retire les points des noms de nœuds : « DEF-spine.001 » devient « DEF-spine001 ».
function rigMap() {
  const map = { pelvis: 'DEF-hips', spine_01: 'DEF-spine.001', spine_02: 'DEF-spine.002', spine_03: 'DEF-spine.003', neck_01: 'DEF-neck', Head: 'DEF-head' };
  for (const side of ['l', 'r']) {
    const S = side.toUpperCase();
    Object.assign(map, {
      [`clavicle_${side}`]: `DEF-shoulder.${S}`, [`upperarm_${side}`]: `DEF-upper_arm.${S}`, [`lowerarm_${side}`]: `DEF-forearm.${S}`,
      [`hand_${side}`]: `DEF-hand.${S}`, [`thigh_${side}`]: `DEF-thigh.${S}`, [`calf_${side}`]: `DEF-shin.${S}`,
      [`foot_${side}`]: `DEF-foot.${S}`, [`ball_${side}`]: `DEF-toe.${S}`,
    });
    for (const f of ['index', 'middle', 'pinky', 'ring']) for (const k of [1, 2, 3]) map[`${f}_0${k}_${side}`] = `DEF-f_${f}.0${k}.${S}`;
    for (const k of [1, 2, 3]) map[`thumb_0${k}_${side}`] = `DEF-thumb.0${k}.${S}`;
  }
  for (const k of Object.keys(map)) map[k] = map[k].replace(/\./g, '');
  return map;
}

const firstSkinned = (root) => {
  let s = null;
  root.traverse((o) => {
    if (!s && o.isSkinnedMesh) s = o;
  });
  return s;
};
const isPerson = (o) => getObjectType(o?.type)?.model === 'person';
const lerpAngle = (a, b, k) => a + Math.atan2(Math.sin(b - a), Math.cos(b - a)) * k;
const HIDDEN = new THREE.MeshBasicMaterial({ visible: false });
const EULER = new THREE.Euler();
const QUAT = new THREE.Quaternion();
/** Caméra sur pied : sa hauteur est celle de son objectif (le pied monte, il ne s'envole pas). */
export const isTripod = (o) => getObjectType(o?.type)?.model === 'camera';
const isCameraModel = (o) => ['camera', 'dolly'].includes(getObjectType(o?.type)?.model);
const followsPath = (o) => ['people', 'animals', 'vehicles'].includes(getObjectType(o?.type)?.cat);
/** Orientation d'une caméra en lacet, tangage et roulis (ordre YXZ : le tangage reste local). */
export function cameraAngles(rotation) {
  const r = rotation || [0, 0, 0];
  QUAT.setFromEuler(EULER.set(r[0] || 0, r[1] || 0, r[2] || 0, 'XYZ'));
  EULER.setFromQuaternion(QUAT, 'YXZ');
  return { yaw: EULER.y, pitch: EULER.x, roll: EULER.z };
}
/** Lacet, tangage, roulis -> rotation (Euler XYZ) enregistrée dans la scène. */
export function cameraRotation(yaw, pitch, roll) {
  QUAT.setFromEuler(EULER.set(pitch || 0, yaw || 0, roll || 0, 'YXZ'));
  EULER.setFromQuaternion(QUAT, 'XYZ');
  return [EULER.x, EULER.y, EULER.z];
}

export class Characters {
  constructor(vp, store) {
    this.vp = vp;
    this.store = store;
    this.rigs = new Map(); // id objet -> rig
    this.t = 0;
    this.lib = null;
    this.error = null;
    this.ready = this._load()
      .then(() => this.syncAll())
      .catch((e) => {
        this.error = String(e?.message || e);
      });
    store.addEventListener('scene', () => this.syncAll());
    store.addEventListener('object-added', (e) => this._sync(e.detail.object));
    store.addEventListener('object-updated', (e) => this._sync(e.detail.object));
    store.addEventListener('object-removed', (e) => this._drop(e.detail));
  }

  // ---------------------------------------------------------------- bibliothèque
  async _load() {
    const loader = new GLTFLoader();
    const [cat, u1, u2, fem] = await Promise.all([
      fetch('/pandora/characters/actions.json').then((r) => r.json()),
      loader.loadAsync('/pandora/characters/ual1.glb'),
      loader.loadAsync('/pandora/characters/ual2.glb'),
      loader.loadAsync('/pandora/characters/mannequin_f.glb'),
    ]);
    this.catalog = cat;
    this.actions = new Map(cat.actions.map((a) => [a.id, a]));
    const native = new Map(u2.animations.map((c) => [c.name, c])); // squelette du volume 2
    const toRetarget = new Map(u1.animations.map((c) => [c.name, c]));
    const src = firstSkinned(SU.clone(u1.scene));
    const dst = firstSkinned(SU.clone(u2.scene));
    const map = rigMap();
    const cache = new Map();
    this.lib = {
      male: u2.scene,
      female: fem.scene,
      clip(name) {
        if (native.has(name)) return native.get(name);
        if (cache.has(name)) return cache.get(name);
        const c = toRetarget.get(name);
        if (!c) return null;
        const out = SU.retargetClip(dst, src, c, { names: map, hip: 'DEF-hips' });
        out.name = name;
        cache.set(name, out);
        return out;
      },
    };
    // hauteur des mannequins à l'échelle 1 (pour les mettre à la taille du personnage)
    this.lib.height = {};
    for (const [k, root] of Object.entries({ male: u2.scene, female: fem.scene })) {
      const b = new THREE.Box3().setFromObject(root);
      this.lib.height[k] = Math.max(0.5, b.max.y - b.min.y);
    }
  }

  /** Actions connues (pour la frise de PANDORA) : [{id, fr, en, group, move, once}]. */
  catalogInfo() {
    return this.catalog ? { groups: this.catalog.groups, actions: this.catalog.actions.map(({ id, fr, en, group, move, once }) => ({ id, fr, en, group, move: !!move, once: !!once })) } : null;
  }

  // ---------------------------------------------------------------- personnages de la scène
  syncAll() {
    for (const id of [...this.rigs.keys()]) if (!this.store.object(id)) this._drop(id);
    for (const o of this.store.scene?.objects || []) this._sync(o);
    this.evaluate(this.t);
  }

  _drop(id) {
    const rig = this.rigs.get(id);
    if (!rig) return;
    rig.root.removeFromParent();
    rig.mixer.stopAllAction();
    this.rigs.delete(id);
  }

  _sync(o) {
    if (!this.lib || !isPerson(o)) return;
    const entry = this.vp.objects.get(o.id);
    if (!entry) return;
    const build = o.props?.build || (o.type === 'person-woman' ? 'woman' : o.type === 'person-child' ? 'child' : 'man');
    const female = build === 'woman';
    const height = (Number(o.props?.height) || (female ? 166 : build === 'child' ? 125 : 178)) / 100;
    const color = this._color(o);
    let rig = this.rigs.get(o.id);
    const key = `${female}|${height}|${color}`;
    if (!rig || rig.key !== key) {
      if (rig) this._drop(o.id);
      const root = SU.clone(female ? this.lib.female : this.lib.male);
      root.scale.setScalar(height / this.lib.height[female ? 'female' : 'male']);
      const main = new THREE.MeshStandardMaterial({ color, roughness: 0.6 });
      const joint = new THREE.MeshStandardMaterial({ color: new THREE.Color(color).multiplyScalar(0.45), roughness: 0.7 });
      root.traverse((m) => {
        if (!m.isMesh) return;
        m.castShadow = true;
        m.receiveShadow = true;
        // Quaternius : deux matériaux (corps / articulations)
        const mats = Array.isArray(m.material) ? m.material : [m.material];
        const swap = mats.map((x, i) => (i === 0 ? main : joint));
        m.material = Array.isArray(m.material) ? swap : swap[0];
        m.frustumCulled = false; // la boîte englobante d'un maillage animé ne suit pas la pose
      });
      const skin = firstSkinned(root);
      rig = { key, root, skin, mixer: new THREE.AnimationMixer(skin), actions: new Map() };
      this.rigs.set(o.id, rig);
    }
    // accroché au corps du modèle d'ARKLIGHT (reconstruit à chaque changement de réglages)
    if (rig.root.parent !== entry.model.body) entry.model.body.add(rig.root);
    entry.model.content?.traverse((m) => {
      if (m.isMesh) m.material = HIDDEN; // silhouette d'ARKLIGHT : invisible, toujours cliquable
    });
    this._place(o, this.t);
  }

  _color(o) {
    const people = (this.store.scene?.objects || []).filter(isPerson).map((x) => x.id).sort();
    return o.pandora?.color || PALETTE[Math.max(0, people.indexOf(o.id)) % PALETTE.length];
  }

  // ---------------------------------------------------------------- frise
  tracks() {
    return this.store.scene?.pandora?.tracks || {};
  }

  /** Action jouée pour un personnage sans marque : sa pose fixe d'ARKLIGHT. */
  _poseAction(o) {
    return this.catalog?.poses?.[o.props?.pose || 'standing'] || 'idle';
  }

  /**
   * État d'un objet au temps t d'après ses keyframes : position, lacet, action en cours (et la
   * précédente pendant le fondu) ; caméra : hauteur d'objectif, tangage et roulis. Sans
   * keyframe : sa place et sa pose fixes.
   */
  stateAt(o, t) {
    const marks = (this.tracks()[o.id] || []).filter((m) => Array.isArray(m.p)).slice().sort((a, b) => a.t - b.t);
    const cam = isCameraModel(o) ? cameraAngles(o.rotation) : null;
    const camera = (lens, pitch, roll) => (cam ? { lens, pitch, roll } : {});
    const baseLens = Number(o.props?.lens) || 1.45;
    if (!marks.length) {
      const id = this._poseAction(o);
      return { p: o.position, yaw: cam ? cam.yaw : o.rotation?.[1] || 0, ...camera(baseLens, cam?.pitch, cam?.roll), cur: { id, start: 0, rate: 1, hold0: !!this.actions?.get(id)?.once }, prev: null, w: 1 };
    }
    const seg = (i) => {
      const a = marks[i];
      const b = marks[i + 1];
      if (!b) return { a, b: null, moving: false, speed: 0 };
      const d = Math.hypot(b.p[0] - a.p[0], b.p[2] - a.p[2]);
      const dt = Math.max(0.05, b.t - a.t);
      // Une action sur place (coup, parole…) portée par une keyframe suivie d'un trajet : elle se
      // joue d'abord sur place, puis le personnage repart vers la keyframe suivante, sans qu'il
      // faille poser une keyframe de plus (Matthieu 30/10/2026). Au plus 70 % de l'intervalle.
      const act = a.action ? this.actions?.get(a.action) : null;
      const hold = d > 0.05 && act && !act.move ? Math.min(this._clipDur(act), dt * 0.7) : 0;
      return { a, b, d, hold, moving: d > 0.05, speed: d / Math.max(0.05, dt - hold) };
    };
    const autoOf = (s) => (!s.moving ? 'idle' : s.speed > 4.2 ? 'sprint' : s.speed > 2.0 ? 'jog' : 'walk');
    // ce que joue le personnage une fois l'éventuelle action sur place terminée
    const actionOf = (s) => (s.a.action && !s.hold ? s.a.action : autoOf(s));
    const rateOf = (s, id) => {
      const act = this.actions?.get(id);
      return act?.move && s.moving && act.speed ? Math.min(2.2, Math.max(0.45, s.speed / act.speed)) : 1;
    };
    let i = marks.length - 1;
    while (i > 0 && marks[i].t > t) i--;
    const s = seg(i);
    let p;
    let yaw;
    if (t <= marks[0].t) {
      p = marks[0].p;
      yaw = marks[0].yaw ?? o.rotation?.[1] ?? 0;
    } else if (!s.b) {
      p = s.a.p;
      yaw = s.a.yaw ?? (i > 0 && seg(i - 1).moving ? Math.atan2(s.a.p[0] - marks[i - 1].p[0], s.a.p[2] - marks[i - 1].p[2]) : o.rotation?.[1] ?? 0);
    } else {
      const from = s.a.t + s.hold;
      const k = Math.min(1, Math.max(0, (t - from) / Math.max(1e-3, s.b.t - from)));
      p = [0, 1, 2].map((j) => s.a.p[j] + (s.b.p[j] - s.a.p[j]) * k);
      if (s.hold && t < from) yaw = i > 0 && seg(i - 1).moving ? Math.atan2(s.a.p[0] - marks[i - 1].p[0], s.a.p[2] - marks[i - 1].p[2]) : s.a.yaw ?? 0;
      else if (s.moving && followsPath(o)) yaw = Math.atan2(s.b.p[0] - s.a.p[0], s.b.p[2] - s.a.p[2]);
      else yaw = lerpAngle(s.a.yaw ?? 0, s.b.yaw ?? s.a.yaw ?? 0, k);
    }
    // Caméra : chaque valeur absente d'une keyframe reprend la précédente
    let extra = {};
    if (cam) {
      let lens = baseLens;
      let pitch = cam.pitch;
      let roll = cam.roll;
      for (let j = 0; j <= i; j++) {
        lens = marks[j].lens ?? lens;
        pitch = marks[j].pitch ?? pitch;
        roll = marks[j].roll ?? roll;
      }
      if (s.b && t > s.a.t) {
        const k = Math.min(1, (t - s.a.t) / Math.max(1e-3, s.b.t - s.a.t));
        lens += ((s.b.lens ?? lens) - lens) * k;
        pitch = lerpAngle(pitch, s.b.pitch ?? pitch, k);
        roll = lerpAngle(roll, s.b.roll ?? roll, k);
      }
      extra = camera(lens, pitch, roll);
    }
    const inHold = s.hold > 0 && t < s.a.t + s.hold;
    let id = inHold ? s.a.action : actionOf(s);
    let start = s.hold > 0 && !inHold ? s.a.t + s.hold : s.a.t;
    let prev = null;
    let w = 1;
    if (s.hold > 0 && !inHold && t < s.a.t + s.hold + FADE) {
      // fin de l'action sur place : fondu vers la marche ou la course
      prev = { id: s.a.action, start: s.a.t, rate: 1 };
      w = Math.max(0, Math.min(1, (t - s.a.t - s.hold) / FADE));
    } else if (i > 0 && t < s.a.t + FADE) {
      const ps = seg(i - 1);
      const pid = actionOf(ps);
      if (pid !== id) {
        prev = { id: pid, start: ps.a.t + ps.hold, rate: rateOf(ps, pid) };
        w = Math.max(0, Math.min(1, (t - s.a.t) / FADE));
      }
    }
    // Un coup porté sur place sans trajet ensuite : une fois fini, retour au repos (pas figé)
    const acted = this.actions?.get(id);
    if (!s.moving && acted?.once && acted.group === 'fight') {
      const end = s.a.t + this._clipDur(acted);
      if (t >= end) {
        prev = { id, start: s.a.t, rate: 1 };
        w = Math.max(0, Math.min(1, (t - end) / FADE));
        id = 'idle';
        start = end;
      }
    }
    const cur = { id, start, rate: inHold ? 1 : rateOf(s, id) };
    return { p, yaw, ...extra, cur, prev, w };
  }

  _clipDur(act) {
    return this.lib?.clip(act.clip)?.duration || 1;
  }

  _action(rig, id) {
    if (rig.actions.has(id)) return rig.actions.get(id);
    const act = this.actions?.get(id);
    const clip = act && this.lib.clip(act.clip);
    const a = clip ? rig.mixer.clipAction(clip) : null;
    if (a) {
      a.enabled = false;
      a.play();
    }
    rig.actions.set(id, a);
    return a;
  }

  _apply(rig, slot, t, weight) {
    if (!slot || weight <= 0) return;
    const a = this._action(rig, slot.id);
    if (!a) return;
    const dur = a.getClip().duration || 1;
    const local = slot.hold0 ? 0 : Math.max(0, t - slot.start) * slot.rate;
    a.enabled = true;
    a.setEffectiveWeight(weight);
    a.time = this.actions.get(slot.id)?.once ? Math.min(local, dur - 1e-3) : local % dur;
  }

  _place(o, t) {
    const entry = this.vp.objects.get(o.id);
    if (!entry) return;
    const st = this.stateAt(o, t);
    const body = entry.model.body;
    // l'objet qu'on déplace à la poignée reste à la poignée (sa keyframe suit, pas l'inverse)
    if (this.tracks()[o.id]?.length && this.vp.draggingObjectId !== o.id) {
      body.position.fromArray(st.p);
      if (st.lens !== undefined) {
        body.quaternion.setFromEuler(EULER.set(st.pitch || 0, st.yaw, st.roll || 0, 'YXZ'));
        this._setLens(entry, o, st.lens);
      } else body.rotation.set(o.rotation?.[0] || 0, st.yaw, o.rotation?.[2] || 0);
    }
    const rig = this.rigs.get(o.id);
    if (!rig) return;
    for (const a of rig.actions.values()) if (a) a.enabled = false;
    this._apply(rig, st.cur, t, st.prev ? st.w : 1);
    this._apply(rig, st.prev, t, st.prev ? 1 - st.w : 0);
    rig.mixer.update(0);
  }

  /** Le pied de la caméra suit la hauteur d'objectif du moment (modèle reconstruit au besoin). */
  _setLens(entry, o, lens) {
    if (!isTripod(o)) return;
    const cur = Number(entry.model.props?.lens) || 1.45;
    if (Math.abs(cur - lens) >= 0.02) entry.model.update({ ...(o.props || {}), lens: Math.round(lens * 100) / 100 });
  }

  /** Pose toute la scène au temps t (personnages animés ; autres objets suivis : place seule). */
  evaluate(t) {
    this.t = Math.max(0, Number(t) || 0);
    for (const o of this.store.scene?.objects || []) {
      if (this.rigs.has(o.id) || this.tracks()[o.id]?.length) this._place(o, this.t);
    }
  }
}
