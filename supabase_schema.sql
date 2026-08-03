
create extension if not exists "pgcrypto";

create table if not exists public.profiles (
 id uuid primary key references auth.users(id) on delete cascade,
 display_name text not null,
 role text not null check (role in ('admin','investor')),
 created_at timestamptz not null default now()
);

create table if not exists public.privacy_settings (
 user_id uuid primary key references public.profiles(id) on delete cascade,
 share_balance boolean not null default false,
 share_holdings boolean not null default false,
 share_trade_details boolean not null default false,
 share_performance_summary boolean not null default true,
 share_strategy_stats boolean not null default true,
 updated_at timestamptz not null default now()
);

create table if not exists public.trades (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references public.profiles(id) on delete cascade,
 owner_name text not null,
 account_type text not null check (account_type in ('Real','Paper')),
 ticker text not null,
 strategy text not null,
 entry_date date not null,
 entry_price numeric not null check (entry_price>0),
 quantity numeric not null check (quantity>0),
 exit_date date,
 exit_price numeric,
 stop_price numeric,
 target_price numeric,
 reason text,
 notes text,
 plan_followed text not null check (plan_followed in ('Yes','Mostly','Partly','No')),
 confidence integer not null default 70 check(confidence between 0 and 100),
 status text not null check(status in ('Open','Closed')),
 created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.privacy_settings enable row level security;
alter table public.trades enable row level security;

create policy "read own profile" on public.profiles for select using(auth.uid()=id);
create policy "manage own privacy" on public.privacy_settings for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create policy "manage own trades" on public.trades for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
