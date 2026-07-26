"""
core/live_mapping.py — Assistant de calage mapping (PANDORA | Live).

Réponse à LA douleur des mappers : tracer les points du polygone de façade dans
l'Advanced Output de Resolume est long, et un recalage en cours de show met le
timing en danger. PANDORA possède déjà la donnée clé : la façade isolée sur fond
noir (BiRefNet) est un masque parfait.

Chaîne :
  1. extract_facade_polygon(image)  — profils haut/bas du masque (silhouette de
     bâtiment ≈ x-monotone) + simplification Douglas-Peucker → ≤ N points propres ;
  2. build_advanced_output_preset() — preset XML Advanced Output (structure
     disséquée depuis un export réel d'Arena 7.26 : Screen > Polygon >
     InputContour/OutputContour + ScreenGuide photo en fond de calage) ;
  3. save_advanced_output_preset()  — écrit dans Documents\\Resolume Arena\\
     Presets\\Advanced Output\\ → apparaît dans le menu Presets d'Arena ;
  4. build_calibration_card()       — mire PNG spécifique au bâtiment (photo
     assombrie + contour + points numérotés + grille) pour caler/recaler
     l'Output Transformation en quelques dizaines de secondes.

Limite assumée v1 : l'extraction par profils capture la silhouette (pignon,
cheminées) mais pas les surplombs latéraux — rarissimes sur une façade.
numpy importé PARESSEUSEMENT (présent dans le build Live via librosa).
"""

from __future__ import annotations

import os
import time

COMP_W, COMP_H = 1920, 1080
_LUMA_THRESHOLD = 18      # fond noir pur (#000) vs façade éclairée
_SCAN_MAX_SIDE  = 640     # profils calculés sur une version réduite (vitesse)


# ── 1. Extraction du polygone ─────────────────────────────────────────────────

def _perp_dist(p, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 <= 1e-12:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    return abs(dx * (ay - py) - (ax - px) * dy) / seg2 ** 0.5


def douglas_peucker(points: list, epsilon: float) -> list:
    """Simplification classique d'une polyligne (récursif)."""
    if len(points) < 3:
        return list(points)
    a, b = points[0], points[-1]
    idx, dmax = 0, 0.0
    for i in range(1, len(points) - 1):
        d = _perp_dist(points[i], a, b)
        if d > dmax:
            idx, dmax = i, d
    if dmax <= epsilon:
        return [a, b]
    left  = douglas_peucker(points[:idx + 1], epsilon)
    right = douglas_peucker(points[idx:], epsilon)
    return left[:-1] + right


def extract_facade_polygon(image_path: str, max_points: int = 12,
                           comp_size: tuple = (COMP_W, COMP_H)) -> list:
    """Polygone fermé (liste de (x, y) en pixels de composition, origine en
    haut à gauche — convention Resolume) épousant la silhouette de la façade.

    image_path = façade isolée sur fond noir (BiRefNet) — ou toute image dont
    le sujet est nettement plus lumineux que le fond."""
    import numpy as np
    from PIL import Image

    img = Image.open(image_path).convert("L")
    w0, h0 = img.size
    scale = max(w0, h0) / float(_SCAN_MAX_SIDE)
    if scale > 1:
        img = img.resize((max(1, round(w0 / scale)), max(1, round(h0 / scale))))
    arr = np.asarray(img, dtype=np.uint8)
    mask = arr > _LUMA_THRESHOLD
    h, w = mask.shape
    cols = np.nonzero(mask.any(axis=0))[0]
    if len(cols) < 4:
        return []

    x_left, x_right = int(cols[0]), int(cols[-1])
    top, bottom = [], []
    for x in range(x_left, x_right + 1):
        ys = np.nonzero(mask[:, x])[0]
        if len(ys) == 0:
            continue
        top.append((float(x), float(ys[0])))
        bottom.append((float(x), float(ys[-1])))

    if not top:
        return []

    # Boucle fermée : profil haut (gauche→droite) puis profil bas (droite→gauche)
    loop = top + bottom[::-1]

    # Simplification : epsilon croissant jusqu'à tenir dans max_points
    eps = 1.5
    simplified = douglas_peucker(loop, eps)
    while len(simplified) > max_points and eps < max(h, w):
        eps *= 1.5
        simplified = douglas_peucker(loop, eps)
    # DP sur boucle ouverte duplique parfois premier/dernier points proches
    if len(simplified) > 1:
        (x1, y1), (x2, y2) = simplified[0], simplified[-1]
        if abs(x1 - x2) + abs(y1 - y2) < 3:
            simplified = simplified[:-1]

    # Coordonnées image réduite → composition (l'image de façade EST le cadre
    # du contenu : nos moods/clips conservent exactement son cadrage)
    cw, ch = comp_size
    sx, sy = cw / float(w), ch / float(h)
    return [(round(x * sx, 4), round(y * sy, 4)) for x, y in simplified]


# ── 2. Preset Advanced Output ─────────────────────────────────────────────────

def _contour_xml(points: list, indent: str) -> str:
    pts = "\n".join(f'{indent}\t<v x="{x}" y="{y}"/>' for x, y in points)
    return (f"{pts}\n{indent[:-1]}</points>\n"
            f"{indent[:-1]}<segments>{'L' * len(points)}</segments>")


def build_advanced_output_preset(name: str, points: list,
                                 comp_size: tuple = (COMP_W, COMP_H),
                                 guide_image: str = "",
                                 uid_base: int | None = None) -> str:
    """Preset XML Advanced Output (structure d'un export réel d'Arena 7.26) :
    un Screen virtuel avec un Polygon dont InputContour = OutputContour = la
    silhouette extraite, et la photo de façade en guide à 25 % d'opacité."""
    cw, ch = comp_size
    uid = uid_base if uid_base is not None else int(time.time() * 1000)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    bx0, bx1 = (min(xs), max(xs)) if xs else (0, cw)
    by0, by1 = (min(ys), max(ys)) if ys else (0, ch)
    pts_in  = _contour_xml(points, "\t\t\t\t\t\t\t\t")
    guide = (f'<ParamPixels name="Image" fileName="{guide_image}"/>'
             if guide_image else '<ParamPixels name="Image"/>')
    return f'''<?xml version="1.0" encoding="utf-8"?>
<XmlState name="{name}">
	<versionInfo name="Resolume Arena" majorVersion="7" minorVersion="26" microVersion="2" revision="8882"/>
	<ScreenSetup name="ScreenSetup">
		<Params name="ScreenSetupParams"/>
		<CurrentCompositionTextureSize width="{cw}" height="{ch}"/>
		<screens>
			<Screen name="PANDORA {name}" uniqueId="{uid}">
				<Params name="Params">
					<Param name="Name" T="STRING" default="" value="PANDORA {name}"/>
					<Param name="Enabled" T="BOOL" default="1" value="1"/>
					<Param name="Hidden" T="BOOL" default="0" value="0"/>
				</Params>
				<guides>
					<ScreenGuide name="ScreenGuide" type="0">
						<Params name="Params">
							{guide}
							<ParamRange name="Opacity" T="DOUBLE" default="0.25" value="0.25">
								<PhaseSourceStatic name="PhaseSourceStatic"/>
								<BehaviourDouble name="BehaviourDouble"/>
								<ValueRange name="defaultRange" min="0" max="1"/>
								<ValueRange name="minMax" min="0" max="1"/>
								<ValueRange name="startStop" min="0" max="1"/>
							</ParamRange>
						</Params>
					</ScreenGuide>
				</guides>
				<layers>
					<Polygon uniqueId="{uid + 14}" IsVirgin="0">
						<Params name="Common">
							<Param name="Name" T="STRING" default="Layer" value="Façade PANDORA"/>
							<Param name="Enabled" T="BOOL" default="1" value="1"/>
						</Params>
						<Params name="Input">
							<ParamChoice name="Input Source" default="0:1" value="0:1" storeChoices="0"/>
							<Param name="Input Opacity" T="BOOL" default="1" value="1"/>
							<Param name="Input Bypass/Solo" T="BOOL" default="1" value="1"/>
						</Params>
						<Params name="Output">
							<Param name="Flip" T="UINT8" default="0" value="0"/>
							<Param name="Is Key" T="BOOL" default="0" value="0"/>
							<Param name="Black BG" T="BOOL" default="0" value="0"/>
						</Params>
						<InputRect orientation="0">
							<v x="{bx0}" y="{by0}"/>
							<v x="{bx1}" y="{by0}"/>
							<v x="{bx1}" y="{by1}"/>
							<v x="{bx0}" y="{by1}"/>
						</InputRect>
						<OutputRect orientation="0">
							<v x="{bx0}" y="{by0}"/>
							<v x="{bx1}" y="{by0}"/>
							<v x="{bx1}" y="{by1}"/>
							<v x="{bx0}" y="{by1}"/>
						</OutputRect>
						<InputContour closed="1">
							<points>
{pts_in}
						</InputContour>
						<OutputContour closed="1">
							<points>
{pts_in}
						</OutputContour>
					</Polygon>
				</layers>
				<OutputDevice>
					<OutputDeviceVirtual name="PANDORA {name}" deviceId="VirtualScreen {uid}" idHash="{uid * 7919 % 10 ** 19}" width="{cw}" height="{ch}">
						<Params name="Params"/>
					</OutputDeviceVirtual>
				</OutputDevice>
			</Screen>
		</screens>
	</ScreenSetup>
</XmlState>
'''


def resolume_presets_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "Documents",
                        "Resolume Arena", "Presets", "Advanced Output")


def save_advanced_output_preset(xml_text: str, name: str,
                                out_dir: str = "") -> str:
    """Écrit le preset là où Arena le liste (menu Presets de l'Advanced Output)."""
    d = out_dir or resolume_presets_dir()
    os.makedirs(d, exist_ok=True)
    safe = "".join(c for c in name if c.isalnum() or c in " -_").strip() or "pandora"
    path = os.path.join(d, f"{safe}.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    return path


def generate_full_calage(ref_path: str, name: str, data_root: str) -> dict:
    """Chaîne complète (partagée Conducteur / page Resolume) :
    polygone → preset Advanced Output → mire. Lève ValueError si façade
    non détectée. Renvoie {points, preset_path, mire_path, preset_name}."""
    points = extract_facade_polygon(ref_path)
    if len(points) < 4:
        raise ValueError("façade non détectée — isole-la d'abord sur fond noir")
    safe_name = (name or "facade").replace("|", "-").strip() or "facade"
    xml = build_advanced_output_preset(safe_name, points, guide_image=ref_path)
    preset_path = save_advanced_output_preset(xml, f"PANDORA {safe_name}")
    mire_path = build_calibration_card(
        ref_path, points, os.path.join(data_root, "mapping", "mire_calage.png"))
    return {"points": points, "preset_path": preset_path,
            "mire_path": mire_path, "preset_name": f"PANDORA {safe_name}"}


# ── 3. Verrouillage du contenu au masque de façade ────────────────────────────
# Retour de test réel : les clips générés « sortent » parfois de la façade.
# Trois leviers cumulés : consigne prompt (doux), keyframes masquées AVANT la
# génération (fort — Seedance suit sa première frame), masque appliqué au clip
# final (option, garanti à 100 %). Le masque pixel vient de la façade isolée
# sur fond noir (BiRefNet) — la même image qui sert au calage.

_MASK_MIN_COVER, _MASK_MAX_COVER = 0.02, 0.95


def facade_mask_coverage(ref_path: str) -> float:
    """Part du cadre occupée par la silhouette éclairée, entre 0 et 1. -1 si illisible.

    Diagnostic pour l'utilisateur (2026-07-26) : le refus de rognage disait
    seulement « détoure-la d'abord », sans dire ce qui avait été mesuré ni sur
    quel critère. Or les deux causes se soignent différemment — une couverture
    quasi nulle veut dire que l'image est trop sombre pour être lue, une
    couverture quasi totale qu'aucun fond noir n'entoure le bâtiment.
    """
    try:
        from PIL import Image
        img = Image.open(ref_path).convert("L")
        mask = img.point(lambda v: 255 if v > _LUMA_THRESHOLD else 0)
        return mask.histogram()[255] / float(mask.size[0] * mask.size[1])
    except Exception:
        return -1.0


def build_facade_mask(ref_path: str, out_path: str, feather: int = 2) -> str:
    """Masque pixel PNG (blanc = façade, noir = hors silhouette) depuis la
    façade isolée sur fond noir. Renvoie "" si la façade n'est PAS isolée
    (masque couvrant ~tout ou ~rien du cadre) — on ne détruit jamais une image
    dont on ne maîtrise pas le détourage."""
    from PIL import Image, ImageFilter

    img = Image.open(ref_path).convert("L")
    mask = img.point(lambda v: 255 if v > _LUMA_THRESHOLD else 0)
    hist = mask.histogram()
    cover = hist[255] / float(mask.size[0] * mask.size[1])
    if not (_MASK_MIN_COVER < cover < _MASK_MAX_COVER):
        return ""
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    mask.save(out_path, "PNG")
    return out_path


def ensure_facade_mask(ref_path: str, data_root: str) -> str:
    """Masque en cache (invalide si la façade change). "" si indisponible."""
    if not ref_path or not os.path.isfile(ref_path):
        return ""
    import hashlib
    key = hashlib.md5(
        f"{ref_path}|{os.path.getmtime(ref_path)}".encode()).hexdigest()[:16]
    out = os.path.join(data_root, "mapping", f"facade_mask_{key}.png")
    if os.path.isfile(out):
        return out
    try:
        return build_facade_mask(ref_path, out)
    except Exception:
        return ""


def apply_facade_mask_to_image(image_path: str, mask_path: str,
                               out_path: str) -> str:
    """Copie de l'image avec tout ce qui dépasse la silhouette rendu noir pur
    (l'original n'est jamais modifié — les moods restent intacts à l'écran)."""
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    mask = Image.open(mask_path).convert("L").resize(img.size)
    black = Image.new("RGB", img.size, (0, 0, 0))
    out = Image.composite(img, black, mask)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    out.save(out_path, "PNG")
    return out_path


# ── Recalage d'un mood sur la façade ─────────────────────────────────────────
# Demande Matthieu 2026-07-26 : un mood mapping doit se superposer EXACTEMENT à la
# façade. Le moteur produit souvent un décalage de quelques pixels — corrigeable —
# mais parfois une vraie déformation (échelle, perspective), qu'aucun recalage ne
# répare : dans ce cas il faut regénérer, pas déplacer l'erreur.
#
# Au-delà de ce seuil de recouvrement APRÈS recalage, on considère que l'écart
# n'était qu'une translation. En dessous, la géométrie a dérivé.
_ALIGN_OK          = 0.97   # superposable : on recale et on rogne
_ALIGN_ACCEPTABLE  = 0.90   # léger écart résiduel : on prévient, on laisse choisir


def _binary(image_path: str, size=None):
    """Zone ÉCLAIRÉE d'une image mapping (le fond est noir pur)."""
    import numpy as np
    from PIL import Image
    im = Image.open(image_path).convert("L")
    if size:
        im = im.resize(size)
    return np.asarray(im) > _LUMA_THRESHOLD


def _iou(a, b) -> float:
    import numpy as np
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def estimate_shift(a, b) -> tuple:
    """Translation (dy, dx) qui superpose `a` sur `b`, par corrélation de phase.

    FFT plutôt qu'une recherche exhaustive : exact au pixel, insensible au bruit,
    et sans dépendance supplémentaire (numpy est déjà là via librosa)."""
    import numpy as np
    A = np.fft.fft2(a.astype(float))
    B = np.fft.fft2(b.astype(float))
    R = A * np.conj(B)
    R /= np.maximum(np.abs(R), 1e-9)
    r = np.fft.ifft2(R).real
    dy, dx = np.unravel_index(int(np.argmax(r)), r.shape)
    h, w = a.shape
    if dy > h // 2:
        dy -= h
    if dx > w // 2:
        dx -= w
    return int(dy), int(dx)


def measure_facade_alignment(image_path: str, mask_path: str) -> dict:
    """Compare un mood à la silhouette de façade.

    Renvoie {iou, shift:(dy,dx), iou_aligned, overflow, missing, verdict} où
    verdict vaut :
      • "aligned"   — déjà superposé, rien à recaler ;
      • "shifted"   — simple translation : recalable SANS perte ;
      • "deformed"  — la géométrie a dérivé : recaler ne ferait que déplacer
                      l'erreur, il faut REGÉNÉRER le mood ;
      • "unavailable" — masque ou image illisible (jamais bloquant).
    """
    import numpy as np
    try:
        from PIL import Image
        msk = Image.open(mask_path).convert("L")
        ref = np.asarray(msk) > 127
        img = _binary(image_path, size=msk.size)
    except Exception:
        return {"verdict": "unavailable"}
    if not ref.any() or not img.any():
        return {"verdict": "unavailable"}

    iou0 = _iou(img, ref)
    dy, dx = estimate_shift(img, ref)
    moved = np.roll(np.roll(img, -dy, axis=0), -dx, axis=1)
    iou1 = _iou(moved, ref)
    # On ne « recale » jamais vers PIRE : si la translation n'apporte rien, on
    # garde la position d'origine et on juge sur elle.
    if iou1 < iou0:
        dy, dx, iou1, moved = 0, 0, iou0, img

    overflow = float(np.logical_and(moved, ~ref).sum() / max(1, moved.sum()))
    missing  = float(np.logical_and(~moved, ref).sum() / max(1, ref.sum()))

    if iou1 < _ALIGN_ACCEPTABLE:
        verdict = "deformed"
    elif dy or dx:
        verdict = "shifted"          # translation pure → recalable sans perte
    elif iou1 >= _ALIGN_OK:
        verdict = "aligned"          # déjà en place
    else:
        # En place mais la lumière déborde de la silhouette : c'est le cas NORMAL
        # d'un halo, et c'est précisément ce que le rognage sert à enlever.
        verdict = "overflow"
    return {"iou": iou0, "shift": (dy, dx), "iou_aligned": iou1,
            "overflow": overflow, "missing": missing, "verdict": verdict}


def align_and_mask_image(image_path: str, mask_path: str, out_path: str,
                         shift: tuple = (0, 0)) -> str:
    """Recale l'image de (dy, dx) puis rend NOIR tout ce qui dépasse la façade.

    L'original n'est jamais modifié. Le recalage se fait à la taille RÉELLE de
    l'image : la mesure, elle, travaille à la taille du masque."""
    from PIL import Image, ImageChops
    img = Image.open(image_path).convert("RGB")
    mask = Image.open(mask_path).convert("L")
    dy, dx = shift
    if dy or dx:
        # La mesure est faite à l'échelle du masque → on remet à l'échelle image.
        sx = img.size[0] / float(mask.size[0])
        sy = img.size[1] / float(mask.size[1])
        img = ImageChops.offset(img, int(round(-dx * sx)), int(round(-dy * sy)))
    black = Image.new("RGB", img.size, (0, 0, 0))
    out = Image.composite(img, black, mask.resize(img.size))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    out.save(out_path, "PNG")
    return out_path


def masked_keyframe(kf_path: str, ref_path: str, data_root: str) -> str:
    """Copie masquée d'un keyframe (cache) — renvoie l'ORIGINAL si le masque
    est indisponible (façade non isolée, erreur PIL…) : jamais bloquant."""
    if not kf_path or not os.path.isfile(kf_path):
        return kf_path
    mask = ensure_facade_mask(ref_path, data_root)
    if not mask:
        return kf_path
    import hashlib
    key = hashlib.md5(
        f"{kf_path}|{os.path.getmtime(kf_path)}|{mask}".encode()).hexdigest()[:16]
    out = os.path.join(data_root, "mapping", "masked_kf", f"{key}.png")
    if os.path.isfile(out):
        return out
    try:
        return apply_facade_mask_to_image(kf_path, mask, out)
    except Exception:
        return kf_path


def build_video_mask_cmd(ffmpeg: str, video_path: str, mask_path: str,
                         out_path: str) -> list:
    """Commande ffmpeg (pure, testable) : multiplie le clip par le masque —
    noir pur GARANTI hors silhouette, audio copié tel quel."""
    return [ffmpeg, "-y", "-i", video_path, "-loop", "1", "-i", mask_path,
            "-filter_complex",
            "[0:v]format=gbrp[vid];[1:v]format=gbrp[mg];"
            "[mg][vid]scale2ref[mk][v2];"
            "[v2][mk]blend=all_mode=multiply:shortest=1,format=yuv420p[out]",
            "-map", "[out]", "-map", "0:a?", "-c:a", "copy", out_path]


def lock_video_to_facade(video_path: str, ref_path: str, data_root: str) -> bool:
    """Applique le masque de façade au clip EN PLACE (même nom → Vidéothèque,
    Resolume et relinks inchangés). False si masque indisponible ou échec —
    le clip d'origine est alors conservé intact."""
    mask = ensure_facade_mask(ref_path, data_root)
    if not mask or not os.path.isfile(video_path):
        return False
    try:
        from core.video_utils import get_ffmpeg_exe
        ff = get_ffmpeg_exe()
    except Exception:
        ff = "ffmpeg"
    tmp = video_path + ".lock.mp4"
    try:
        import subprocess
        flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
        proc = subprocess.run(build_video_mask_cmd(ff, video_path, mask, tmp),
                              capture_output=True, creationflags=flags, timeout=600)
        if (proc.returncode == 0 and os.path.isfile(tmp)
                and os.path.getsize(tmp) > 0):
            os.replace(tmp, video_path)
            return True
        return False
    except Exception:
        return False
    finally:
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ── 4. Mire de calage spécifique au bâtiment ──────────────────────────────────

def build_calibration_card(image_path: str, points: list, out_path: str,
                           comp_size: tuple = (COMP_W, COMP_H)) -> str:
    """Mire PNG : photo de façade assombrie + contour accentué + points
    numérotés + grille des tiers. Projetée sur le bâtiment, elle permet de
    caler (et surtout RECALER en urgence) l'Output Transformation en faisant
    coïncider le contour avec les vraies arêtes."""
    from PIL import Image, ImageDraw

    cw, ch = comp_size
    base = Image.open(image_path).convert("RGB").resize((cw, ch))
    dark = Image.eval(base, lambda v: v // 2)        # photo à ~50 %
    draw = ImageDraw.Draw(dark)

    # Grille des tiers + croix centrale (repères de déformation globale)
    grid = (90, 90, 90)
    for fx in (cw / 3, 2 * cw / 3):
        draw.line([(fx, 0), (fx, ch)], fill=grid, width=1)
    for fy in (ch / 3, 2 * ch / 3):
        draw.line([(0, fy), (cw, fy)], fill=grid, width=1)
    draw.line([(cw / 2 - 40, ch / 2), (cw / 2 + 40, ch / 2)], fill=(255, 255, 255), width=2)
    draw.line([(cw / 2, ch / 2 - 40), (cw / 2, ch / 2 + 40)], fill=(255, 255, 255), width=2)

    if points:
        loop = list(points) + [points[0]]
        # double trait : halo sombre + trait clair (lisible sur toute matière)
        draw.line(loop, fill=(0, 0, 0), width=7)
        draw.line(loop, fill=(78, 205, 196), width=3)
        for i, (x, y) in enumerate(points, 1):
            r = 14
            draw.ellipse([x - r, y - r, x + r, y + r],
                         outline=(255, 255, 255), width=3, fill=(20, 20, 30))
            draw.text((x - (4 if i < 10 else 8), y - 6), str(i),
                      fill=(255, 255, 255))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    dark.save(out_path, "PNG")
    return out_path
