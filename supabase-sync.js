import { SUPABASE_URL, SUPABASE_ANON_KEY } from './supabase-config.js';

const SYNC_KEY = 'dolhareubang_jeju_v1';
const STAMP_KEY = SYNC_KEY + '_cloud_at';
let client = null;
let userId = null;
let timer = null;

async function init() {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) return false;
  try {
    const { createClient } = await import('https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm');
    client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    let { data: { session } } = await client.auth.getSession();
    if (!session) ({ data: { session } } = await client.auth.signInAnonymously());
    userId = session && session.user.id;
    return !!userId;
  } catch (e) { console.warn('[supabase] init failed', e); return false; }
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
