-- v0.6 Sherlock Case Files upgrade
alter table public.trades
  add column if not exists case_snapshot jsonb;

alter table public.trades
  add column if not exists evidence_score integer;

alter table public.trades
  add column if not exists case_verdict text;

alter table public.trades
  add column if not exists case_created_at timestamptz;
