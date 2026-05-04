-- ============================================================
-- APEX Schema v2 — Run in Supabase SQL Editor
-- ============================================================

-- ── EXPENSES ─────────────────────────────────────────────────
create table if not exists public.expenses (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete cascade not null,
  amount      numeric(12,2) not null,
  currency    text not null default 'INR',
  category    text not null default 'other'
              check (category in ('food','transport','shopping','health','entertainment','bills','investment','other')),
  description text,
  paid_to     text,
  expense_at  timestamptz not null default now(),
  created_at  timestamptz not null default now()
);
create index on public.expenses (user_id, expense_at desc);
alter table public.expenses enable row level security;
create policy "expenses_own" on public.expenses for all using (auth.uid() = user_id);

-- ── SUBSCRIPTIONS ─────────────────────────────────────────────
create table if not exists public.subscriptions (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade not null,
  name         text not null,
  amount       numeric(12,2) not null,
  currency     text not null default 'INR',
  cycle        text not null default 'monthly'
               check (cycle in ('daily','weekly','monthly','yearly')),
  next_due     date,
  category     text default 'other',
  is_active    boolean not null default true,
  created_at   timestamptz not null default now()
);
alter table public.subscriptions enable row level security;
create policy "subscriptions_own" on public.subscriptions for all using (auth.uid() = user_id);

-- ── HABITS ───────────────────────────────────────────────────
create table if not exists public.habits (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade not null,
  title        text not null,
  description  text,
  frequency    text not null default 'daily'
               check (frequency in ('daily','weekly','monthly')),
  target_days  int[] default '{1,2,3,4,5,6,7}',
  remind_at    time,
  is_active    boolean not null default true,
  created_at   timestamptz not null default now()
);
alter table public.habits enable row level security;
create policy "habits_own" on public.habits for all using (auth.uid() = user_id);

create table if not exists public.habit_logs (
  id         uuid primary key default gen_random_uuid(),
  habit_id   uuid references public.habits(id) on delete cascade not null,
  user_id    uuid references auth.users(id) on delete cascade not null,
  logged_at  date not null default current_date,
  note       text,
  unique (habit_id, logged_at)
);
create index on public.habit_logs (habit_id, logged_at desc);
alter table public.habit_logs enable row level security;
create policy "habit_logs_own" on public.habit_logs for all using (auth.uid() = user_id);

-- ── PROJECTS ─────────────────────────────────────────────────
create table if not exists public.projects (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade not null,
  title        text not null,
  description  text,
  status       text not null default 'active'
               check (status in ('active','paused','completed','abandoned')),
  due_date     date,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
alter table public.projects enable row level security;
create policy "projects_own" on public.projects for all using (auth.uid() = user_id);
create trigger projects_updated_at before update on public.projects for each row execute function update_updated_at();

-- ── NOTES ────────────────────────────────────────────────────
create table if not exists public.notes (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid references auth.users(id) on delete cascade not null,
  title      text,
  content    text not null,
  tags       text[] default '{}',
  pinned     boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on public.notes (user_id, created_at desc);
alter table public.notes enable row level security;
create policy "notes_own" on public.notes for all using (auth.uid() = user_id);
create trigger notes_updated_at before update on public.notes for each row execute function update_updated_at();

-- ── LISTS ────────────────────────────────────────────────────
create table if not exists public.lists (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid references auth.users(id) on delete cascade not null,
  name       text not null,
  type       text not null default 'general'
             check (type in ('grocery','shopping','todo','packing','general')),
  created_at timestamptz not null default now()
);
alter table public.lists enable row level security;
create policy "lists_own" on public.lists for all using (auth.uid() = user_id);

create table if not exists public.list_items (
  id         uuid primary key default gen_random_uuid(),
  list_id    uuid references public.lists(id) on delete cascade not null,
  user_id    uuid references auth.users(id) on delete cascade not null,
  text       text not null,
  checked    boolean not null default false,
  created_at timestamptz not null default now()
);
alter table public.list_items enable row level security;
create policy "list_items_own" on public.list_items for all using (auth.uid() = user_id);

-- ── ROUTINES ─────────────────────────────────────────────────
create table if not exists public.routines (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete cascade not null,
  title       text not null,
  description text,
  steps       jsonb not null default '[]',
  trigger_at  time,
  days        int[] default '{1,2,3,4,5}',
  is_active   boolean not null default true,
  last_run_at timestamptz,
  created_at  timestamptz not null default now()
);
alter table public.routines enable row level security;
create policy "routines_own" on public.routines for all using (auth.uid() = user_id);

-- ── Enable Realtime for new tables ───────────────────────────
alter publication supabase_realtime add table public.habits;
alter publication supabase_realtime add table public.habit_logs;
