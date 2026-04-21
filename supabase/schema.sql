-- ============================================================
-- APEX — Supabase Schema
-- Run this in your Supabase SQL Editor
-- ============================================================

-- Enable required extensions
create extension if not exists vector;
create extension if not exists pg_cron;
create extension if not exists pg_net;

-- ============================================================
-- PROFILES (extends auth.users)
-- ============================================================
create table public.profiles (
  id             uuid references auth.users(id) on delete cascade primary key,
  name           text not null,
  timezone       text not null default 'Asia/Kolkata',
  mood_today     text check (mood_today in ('energetic','focused','good','tired','stressed')),
  preferences    jsonb not null default '{}',
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

-- ============================================================
-- CONNECTIONS (PA-to-PA friend/colleague graph)
-- ============================================================
create table public.connections (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid references auth.users(id) on delete cascade not null,
  connected_user_id uuid references auth.users(id) on delete cascade not null,
  status            text not null default 'pending'
                    check (status in ('pending','accepted','blocked')),
  created_at        timestamptz not null default now(),
  unique (user_id, connected_user_id)
);

-- ============================================================
-- GOALS
-- ============================================================
create table public.goals (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid references auth.users(id) on delete cascade not null,
  title             text not null,
  description       text,
  category          text not null default 'work'
                    check (category in ('work','health','finance','personal','learning')),
  status            text not null default 'active'
                    check (status in ('active','paused','completed','abandoned')),
  progress_pct      int not null default 0 check (progress_pct between 0 and 100),
  target_date       date,
  check_in_schedule text not null default 'weekly'
                    check (check_in_schedule in ('daily','weekly','monthly')),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- ============================================================
-- TASKS
-- ============================================================
create table public.tasks (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid references auth.users(id) on delete cascade not null,
  goal_id             uuid references public.goals(id) on delete set null,
  parent_task_id      uuid references public.tasks(id) on delete cascade,
  title               text not null,
  description         text,
  status              text not null default 'pending'
                      check (status in ('pending','in_progress','done','deferred','cancelled')),
  priority            text not null default 'medium'
                      check (priority in ('low','medium','high','critical')),
  eisenhower_quadrant int check (eisenhower_quadrant between 1 and 4),
  energy_required     text check (energy_required in ('low','medium','high')),
  due_at              timestamptz,
  source_integration  text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

-- ============================================================
-- CALENDAR EVENTS
-- ============================================================
create table public.calendar_events (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references auth.users(id) on delete cascade not null,
  external_id   text,
  title         text not null,
  description   text,
  location      text,
  start_at      timestamptz not null,
  end_at        timestamptz not null,
  attendees     jsonb not null default '[]',
  source        text not null default 'manual'
                check (source in ('google','outlook','manual')),
  buffer_before int not null default 0,
  is_cancelled  boolean not null default false,
  created_at    timestamptz not null default now(),
  unique (user_id, external_id, source)
);

-- ============================================================
-- MEMORIES (pgvector — replaces Qdrant)
-- ============================================================
create table public.memories (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid references auth.users(id) on delete cascade not null,
  content    text not null,
  category   text not null
             check (category in ('preference','relationship','pattern','fact','decision','commitment')),
  source     text not null default 'conversation'
             check (source in ('conversation','call','task','goal','user_explicit')),
  embedding  vector(384),
  metadata   jsonb not null default '{}',
  is_deleted boolean not null default false,
  created_at timestamptz not null default now()
);

create index on public.memories using ivfflat (embedding vector_cosine_ops) with (lists = 100);
create index on public.memories (user_id, is_deleted);

-- Semantic similarity search function
create or replace function match_memories(
  query_embedding  vector(384),
  match_user_id    uuid,
  match_threshold  float default 0.4,
  match_count      int   default 10
)
returns table (
  id         uuid,
  content    text,
  category   text,
  source     text,
  similarity float,
  created_at timestamptz
)
language sql stable
as $$
  select
    id, content, category, source,
    1 - (embedding <=> query_embedding) as similarity,
    created_at
  from public.memories
  where user_id   = match_user_id
    and is_deleted = false
    and 1 - (embedding <=> query_embedding) > match_threshold
  order by embedding <=> query_embedding
  limit match_count;
$$;

-- ============================================================
-- REMINDERS
-- ============================================================
create table public.reminders (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade not null,
  title        text not null,
  body         text,
  type         text not null default 'time'
               check (type in ('time','location','deadline','inactivity','relationship')),
  remind_at    timestamptz not null,
  status       text not null default 'pending'
               check (status in ('pending','snoozed','dismissed','fired')),
  snoozed_until timestamptz,
  metadata     jsonb not null default '{}',
  created_at   timestamptz not null default now()
);

create index on public.reminders (user_id, status, remind_at);

-- ============================================================
-- AGENT MESSAGES (PA-to-PA)
-- ============================================================
create table public.agent_messages (
  id           uuid primary key default gen_random_uuid(),
  from_user_id uuid references auth.users(id) on delete cascade not null,
  to_user_id   uuid references auth.users(id) on delete cascade not null,
  message_type text not null
               check (message_type in (
                 'scheduling_request','scheduling_response',
                 'financial_settle','follow_up_nudge',
                 'info_request','info_response'
               )),
  content      jsonb not null,
  status       text not null default 'pending'
               check (status in ('pending','accepted','declined','negotiating','resolved','expired')),
  thread_id    uuid,
  resolved_at  timestamptz,
  created_at   timestamptz not null default now()
);

create index on public.agent_messages (to_user_id, status);
create index on public.agent_messages (thread_id);

-- ============================================================
-- CALL SESSIONS
-- ============================================================
create table public.call_sessions (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade not null,
  title        text,
  transcript   text not null default '',
  summary      text,
  action_items jsonb not null default '[]',
  decisions    jsonb not null default '[]',
  people       jsonb not null default '[]',
  status       text not null default 'active'
               check (status in ('active','ended')),
  started_at   timestamptz not null default now(),
  ended_at     timestamptz
);

-- ============================================================
-- OAUTH INTEGRATIONS
-- ============================================================
create table public.integrations (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid references auth.users(id) on delete cascade not null,
  provider          text not null
                    check (provider in ('google','slack','notion','zoom')),
  access_token_enc  text not null,
  refresh_token_enc text,
  scope             text,
  external_user_id  text,
  expires_at        timestamptz,
  is_active         boolean not null default true,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  unique (user_id, provider)
);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
alter table public.profiles         enable row level security;
alter table public.connections       enable row level security;
alter table public.goals             enable row level security;
alter table public.tasks             enable row level security;
alter table public.calendar_events   enable row level security;
alter table public.memories          enable row level security;
alter table public.reminders         enable row level security;
alter table public.agent_messages    enable row level security;
alter table public.call_sessions     enable row level security;
alter table public.integrations      enable row level security;

-- Profiles
create policy "profiles_own" on public.profiles for all using (auth.uid() = id);

-- Connections
create policy "connections_own" on public.connections for all using (auth.uid() = user_id);
create policy "connections_visible" on public.connections for select using (auth.uid() = connected_user_id);

-- Goals
create policy "goals_own" on public.goals for all using (auth.uid() = user_id);

-- Tasks
create policy "tasks_own" on public.tasks for all using (auth.uid() = user_id);

-- Calendar Events
create policy "events_own" on public.calendar_events for all using (auth.uid() = user_id);

-- Memories
create policy "memories_own" on public.memories for all using (auth.uid() = user_id);

-- Reminders
create policy "reminders_own" on public.reminders for all using (auth.uid() = user_id);

-- Agent Messages
create policy "agent_messages_sender" on public.agent_messages for all using (auth.uid() = from_user_id);
create policy "agent_messages_receiver" on public.agent_messages for select using (auth.uid() = to_user_id);
create policy "agent_messages_receiver_update" on public.agent_messages for update using (auth.uid() = to_user_id);

-- Call Sessions
create policy "calls_own" on public.call_sessions for all using (auth.uid() = user_id);

-- Integrations
create policy "integrations_own" on public.integrations for all using (auth.uid() = user_id);

-- ============================================================
-- TRIGGERS — auto-update updated_at
-- ============================================================
create or replace function update_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_updated_at         before update on public.profiles         for each row execute function update_updated_at();
create trigger goals_updated_at            before update on public.goals            for each row execute function update_updated_at();
create trigger tasks_updated_at            before update on public.tasks            for each row execute function update_updated_at();
create trigger integrations_updated_at     before update on public.integrations     for each row execute function update_updated_at();

-- ============================================================
-- AUTO-CREATE PROFILE ON SIGNUP
-- ============================================================
create or replace function handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (id, name)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'name', split_part(new.email, '@', 1))
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();
