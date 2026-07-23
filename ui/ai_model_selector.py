"""Helpers partagés des sélecteurs IA des pages Paramètres Cinéma et Live."""

from __future__ import annotations

from core.ai_registry import (ENGINES, PROFILES, engine, primary_menu_items,
                              profile_from_config, resolve_engine)


def _disable_last(combo) -> None:
    item = combo.model().item(combo.count() - 1)
    if item is not None:
        item.setEnabled(False)


def _selected_engine_from_legacy(cfg: dict) -> str:
    saved = (cfg.get("ai_engine") or "").strip()
    if saved:
        return saved
    provider = (cfg.get("ai_provider") or "anthropic").strip().lower()
    model = (cfg.get("ai_model_creative") or "").strip()
    if provider == "openai":
        model = (cfg.get("openai_model") or model or "gpt-5.5").strip()
    for key, item in ENGINES.items():
        if item["provider"] == provider and item.get("model", "") == model:
            return key
    return f"{provider}:{model}" if provider and model else ""


def populate_primary(combo, cfg: dict) -> None:
    combo.blockSignals(True)
    combo.clear()
    rows = primary_menu_items(cfg.get("ai_available_models") or {})
    for row in rows:
        if not row.get("selectable"):
            combo.addItem(f"── {row['label']} ──", None)
            _disable_last(combo)
            continue
        combo.addItem(row["label"], {"profile": row.get("profile", "single"),
                                      "engine": row.get("engine", "")})

    profile = profile_from_config(cfg)
    selected_engine = _selected_engine_from_legacy(cfg)
    selected = -1
    for idx in range(combo.count()):
        data = combo.itemData(idx)
        if not isinstance(data, dict):
            continue
        if profile in PROFILES and data.get("profile") == profile:
            selected = idx
            break
        if profile not in PROFILES and data.get("engine") == selected_engine:
            selected = idx
            break
    if selected < 0 and selected_engine:
        spec = engine(selected_engine, cfg)
        if spec:
            combo.addItem(spec["name"], {"profile": "single", "engine": selected_engine})
            selected = combo.count() - 1
    if selected < 0:
        selected = next((i for i in range(combo.count())
                         if isinstance(combo.itemData(i), dict)), 0)
    combo.setCurrentIndex(selected)
    combo.blockSignals(False)


def selected_primary(combo) -> dict:
    data = combo.currentData()
    return data if isinstance(data, dict) else {"profile": "anthropic_optimized", "engine": ""}


def selection_provider(combo, cfg: dict | None = None) -> str:
    data = selected_primary(combo)
    profile = data.get("profile", "")
    if profile in PROFILES:
        return PROFILES[profile]["group"]
    spec = engine(data.get("engine", ""), cfg or {})
    return (spec or {}).get("provider", "custom")


def apply_primary_to_config(cfg: dict, combo) -> dict:
    data = selected_primary(combo)
    profile = data.get("profile", "single")
    key = data.get("engine", "")
    cfg["ai_profile"] = profile
    cfg["ai_engine"] = key
    if profile == "anthropic_optimized":
        cfg["ai_provider"] = "anthropic"
        cfg["ai_model_creative"] = "claude-opus-4-8"
    elif profile == "openai_optimized":
        cfg["ai_provider"] = "openai"
        cfg["ai_model_creative"] = "gpt-5.6-sol"
    else:
        spec = engine(key, cfg) or engine("custom", cfg)
        provider = spec["provider"]
        model = spec.get("model", "")
        cfg["ai_provider"] = provider
        cfg["ai_model_creative"] = model
        if provider in ("openai", "kimi", "glm", "ollama", "custom"):
            cfg[f"{provider}_model"] = model
    return cfg


def populate_task_engines(combo, cfg: dict, task: str, saved_key: str = "") -> None:
    """Ajoute défaut, groupes et modèles statiques/découverts au combo d'une tâche."""
    combo.blockSignals(True)
    combo.clear()
    profile = profile_from_config(cfg)
    strict_group = (PROFILES.get(profile) or {}).get("group", "")
    base_cfg = dict(cfg)
    base_cfg["ai_task_engines"] = {}
    recommended_name = resolve_engine(base_cfg, task).get("name", "Assistant IA")
    combo.addItem(f"Par défaut · {recommended_name}", "")
    rows = primary_menu_items(cfg.get("ai_available_models") or {})
    added = set()
    for row in rows:
        if strict_group and row.get("group") != strict_group:
            continue
        if not row.get("selectable"):
            combo.addItem(f"── {row['label']} ──", None)
            _disable_last(combo)
            continue
        key = row.get("engine", "")
        if not key or key in added:
            continue
        added.add(key)
        combo.addItem(row["label"], key)
    saved_spec = engine(saved_key, cfg) if saved_key else None
    if strict_group and saved_spec and saved_spec.get("group") != strict_group:
        saved_key = ""
        saved_spec = None
    if saved_key and saved_key not in added:
        spec = saved_spec
        combo.addItem((spec or {}).get("name", saved_key), saved_key)
    for idx in range(combo.count()):
        if combo.itemData(idx) == saved_key:
            combo.setCurrentIndex(idx)
            break
    combo.blockSignals(False)


def refresh_task_engines_for_primary(primary_combo, task_combos: dict,
                                     cfg: dict) -> None:
    """Recalcule les tâches dès que l'assistant principal change.

    Le choix d'un nouveau profil signifie « utiliser ce profil pour toutes les
    tâches ». Les anciens overrides sont donc remis sur « Par défaut » dans l'UI ;
    la sauvegarde automatique les retire ensuite de la configuration.
    """
    next_cfg = dict(cfg)
    apply_primary_to_config(next_cfg, primary_combo)
    next_cfg["ai_task_engines"] = {}
    for task, combo in (task_combos or {}).items():
        populate_task_engines(combo, next_cfg, task, "")


def start_model_discovery(owner, primary_combo, task_combos: dict, button) -> None:
    """Lance la découverte dans un QThread et recharge les combos à l'arrivée."""
    if getattr(owner, "_model_discovery_worker", None) is not None:
        return
    from api.ai_models import ModelDiscoveryWorker
    from core.config import load_config, save_config

    button.setEnabled(False)
    button.setText("Recherche des modèles accessibles…")
    cfg = load_config()
    worker = ModelDiscoveryWorker(cfg, parent=owner)
    owner._model_discovery_worker = worker

    def _done(models: dict, errors: dict):
        current = load_config()
        cached = dict(current.get("ai_available_models") or {})
        cached.update(models)
        current["ai_available_models"] = cached
        save_config(current)
        populate_primary(primary_combo, current)
        saved = current.get("ai_task_engines") or {}
        for task, combo in (task_combos or {}).items():
            populate_task_engines(combo, current, task, saved.get(task, ""))
        count = sum(len(v) for v in models.values())
        if count:
            button.setText(f"Actualiser les modèles accessibles · {count} détectés")
        elif errors:
            button.setText("Actualiser les modèles accessibles · connexion impossible")
        else:
            button.setText("Actualiser les modèles accessibles · aucune clé disponible")
        button.setEnabled(True)

    worker.done.connect(_done)
    def _cleanup():
        if getattr(owner, "_model_discovery_worker", None) is worker:
            owner._model_discovery_worker = None
        worker.deleteLater()
    # ``finished`` est ici le signal NATIF de QThread, uniquement pour libérer un
    # worker déjà terminé ; le résultat métier reste bien le signal personnalisé done.
    worker.finished.connect(_cleanup)
    worker.start()
