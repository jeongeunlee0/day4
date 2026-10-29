import { SUPABASE_URL, SUPABASE_ANON_KEY } from './supabase-config.js';

const SYNC_KEY = 'dolhareubang_jeju_v1';
const STAMP_KEY = SYNC_KEY + '_cloud_at';
let client = null;
let userId = null;
let user = null;
let timer = null;
let ready = null;

function init() {
  if (ready) return ready;
  ready = (async () => {
    if (!SUPABASE_URL || !SUPABASE_ANON_KEY) return false;
    try {
      const { createClient } = await import('https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm');
      client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
      let { data: { session } } = await client.auth.getSession();
      if (!session) ({ data: { session } } = await client.auth.signInAnonymously());
      user = session && session.user;
      userId = user && user.id;
      return !!userId;
    } catch (e) { console.warn('[supabase] init failed', e); return false; }
  })();
  return ready;
}

// Pull the cloud save; if it is newer than the local one, store it locally and reload once.
async function pull() {
  const { data, error } = await client.from('game_saves').select('data, updated_at').eq('user_id', userId).maybeSingle();
  if (error || !data) return;
  const localAt = Number(localStorage.getItem(STAMP_KEY) || 0);
  const cloudAt = Date.parse(data.updated_at);
  if (cloudAt > localAt) {
    localStorage.setItem(SYNC_KEY, JSON.stringify(data.data));
    localStorage.setItem(STAMP_KEY, String(cloudAt));
    location.reload();
  }
}

async function push() {
  const raw = localStorage.getItem(SYNC_KEY);
  if (!raw || !client || !userId) return;
  const now = new Date().toISOString();
  const { error } = await client.from('game_saves').upsert({ user_id: userId, data: JSON.parse(raw), updated_at: now });
  if (!error) localStorage.setItem(STAMP_KEY, String(Date.parse(now)));
}

// Call after each local save; uploads are debounced.
export function scheduleCloudSave() {
  if (!client) return;
  clearTimeout(timer);
  timer = setTimeout(push, 5000);
}

export async function startCloudSync() {
  if (await init()) await pull();
}

/* ---- email / password accounts ---- */

// 'guest' (anonymous), 'user' (email account) or 'off' (Supabase not configured)
export async function authState() {
  if (!(await init())) return { mode: 'off' };
  return user.is_anonymous ? { mode: 'guest' } : { mode: 'user', name: unhex(user.email.split('@')[0]) };
}

// Nicknames are mapped to a throw-away address so players never need a real email.
const hex = t => [...new TextEncoder().encode(t)].map(b => b.toString(16).padStart(2, '0')).join('');
const unhex = h => new TextDecoder().decode(Uint8Array.from(h.match(/../g) || [], x => parseInt(x, 16)));
const toEmail = nick => hex(nick.trim().toLowerCase()) + '@dolhareubang.app';
const friendly = m => /already|registered/i.test(m) ? '이미 사용 중인 닉네임이에요' : /invalid login/i.test(m) ? '닉네임 또는 비밀번호가 달라요' : m;
const fail = error => ({ ok: false, message: friendly(error.message) });

// Turns the current guest into an email account, so the existing progress is kept.
export async function signUp(nick, password) {
  if (!(await init())) return { ok: false, message: 'Supabase 설정이 필요해요' };
  const { error } = await client.auth.updateUser({ email: toEmail(nick), password });
  if (error) return fail(error);
  await push();
  return { ok: true, message: '가입 완료! 이제 어디서든 로그인할 수 있어요 🎉' };
}

export async function signIn(nick, password) {
  if (!(await init())) return { ok: false, message: 'Supabase 설정이 필요해요' };
  const { data, error } = await client.auth.signInWithPassword({ email: toEmail(nick), password });
  if (error) return fail(error);
  user = data.user; userId = user.id;
  localStorage.removeItem(STAMP_KEY); // let the account's own cloud save win
  await pull();
  return { ok: true, message: '로그인 성공!' };
}

export async function signOut() {
  if (!(await init())) return;
  await push(); // flush the latest progress before leaving the account
  await client.auth.signOut();
  localStorage.removeItem(SYNC_KEY);
  localStorage.removeItem(STAMP_KEY);
  location.reload();
}
