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

// База API. В dev пусто → работает vite-прокси /api. На GitHub Pages задаётся
// через VITE_API_BASE (адрес задеплоенного бэкенда). Если не задано и /api нет —
// getJSON отдаёт мок (фолбэк), и приложение всё равно живёт.
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

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
export const loadUser = () => getJSON("/api/me", mockUser);

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
