-- Supabase SQL Editor'da bir marta ishga tushiring
create extension if not exists pgcrypto;

create table if not exists questions(
  id bigserial primary key,
  text text not null, a text not null, b text not null, c text not null, d text not null,
  correct char(1) not null check (correct in ('A','B','C','D'))
);
create table if not exists attempts(
  id uuid primary key default gen_random_uuid(),
  first_name text not null, last_name text not null,
  name_key text not null unique,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  score int not null default 0, wrong int not null default 0,
  current_idx int not null default 0,
  q_started_at timestamptz not null default now(),
  qids bigint[] not null
);
create table if not exists admins(user_id uuid primary key references auth.users(id) on delete cascade);

alter table questions enable row level security;
alter table attempts enable row level security;
alter table admins enable row level security;

create or replace function is_admin() returns boolean language sql security definer stable as
$$ select exists(select 1 from admins where user_id = auth.uid()) $$;

drop policy if exists adm_q on questions;
create policy adm_q on questions for all to authenticated using (is_admin()) with check (is_admin());
drop policy if exists adm_a_sel on attempts;
create policy adm_a_sel on attempts for select to authenticated using (is_admin());
drop policy if exists adm_a_del on attempts;
create policy adm_a_del on attempts for delete to authenticated using (is_admin());

-- Serverdagi vaqt nazorati: har savol 30 soniya
create or replace function sync_attempt(aid uuid) returns attempts language plpgsql security definer as $$
declare a attempts; n int;
begin
  select * into a from attempts where id = aid for update;
  if not found then raise exception 'notfound'; end if;
  n := array_length(a.qids,1);
  while a.finished_at is null and a.current_idx < n and now() - a.q_started_at >= interval '30 seconds' loop
    a.wrong := a.wrong + 1; a.current_idx := a.current_idx + 1;
    a.q_started_at := a.q_started_at + interval '30 seconds';
  end loop;
  if a.finished_at is null and a.current_idx >= n then a.finished_at := now(); end if;
  update attempts set wrong=a.wrong, current_idx=a.current_idx, q_started_at=a.q_started_at, finished_at=a.finished_at where id = aid;
  return a;
end $$;
revoke execute on function sync_attempt(uuid) from public, anon, authenticated;

create or replace function start_attempt(f text, l text) returns json language plpgsql security definer as $$
declare ids bigint[]; nid uuid;
begin
  f := trim(f); l := trim(l);
  if length(f) < 2 or length(l) < 2 then raise exception 'invalid'; end if;
  select array_agg(id) into ids from (select id from questions order by random() limit 15) s;
  if ids is null then raise exception 'noquestions'; end if;
  begin
    insert into attempts(first_name,last_name,name_key,qids)
    values (f,l,lower(f||' '||l),ids) returning id into nid;
  exception when unique_violation then raise exception 'already';
  end;
  return json_build_object('id', nid);
end $$;

create or replace function get_question(aid uuid) returns json language plpgsql security definer as $$
declare a attempts; q questions; n int;
begin
  a := sync_attempt(aid); n := array_length(a.qids,1);
  if a.finished_at is not null then
    return json_build_object('done',true,'score',a.score,'total',n);
  end if;
  select * into q from questions where id = a.qids[a.current_idx+1];
  return json_build_object('done',false,'idx',a.current_idx,'total',n,
    'left', greatest(0, 30 - extract(epoch from now() - a.q_started_at)),
    'text',q.text,'a',q.a,'b',q.b,'c',q.c,'d',q.d);
end $$;

create or replace function answer_q(aid uuid, i int, c text) returns json language plpgsql security definer as $$
declare a attempts; q questions; n int; ok boolean;
begin
  a := sync_attempt(aid); n := array_length(a.qids,1);
  if a.finished_at is null and a.current_idx = i then
    select * into q from questions where id = a.qids[a.current_idx+1];
    ok := (upper(c) = q.correct);
    update attempts set
      score = score + (case when ok then 1 else 0 end),
      wrong = wrong + (case when ok then 0 else 1 end),
      current_idx = current_idx + 1, q_started_at = now(),
      finished_at = case when current_idx + 1 >= n then now() else null end
    where id = aid;
  end if;
  return get_question(aid);
end $$;

grant execute on function start_attempt(text,text), get_question(uuid), answer_q(uuid,int,text), is_admin() to anon, authenticated;

alter publication supabase_realtime add table attempts;

-- Namuna savollar (admin paneldan o'zgartirasiz)
insert into questions(text,a,b,c,d,correct) values
('2 + 2 * 2 = ?','6','8','4','10','A'),
('O''zbekiston poytaxti?','Samarqand','Toshkent','Buxoro','Xiva','B'),
('Bir yilda necha oy bor?','10','11','12','13','C'),
('HTML nima?','Dasturlash tili emas, belgilash tili','Ma''lumotlar bazasi','Operatsion tizim','Brauzer','A'),
('CSS nima uchun ishlatiladi?','Server','Dizayn','Baza','Tarmoq','B'),
('Suvning qaynash harorati (°C)?','90','80','100','120','C'),
('Eng katta okean?','Tinch','Atlantika','Hind','Arktika','A'),
('10 * 10 = ?','10','100','1000','20','B'),
('JavaScript qaysi muhitda ishlaydi?','Faqat serverda','Faqat telefonda','Brauzerda va serverda','Faqat Windowsda','C'),
('Haftada necha kun bor?','7','6','5','8','A'),
('Quyosh tizimida nechta sayyora bor?','7','9','8','10','C'),
('15 - 7 = ?','8','7','9','6','A'),
('SQL nima uchun?','Rasm chizish','Ma''lumotlar bilan ishlash','O''yin yaratish','Musiqa','B'),
('Futbol jamoasida maydonda nechta o''yinchi?','9','10','12','11','D'),
('1 km necha metr?','100','10000','1000','500','C');

-- Admin yaratish: Authentication > Users orqali foydalanuvchi qo'shing, so'ng:
-- insert into admins(user_id) select id from auth.users where email = 'admin@example.com';
