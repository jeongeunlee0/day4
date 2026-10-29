-- Cloud save table: one row per (anonymous) user, protected by RLS.
create table if not exists public.game_saves (
  user_id uuid primary key references auth.users (id) on delete cascade,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

alter table public.game_saves enable row level security;

create policy "own save: select" on public.game_saves
  for select using (auth.uid() = user_id);
create policy "own save: insert" on public.game_saves
  for insert with check (auth.uid() = user_id);
create policy "own save: update" on public.game_saves
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own save: delete" on public.game_saves
  for delete using (auth.uid() = user_id);
