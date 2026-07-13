"""Envoi des avis / bugs / rapports de crash vers Supabase (table pandora_reports).

Principe : l'utilisateur clique « Envoyer » dans PANDORA (fenêtre Nous contacter ou
fenêtre de crash) → une ligne est insérée dans la table Supabase de 22eme ARKANE,
SANS passer par une boîte mail. Matthieu consulte les rapports dans le dashboard
Supabase (Table Editor → pandora_reports) ; un e-mail automatique pourra s'ajouter
plus tard via une Edge Function.

La clé « anon » est PUBLIQUE PAR CONCEPTION (Supabase la destine aux clients) : la
sécurité vient des politiques RLS de la table — insertion seule, aucune lecture ni
modification possible (voir tools/supabase_pandora_reports.sql). Tant que les deux
constantes ci-dessous sont vides, la fonctionnalité est simplement DÉSACTIVÉE (les
boutons d'envoi ne s'affichent pas) : l'app reste 100 % fonctionnelle sans serveur.

Aucune dépendance UI — testable hors ligne.
"""

# ⚠ À REMPLIR (Matthieu) : URL du projet + clé « anon public » — Supabase dashboard
# → Settings → API. Exemple : "https://abcdefgh.supabase.co"
SUPABASE_URL = ""
SUPABASE_ANON_KEY = ""

_TABLE = "pandora_reports"

# Bornes anti-abus : on tronque plutôt que refuser (un rapport tronqué vaut mieux
# qu'un envoi qui échoue). Le log garde sa FIN (c'est là que vit l'erreur).
_MAX_MESSAGE = 8000
_MAX_EMAIL   = 200
_MAX_LOG     = 12000

REPORT_KINDS = ("avis", "bug", "crash")


def is_configured() -> bool:
    """False tant que l'URL/clé ne sont pas renseignées → UI d'envoi masquée."""
    return bool(SUPABASE_URL.strip() and SUPABASE_ANON_KEY.strip())


def build_payload(kind: str, message: str, email: str = "", log: str = "") -> dict:
    """Construit la ligne à insérer (pur, testable) : tronque, borne, contextualise."""
    import platform
    from core.version import VERSION
    if kind not in REPORT_KINDS:
        kind = "avis"
    return {
        "kind":        kind,
        "message":     (message or "").strip()[:_MAX_MESSAGE],
        "email":       (email or "").strip()[:_MAX_EMAIL],
        "app_version": VERSION,
        "os":          f"{platform.system()} {platform.release()}",
        "log":         (log or "")[-_MAX_LOG:],
    }


def submit_report(kind: str, message: str, email: str = "", log: str = "") -> None:
    """Insère un rapport dans la table Supabase. Lève une exception en cas d'échec
    (l'appelant affiche l'erreur humanisée). À appeler depuis un worker — sauf au
    crash, où un appel bloquant court est acceptable."""
    if not is_configured():
        raise RuntimeError("Envoi non configuré dans cette version de PANDORA.")
    import requests
    r = requests.post(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/{_TABLE}",
        json=build_payload(kind, message, email, log),
        timeout=15,
        headers={
            "apikey":        SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type":  "application/json",
            "Prefer":        "return=minimal",   # pas de lecture en retour (RLS)
        },
    )
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Envoi refusé (HTTP {r.status_code}) : {r.text[:200]}")
