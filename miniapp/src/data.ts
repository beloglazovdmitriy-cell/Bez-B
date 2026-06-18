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
  if (u) return { name: u.first_name || "Гость", isAdmin: u.id === ADMIN_ID, isPremium: false, isSubscribed: false, premiumUntil: 0, premiumPrice: 990, premiumEarlyBird: false, earlyBirdLeft: 100 };
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
export type Pf = "bezb" | "me" | "fantasy";
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

// POST с телом, возвращает JSON-ответ
async function postJSONr<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Init-Data": initData() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as any).detail || "Ошибка");
  }
  return res.json();
}

export const apiBuy = (pf: Pf, b: { ticker: string; amountUsdt: number; reason?: string }) =>
  postJSON(`/api/buy?p=${pf}`, b);
export const apiSell = (pf: Pf, b: { ticker: string; amountUsdt: number | null; reason?: string }) =>
  postJSON(`/api/sell?p=${pf}`, b);
export const apiDeposit = (pf: Pf, b: { rub: number; rate: number }) =>
  postJSON(`/api/deposit?p=${pf}`, b);
export const apiWithdraw = (pf: Pf, b: { amountUsdt: number }) =>
  postJSON(`/api/withdraw?p=${pf}`, b);

// ── сезон фэнтези-портфелей ──
export interface Fantasy {
  season: { startTs: number; endTs: number };
  joined: boolean; startCapital: number; value: number | null;
  returnPct: number | null; rank: number | null; players: number; bezbReturnPct: number;
}
export interface FantasyLeader { name: string; value: number; returnPct: number; }
export const apiFantasy = () => reqJSON<Fantasy>("/api/fantasy");
export const apiFantasyJoin = () => reqJSON<Fantasy>("/api/fantasy/join", "POST");
export const apiFantasyLeaderboard = () => reqJSON<FantasyLeader[]>("/api/fantasy/leaderboard");

export interface PlayerLevel {
  xp: number; level: number; title: string; curXp: number; nextXp: number | null; anon?: boolean;
}
export const apiProfileLevel = () => reqJSON<PlayerLevel>("/api/profile/level");
export const apiFantasyMentor = () => reqJSON<{ text: string }>("/api/fantasy/mentor", "POST");

// ── событие дня + стрик входов ──
export interface DailyEvent {
  id: number; title: string; text: string;
  choices: { key: string; label: string }[];
  myChoice: string | null; crowd: Record<string, number>; total: number; takeaway?: string;
}
export const apiEventToday = () => reqJSON<DailyEvent>("/api/event/today");
export const apiEventChoose = (choice: string) =>
  postJSONr<{ myChoice: string; takeaway: string; crowd: Record<string, number>; total: number }>(
    "/api/event/choose", { choice });
export interface Streak { streak: number; best: number; today?: boolean; }
export const apiStreakPing = () => postJSONr<Streak>("/api/streak/ping", {});

// ── реферал + бейджи ──
export interface Referral { link: string; count: number; days: number; }
export const apiReferral = () => reqJSON<Referral>("/api/referral");
export interface Badge { icon: string; label: string; earned: boolean; }
export const apiBadges = () => reqJSON<Badge[]>("/api/profile/badges");

// ── квиз «Детектор буллшита» ──
export interface QuizStats { score: number; streak: number; best: number; answered: number[]; }
export interface QuizNext {
  done: boolean; question?: { id: number; text: string };
  stats: QuizStats; total: number; answeredCount: number;
}
export interface QuizResult { correct: boolean; bs: boolean; explain: string; stats: QuizStats; }
export const apiQuizNext = () => reqJSON<QuizNext>("/api/quiz/next");
export const apiQuizAnswer = (qid: number, bs: boolean) =>
  postJSONr<QuizResult>("/api/quiz/answer", { qid, bs });
export const apiQuizReset = () => postJSONr<{ ok: boolean }>("/api/quiz/reset", {});

// ── игра «Прогноз недели» ──
export interface PredRound {
  id: number; symbol: string; target: number; startTs: number; closeTs: number;
  status: string; result: "up" | "down" | null; closePrice: number | null;
}
export interface Predict {
  round: PredRound | null; myVote: "up" | "down" | null;
  crowd: { up: number; down: number; total: number };
  last: PredRound | null; me: { points: number; total: number };
}
export interface PredLeader { uid: string; name: string; points: number; total: number; }
export const apiPredict = () => reqJSON<Predict>("/api/predict");
export const apiPredictVote = (choice: "up" | "down") =>
  postJSONr<{ ok: boolean; myVote: string; crowd: { up: number; down: number; total: number } }>(
    "/api/predict/vote", { choice });
export const apiPredictLeaderboard = () => reqJSON<PredLeader[]>("/api/predict/leaderboard");

// ── оплата премиума ──
export const apiPayInvoice = () => postJSONr<{ link: string }>("/api/pay/invoice", {});

export interface PayConfig {
  provider: "cloudpayments" | "telegram" | "none";
  publicId: string; price: number; tier: string; days: number;
  title: string; accountId: string; invoiceId: string;
}
export const apiPayConfig = () => reqJSON<PayConfig>("/api/pay/config");

// Создать платёжную ссылку CloudPayments (hosted-страница). Открываем её во внешнем
// браузере — там 3DS работает, в отличие от виджета внутри Telegram WebView (виснет).
export const apiCreateOrder = () => reqJSON<{ url: string }>("/api/cloudpayments/order", "POST");

// Загрузить SDK CloudPayments (один раз) и открыть виджет оплаты.
let _cpLoaded: Promise<void> | null = null;
function loadCloudPayments(): Promise<void> {
  if ((window as any).cp) return Promise.resolve();
  if (_cpLoaded) return _cpLoaded;
  _cpLoaded = new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = "https://widget.cloudpayments.ru/bundles/cloudpayments.js";
    s.onload = () => res();
    s.onerror = () => rej(new Error("Не удалось загрузить форму оплаты"));
    document.head.appendChild(s);
  });
  return _cpLoaded;
}

export async function payCloudPayments(
  cfg: PayConfig, cb: { onSuccess?: () => void; onFail?: (r: string) => void } = {},
): Promise<void> {
  await loadCloudPayments();
  const tg = (window as any).Telegram?.WebApp;
  // На время оплаты выходим из фуллскрина и возвращаем вертикальные свайпы:
  // иначе окно 3DS банка (ввод кода из СМС) виснет — клавиатура не появляется,
  // а Telegram перехватывает касания/скролл оверлея.
  try { tg?.exitFullscreen?.(); } catch { /* старые клиенты */ }
  try { tg?.enableVerticalSwipes?.(); } catch { /* старые клиенты */ }
  const restore = () => {
    try { tg?.requestFullscreen?.(); } catch { /* noop */ }
    try { tg?.disableVerticalSwipes?.(); } catch { /* noop */ }
  };

  const widget = new (window as any).cp.CloudPayments();
  widget.pay("charge", {
    publicId: cfg.publicId,
    description: cfg.title,
    amount: cfg.price,
    currency: "RUB",
    accountId: cfg.accountId,
    invoiceId: cfg.invoiceId,
    skin: "classic",
  }, {
    onSuccess: () => { restore(); cb.onSuccess?.(); },
    onFail: (reason: string) => { restore(); cb.onFail?.(reason); },
    onComplete: () => { restore(); },   // на любой исход (в т.ч. закрытие окна)
  });
}

// ── подписка на мгновенные пуши о сделках Без Б ──
export const apiSubscribe = () => reqJSON<{ ok: boolean; isSubscribed: boolean }>("/api/subscribe", "POST");
export const apiUnsubscribe = () => reqJSON<{ ok: boolean; isSubscribed: boolean }>("/api/unsubscribe", "POST");

// ── стрик дисциплины DCA ──
export interface Dca {
  streak: number; longest: number; total: number; lastTs: number | null;
  canCheckIn: boolean; nextInDays: number; atRisk: boolean; anon?: boolean;
  result?: "started" | "on_time" | "reset" | "early"; ok?: boolean;
}
export const apiDca = () => reqJSON<Dca>("/api/dca");
export const apiDcaCheckin = () => reqJSON<Dca>("/api/dca/checkin", "POST");

// ── онбординг (5 уроков) ──
export interface Onboarding {
  done: number; total: number; canRead: boolean; finished: boolean;
  nextInHours: number; anon?: boolean; ok?: boolean;
}
export const apiOnboarding = () => reqJSON<Onboarding>("/api/onboarding");
export const apiOnboardingRead = () => reqJSON<Onboarding>("/api/onboarding/read", "POST");

// ── Q&A ──
export interface QaItem {
  id: number; ts: number; uid?: string; name?: string;
  question: string; answer: string | null; answeredBy: string | null;
}
export const apiQaAsk = (question: string) => postJSONr<QaItem>("/api/qa/ask", { question });
export const apiQaMine = () => reqJSON<QaItem[]>("/api/qa/mine");
export const apiQaAll = () => reqJSON<QaItem[]>("/api/qa/all");
export const apiQaAnswer = (id: number, text: string) =>
  postJSONr<{ ok: boolean }>("/api/qa/answer", { id, text });

// ── DCA-песочница (бэктест на истории) ──
export interface SandboxPoint { date: string; invested: number; value: number; }
export interface SandboxResult {
  ticker: string; amount: number; everyWeeks: number; weeks: number;
  invested: number; value: number; units: number; profitPct: number;
  avgPrice: number; lumpValue: number; lumpProfitPct: number;
  firstPrice: number; lastPrice: number; priceChangePct: number; points: SandboxPoint[];
}
export const apiSandboxDca = (ticker: string, amount: number, years: number) =>
  reqJSON<SandboxResult>(`/api/sandbox/dca?ticker=${ticker}&amount=${amount}&years=${years}`);
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
  reactions?: Record<string, number>; mine?: string[]; comments?: number;
}
export interface ReactState { counts: Record<string, number>; mine: string[]; }
// "bez" — фирменная реакция-логотип (рисуется монетой), остальные — эмодзи.
export const FEED_REACTIONS = ["bez", "🔥", "👍"];

export interface Comment { id: number; uid: string; name: string; text: string; ts: number; }
export const apiComments = (post_id: number) =>
  reqJSON<Comment[]>(`/api/feed/comments?post_id=${post_id}`);
export const apiAddComment = (post_id: number, text: string) =>
  postJSONr<Comment>("/api/feed/comment", { post_id, text });
export const apiDeleteComment = (id: number) =>
  postJSONr<{ ok: boolean }>("/api/feed/comment/delete", { id });

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

// ── «Нелюбимчик недели» (премиум; free видит тизер) ──
export interface UnderdogStats {
  ticker: string; score: number; price: number; dd: number;
  rsi: number | null; ret7: number; ret30: number; belowSma200: boolean;
}
export interface Underdog {
  locked: boolean; weekId?: string; ticker?: string | null; score?: number;
  stats?: UnderdogStats; analysis?: string; top3?: UnderdogStats[]; teaser?: string;
}
export const apiUnderdog = () => reqJSON<Underdog>("/api/underdog");

// Зафиксировать источник перехода (start_param из диплинка ?startapp=src_...)
export const apiAppOpen = (src: string) =>
  reqJSON<{ ok: boolean }>(`/api/appopen?src=${encodeURIComponent(src)}`, "POST");

// ── Главная (домашняя сводка) ──
export interface HomeMood { value: number; label: string; prev: number; trend: "up" | "down" | "flat"; }
export interface HomeDigest { id: number; ts: number; text: string; }
export interface HomeTrade { side: "buy" | "sell"; ticker: string; amountUsd: number; date: string; isToday: boolean; reason: string; }
export interface BezbIndexComp { label: string; score: number; detail: string; }
export interface BezbIndex { value: number; label: string; zone: string; components: BezbIndexComp[]; }
export interface Home { mood: HomeMood | null; digest: HomeDigest | null; bezbToday: HomeTrade | null; bezbIndex?: BezbIndex | null; }
export const apiHome = () => reqJSON<Home>("/api/home");
export const apiContentGenerate = (kind: string) =>
  reqJSON<Draft>(`/api/content/generate?kind=${kind}`, "POST");
export const apiContentDrafts = () => reqJSON<Draft[]>("/api/content/drafts");
export interface PlanSlot { kind: string; label: string; }
export interface PlanDay { day: number; dow: string; isToday: boolean; morning: PlanSlot; evening: PlanSlot; }
export interface ContentPlan { today: number; morningHour: number; eveningHour: number; days: PlanDay[]; }
export const apiContentPlan = () => reqJSON<ContentPlan>("/api/content/plan");
export async function apiContentPublish(
  id: number,
  opts: { cta?: boolean; chart?: boolean; card?: boolean; image?: File | null } = {},
): Promise<{ ok: boolean }> {
  const cta = opts.cta !== false;
  const chart = opts.chart !== false;
  const card = opts.card === true;
  const url = `${API_BASE}/api/content/publish?id=${id}&cta=${cta}&chart=${chart}&card=${card}`;
  const init: RequestInit = { method: "POST", headers: { "X-Init-Data": initData() } };
  if (opts.image) {
    const fd = new FormData();
    fd.append("image", opts.image);
    init.body = fd;
  }
  const res = await fetch(url, init);
  if (!res.ok) {
    const e = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((e as any).detail || "Ошибка публикации");
  }
  return res.json();
}
export const apiContentDelete = (id: number) => reqJSON<{ ok: boolean }>(`/api/content/delete?id=${id}`, "POST");
export const apiContentUpdate = (id: number, text: string) => postJSON(`/api/content/update?id=${id}`, { text });
export const apiContentCustom = (topic: string) => postJSON("/api/content/custom", { topic });
