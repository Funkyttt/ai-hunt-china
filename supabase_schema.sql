create table if not exists public.favorites (
  user_id uuid not null references auth.users(id) on delete cascade,
  product_key text not null,
  product_date date not null,
  created_at timestamptz not null default now(),
  primary key (user_id, product_key)
);

alter table public.favorites enable row level security;

drop policy if exists "favorites are publicly countable" on public.favorites;
drop policy if exists "users read their own favorites" on public.favorites;
create policy "users read their own favorites"
on public.favorites for select
using (auth.uid() = user_id);

drop policy if exists "users insert their own favorites" on public.favorites;
create policy "users insert their own favorites"
on public.favorites for insert
with check (auth.uid() = user_id);

drop policy if exists "users delete their own favorites" on public.favorites;
create policy "users delete their own favorites"
on public.favorites for delete
using (auth.uid() = user_id);

create or replace function public.get_favorite_counts(product_keys text[])
returns table(product_key text, favorite_count bigint)
language sql
security definer
set search_path = public
stable
as $$
  select favorites.product_key, count(*)::bigint
  from public.favorites
  where favorites.product_key = any(product_keys)
  group by favorites.product_key;
$$;

revoke all on function public.get_favorite_counts(text[]) from public;
grant execute on function public.get_favorite_counts(text[]) to anon, authenticated;
grant select, insert, delete on public.favorites to authenticated;
