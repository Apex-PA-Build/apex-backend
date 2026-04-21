-- Migration: switch memories embedding from vector(512) to vector(384)
-- Run this in Supabase SQL Editor if you already have tables from the old schema.sql
-- Safe to run multiple times.

-- 1. Drop the old index and function
drop index if exists public.memories_embedding_idx;
drop function if exists match_memories(vector(512), uuid, float, int);

-- 2. Swap the column (existing rows get NULL embedding — they'll be re-embedded on next search/store)
alter table public.memories drop column if exists embedding;
alter table public.memories add column embedding vector(384);

-- 3. Rebuild the IVFFLAT index
create index on public.memories using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- 4. Recreate the RPC function with correct dimension and lower threshold
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
  where user_id    = match_user_id
    and is_deleted = false
    and embedding  is not null
    and 1 - (embedding <=> query_embedding) > match_threshold
  order by embedding <=> query_embedding
  limit match_count;
$$;
