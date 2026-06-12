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
const API_BASE = import.meta.env.VITE_API_BASE ?? (ON_PAGES ? "https://155.212.134.96.sslip.io" : "");

async function getJSON<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { headers: { "X-Init-Data": initData() } });
    if (!res.ok) throw new Error(String(res.status));
    return (await res.json()) as T;
  } catch {
    return fallback; // бэкенд не запущен / ошибка — показываем мок
  }
}

export const loadSummary = () => getJSON("/api/summary", mockSummary);
export const loadHistory = () => getJSON("/api/history", mockHistory);
export const loadBench = () => getJSON("/api/compare", mockBench);
export const loadJournal = () => getJSON("/api/journal", mockJournal);
export const loadUser = () => getJSON("/api/me", fallbackUser());

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

export const apiBuy = (b: { ticker: string; amountUsdt: number; reason?: string }) =>
  postJSON("/api/buy", b);
export const apiSell = (b: { ticker: string; amountUsdt: number | null; reason?: string }) =>
  postJSON("/api/sell", b);
export const apiDeposit = (b: { rub: number; rate: number }) =>
  postJSON("/api/deposit", b);
export const apiWithdraw = (b: { amountUsdt: number }) =>
  postJSON("/api/withdraw", b);
export const apiDepositAsset = (b: { ticker: string; amountUsdt: number; price?: number; reason?: string }) =>
  postJSON("/api/deposit_asset", b);
