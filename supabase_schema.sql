create table if not exists public.favorites (
  user_id uuid not null references auth.users(id) on delete cascade,
  product_key text not null,
  product_date date not null,
  created_at timestamptz not null default now(),
  primary key (user_id, product_key)
);

alter table public.favorites enable row level security;

create policy "favorites are publicly countable"
on public.favorites for select
using (true);

create policy "users insert their own favorites"
on public.favorites for insert
with check (auth.uid() = user_id);

create policy "users delete their own favorites"
on public.favorites for delete
using (auth.uid() = user_id);

create or replace view public.favorite_counts
with (security_invoker = true)
as
select product_key, count(*)::bigint as favorite_count
from public.favorites
group by product_key;

grant select on public.favorite_counts to anon, authenticated;
grant select, insert, delete on public.favorites to authenticated;
