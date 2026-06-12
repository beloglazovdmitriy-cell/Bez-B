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
