-- ═══════════════════════════════════════════════════════════════════════════
-- PANDORA — table des rapports (avis / bugs / crashs) envoyés depuis l'app.
--
-- À exécuter UNE FOIS dans le dashboard Supabase : SQL Editor → New query →
-- coller ce fichier → Run. Puis récupérer dans Settings → API :
--   · Project URL   → core/support_backend.py : SUPABASE_URL
--   · anon public   → core/support_backend.py : SUPABASE_ANON_KEY
--
-- Sécurité : RLS activée, la clé anon ne peut QU'INSÉRER — aucune lecture,
-- modification ni suppression possible depuis l'app. Les rapports se consultent
-- dans Table Editor → pandora_reports (ou via un e-mail auto ajouté plus tard
-- avec une Edge Function + Resend).
-- ═══════════════════════════════════════════════════════════════════════════

create table if not exists public.pandora_reports (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  kind        text not null check (kind in ('avis', 'bug', 'crash')),
  message     text not null default '',
  email       text not null default '',   -- optionnel : pour répondre à l'utilisateur
  app_version text not null default '',
  os          text not null default '',
  log         text not null default ''    -- queue du log en cas de bug/crash
);

alter table public.pandora_reports enable row level security;

-- Insertion seule pour la clé anon (celle embarquée dans PANDORA).
create policy "pandora_reports_insert_anon"
  on public.pandora_reports
  for insert
  to anon
  with check (true);

-- AUCUNE policy select/update/delete pour anon → lecture impossible depuis l'app.
-- (Le dashboard Supabase, lui, passe par le rôle service et voit tout.)
