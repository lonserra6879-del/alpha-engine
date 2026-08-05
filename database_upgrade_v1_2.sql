create table if not exists public.paper_trades (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  ticker text not null,
  strategy text not null,
  thesis text,
  entry_date date not null,
  entry_price numeric not null check (entry_price > 0),
  quantity numeric not null check (quantity > 0),
  stop_price numeric,
  target_price numeric,
  planned_risk_reward numeric,
  status text not null default 'Open' check (status in ('Open','Closed')),
  exit_date date,
  exit_price numeric,
  close_reason text,
  lesson text,
  created_at timestamptz not null default now()
);

create table if not exists public.academy_progress (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  lesson_key text not null,
  completed boolean not null default false,
  completed_at timestamptz,
  unique(user_id, lesson_key)
);

alter table public.paper_trades enable row level security;
alter table public.academy_progress enable row level security;

drop policy if exists "manage own paper trades" on public.paper_trades;
create policy "manage own paper trades"
on public.paper_trades for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "manage own academy progress" on public.academy_progress;
create policy "manage own academy progress"
on public.academy_progress for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);
