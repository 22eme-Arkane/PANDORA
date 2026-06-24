"""
core/recurrence.py — détection de plans RÉCURRENTS (même configuration caméra) au
sein d'une MÊME séquence, pour les libeller en couleur (un groupe = une couleur).

Cœur DÉTERMINISTE (sans réseau, testable) : regroupe les plans d'une séquence par
(décor, axe caméra, valeur de plan, acteurs cadrés). L'analyse Claude
(`api.screenplay.AnalyzeRecurrentShotsWorker`) RAFFINE ce résultat pour les cas
subtils (même acteur à la même position, champ/contrechamp) ; en l'absence de clé
IA, ce cœur déterministe sert de repli. La couleur d'un groupe sert ensuite de clé
de sélection « Rendu/Audio » (sélectionner tous les plans d'un même groupe).
"""


def _key(shot: dict) -> tuple:
    """Signature de configuration caméra d'un plan (décor + axe + cadrage + acteurs)."""
    chars = tuple(sorted(
        str(c) for c in
        (shot.get("character_ids") or shot.get("character_names") or [])))
    return (
        (shot.get("decor_id") or shot.get("decor_name") or "").strip().lower(),
        (shot.get("camera_axis") or "").strip().lower(),
        (shot.get("shot_size") or "").strip().lower(),
        chars,
    )


def group_recurrent(shots: list) -> list:
    """Groupes de plans récurrents PAR SÉQUENCE : pour chaque séquence, les plans
    partageant la même signature caméra et présents AU MOINS 2 fois. Renvoie
    [[shot_id, …], …] dans l'ordre d'apparition (séquence par séquence)."""
    by_seq: dict = {}
    order: list = []
    for s in shots or []:
        seq = s.get("seq_num", 1)
        if seq not in by_seq:
            by_seq[seq] = []
            order.append(seq)
        by_seq[seq].append(s)

    groups: list = []
    for seq in order:
        buckets: dict = {}
        b_order: list = []
        for s in by_seq[seq]:
            k = _key(s)
            if not k[0] and not k[1]:        # ni décor ni axe → non exploitable
                continue
            if k not in buckets:
                buckets[k] = []
                b_order.append(k)
            sid = s.get("id")
            if sid:
                buckets[k].append(sid)
        for k in b_order:
            if len(buckets[k]) >= 2:         # récurrent = revient au moins 1 fois
                groups.append(buckets[k])
    return groups


def group_name(index: int) -> str:
    """Nom lisible d'un groupe récurrent : « Récurrent A », « Récurrent B », …"""
    return "Récurrent " + (chr(65 + index) if index < 26 else str(index + 1))


def apply_groups(groups: list, version_id: str | None = None) -> int:
    """Pose le FLAG « récurrent » à chaque groupe avec une COULEUR DISTINCTE
    (+ nom « Récurrent A/B… »). N'écrase PAS le libellé couleur esthétique
    (champ séparé). Renvoie le nombre de groupes flaggés."""
    import core.storyboard as sb
    vid = version_id or sb.DEFAULT_VERSION_ID
    for gi, ids in enumerate(groups or []):
        color = sb.recurrent_color(gi)
        name = group_name(gi)
        for sid in ids:
            sb.set_recurrent(sid, color, name, vid)
    return len(groups or [])


def detect_and_apply(version_id: str | None = None) -> int:
    """Détection déterministe + coloration des groupes récurrents d'une version."""
    import core.storyboard as sb
    vid = version_id or sb.DEFAULT_VERSION_ID
    return apply_groups(group_recurrent(sb.list_shots(vid)), vid)
