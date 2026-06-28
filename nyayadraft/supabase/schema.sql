-- NyayaDraft — draft history schema.
--
-- Run this ONCE against your Supabase project before using draft history:
--   Supabase dashboard → SQL Editor → paste → Run
-- (or `supabase db query < supabase/schema.sql` with the CLI).
--
-- It is idempotent: safe to re-run. RLS confines every row to its owner, so the
-- browser anon key can never read or write another user's drafts.

create extension if not exists pgcrypto;

create table if not exists public.drafts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid()
    references auth.users (id) on delete cascade,
  doc_type text not null,
  doc_type_label text not null,
  fields jsonb not null default '{}'::jsonb,
  generated_text text not null,
  title text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists drafts_user_id_updated_at_idx
  on public.drafts (user_id, updated_at desc);

-- Expose the table to the authenticated role (RLS still gates the rows).
grant select, insert, update, delete on public.drafts to authenticated;

alter table public.drafts enable row level security;

drop policy if exists "Users can read own drafts" on public.drafts;
create policy "Users can read own drafts" on public.drafts
  for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert own drafts" on public.drafts;
create policy "Users can insert own drafts" on public.drafts
  for insert to authenticated
  with check ((select auth.uid()) = user_id);

drop policy if exists "Users can update own drafts" on public.drafts;
create policy "Users can update own drafts" on public.drafts
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists "Users can delete own drafts" on public.drafts;
create policy "Users can delete own drafts" on public.drafts
  for delete to authenticated
  using ((select auth.uid()) = user_id);
