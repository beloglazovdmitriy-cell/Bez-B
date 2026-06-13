// Слой данных Mini App: тянет реальные данные из API (api.py через vite-прокси /api),
// а при недоступности бэкенда мягко откатывается на мок — чтобы экраны всегда жили.

import {
  mockSummary, mockHistory, mockBench, mockJournal, mockUser,
} from "./mock";
export type { Summary, Position, HistoryPoint, BenchRow, JournalEntry } from "./mock";

// initData из Telegram (если открыто внутри Telegram) — для авторизации на бэке.
function initData(): string {
  return (window as any).Telegram?.WebApp?.initData || "";
}

// id владельца (публичный, не секрет) — чтобы узнавать админа на клиенте,
// когда API недоступен (напр. Pages без бэкенда). Реальная защита операций —
// на сервере по подписанному initData.
const ADMIN_ID = Number(import.meta.env.VITE_ADMIN_ID ?? 503720103);

function fallbackUser() {
  const u = (window as any).Telegram?.WebApp?.initDataUnsafe?.user;
  if (u) return { name: u.first_name || "Гость", isAdmin: u.id === ADMIN_ID, isPremium: false };
  return mockUser;
}

// База API. В dev пусто → работает vite-прокси /api. На GitHub Pages по умолчанию
// ходим к нашему серверу (VPS, HTTPS). Можно переопределить через VITE_API_BASE.
const ON_PAGES = typeof location !== "undefined" && location.hostname.endsWith("github.io");
const ENV_BASE = import.meta.env.VITE_API_BASE;
// важно: пустая строка (когда репо-переменная не задана в Actions) = «не задано»
const API_BASE = (ENV_BASE && ENV_BASE.length > 0)
  ? ENV_BASE
  : (ON_PAGES ? "https://155.212.134.96.sslip.io" : "");

async function getJSON<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { headers: { "X-Init-Data": initData() } });
    if (!res.ok) throw new Error(String(res.status));
    return (await res.json()) as T;
  } catch {
    return fallback; // бэкенд не запущен / ошибка — показываем мок
  }
}

// pf — какой портфель: "bezb" (публичный) или "me" (личный пользователя)
export type Pf = "bezb" | "me";
export const loadSummary = (pf: Pf) => getJSON(`/api/summary?p=${pf}`, mockSummary);
export const loadHistory = (pf: Pf) => getJSON(`/api/history?p=${pf}`, mockHistory);
export const loadBench = (pf: Pf) => getJSON(`/api/compare?p=${pf}`, mockBench);
export const loadJournal = (pf: Pf) => getJSON(`/api/journal?p=${pf}`, mockJournal);
export async function loadUser() {
  const u = await getJSON("/api/me", fallbackUser());
  // подстраховка: если Telegram сообщает, что это владелец — показываем
  // админ-вкладки даже если серверная проверка подписи дала сбой
  // (сами операции всё равно защищены проверкой на сервере).
  const tg = (window as any).Telegram?.WebApp?.initDataUnsafe?.user;
  if (tg && tg.id === ADMIN_ID) return { ...u, isAdmin: true };
  return u;
}

// ── пишущие операции (только владелец; бэкенд проверяет initData) ──
async function postJSON(path: string, body: unknown): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Init-Data": initData() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as any).detail || "Ошибка операции");
  }
}

export const apiBuy = (pf: Pf, b: { ticker: string; amountUsdt: number; reason?: string }) =>
  postJSON(`/api/buy?p=${pf}`, b);
export const apiSell = (pf: Pf, b: { ticker: string; amountUsdt: number | null; reason?: string }) =>
  postJSON(`/api/sell?p=${pf}`, b);
export const apiDeposit = (pf: Pf, b: { rub: number; rate: number }) =>
  postJSON(`/api/deposit?p=${pf}`, b);
export const apiWithdraw = (pf: Pf, b: { amountUsdt: number }) =>
  postJSON(`/api/withdraw?p=${pf}`, b);
export const apiDepositAsset = (pf: Pf, b: { ticker: string; amountUsdt: number; price?: number; reason?: string }) =>
  postJSON(`/api/deposit_asset?p=${pf}`, b);

// AI-разбор портфеля → возвращает текст разбора
export async function apiAnalyze(pf: Pf): Promise<string> {
  const res = await fetch(`${API_BASE}/api/analyze?p=${pf}`, {
    method: "POST",
    headers: { "X-Init-Data": initData() },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as any).detail || "AI недоступен");
  }
  return (await res.json()).text as string;
}

// AI-разбор конкретной сделки (черновик поста) → текст
export async function apiTradeComment(pf: Pf, id: number): Promise<string> {
  const res = await fetch(`${API_BASE}/api/trade_comment?p=${pf}&id=${id}`, {
    method: "POST",
    headers: { "X-Init-Data": initData() },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as any).detail || "AI недоступен");
  }
  return (await res.json()).text as string;
}

// AI-сценарии по портфелю → текст
export async function apiScenarios(pf: Pf): Promise<string> {
  const res = await fetch(`${API_BASE}/api/scenarios?p=${pf}`, {
    method: "POST", headers: { "X-Init-Data": initData() },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as any).detail || "AI недоступен");
  }
  return (await res.json()).text as string;
}

// AI-дайджест рынка (владелец) → текст-черновик
export async function apiDigest(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/digest`, {
    method: "POST", headers: { "X-Init-Data": initData() },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as any).detail || "AI недоступен");
  }
  return (await res.json()).text as string;
}

// Опубликовать текст в канал (только владелец)
export const apiPublish = (text: string) => postJSON("/api/publish", { text });

// ── Контент-студия (очередь черновиков, только владелец) ──
export interface Draft {
  id: number; ts: number; kind: string; text: string; status: string;
  reactions?: Record<string, number>; mine?: string[];
}
export interface ReactState { counts: Record<string, number>; mine: string[]; }
export const FEED_REACTIONS = ["🔥", "👍", "🤔"];

export async function apiFeedReact(post_id: number, emoji: string): Promise<ReactState> {
  const res = await fetch(`${API_BASE}/api/feed/react`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Init-Data": initData() },
    body: JSON.stringify({ post_id, emoji }),
  });
  if (!res.ok) {
    const e = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((e as any).detail || "Ошибка реакции");
  }
  return res.json();
}

async function reqJSON<T>(path: string, method = "GET"): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method, headers: { "X-Init-Data": initData() } });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as any).detail || "Ошибка");
  }
  return res.json();
}

export const apiFeed = () => reqJSON<Draft[]>("/api/feed");

// ── Главная (домашняя сводка) ──
export interface HomeMood { value: number; label: string; prev: number; trend: "up" | "down" | "flat"; }
export interface HomeDigest { id: number; ts: number; text: string; }
export interface HomeTrade { side: "buy" | "sell"; ticker: string; amountUsd: number; date: string; isToday: boolean; reason: string; }
export interface Home { mood: HomeMood | null; digest: HomeDigest | null; bezbToday: HomeTrade | null; }
export const apiHome = () => reqJSON<Home>("/api/home");
export const apiContentGenerate = (kind: string) =>
  reqJSON<Draft>(`/api/content/generate?kind=${kind}`, "POST");
export const apiContentDrafts = () => reqJSON<Draft[]>("/api/content/drafts");
export const apiContentPublish = (id: number) => reqJSON<{ ok: boolean }>(`/api/content/publish?id=${id}`, "POST");
export const apiContentDelete = (id: number) => reqJSON<{ ok: boolean }>(`/api/content/delete?id=${id}`, "POST");
export const apiContentUpdate = (id: number, text: string) => postJSON(`/api/content/update?id=${id}`, { text });
export const apiContentCustom = (topic: string) => postJSON("/api/content/custom", { topic });
