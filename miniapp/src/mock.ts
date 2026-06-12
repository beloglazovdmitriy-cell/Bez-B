// Мок-данные портфеля для прототипа. Структура повторяет то, что отдаст
// будущий API (portfolio.summary()), поэтому экраны потом подключатся без переделки.

export interface Position {
  ticker: string;
  valueUsd: number;
  avgPrice: number;
  priceNow: number;
  profitPct: number;
  color: string;
}

export interface Summary {
  totalUsd: number;
  totalRub: number;
  profitUsdPct: number;
  profitRubPct: number;
  index: number;
  cashUsdt: number;
  positions: Position[];
}

export const mockSummary: Summary = {
  totalUsd: 6338.75,
  totalRub: 455053.96,
  profitUsdPct: 8.1,
  profitRubPct: 12.4,
  index: 118.3,
  cashUsdt: 612.4,
  positions: [
    { ticker: "BTC", valueUsd: 2220.5, avgPrice: 61650, priceNow: 79010, profitPct: 28.1, color: "#f7931a" },
    { ticker: "ETH", valueUsd: 1010.0, avgPrice: 1628, priceNow: 1726, profitPct: 6.0, color: "#627eea" },
    { ticker: "TSLA", valueUsd: 980.3, avgPrice: 381.5, priceNow: 366.0, profitPct: -4.1, color: "#e82127" },
    { ticker: "NVDA", valueUsd: 760.0, avgPrice: 118.0, priceNow: 131.2, profitPct: 11.2, color: "#76b900" },
    { ticker: "GDX", valueUsd: 755.5, avgPrice: 73.8, priceNow: 79.4, profitPct: 7.6, color: "#d4af37" },
  ],
};

// История стоимости (₽) и индекса — для экрана «Динамика».
export interface HistoryPoint { date: string; value: number; invested: number; index: number; }
export const mockHistory: HistoryPoint[] = [
  { date: "01.04", value: 405000, invested: 405000, index: 100.0 },
  { date: "08.04", value: 398000, invested: 410000, index: 98.3 },
  { date: "15.04", value: 421000, invested: 415000, index: 103.1 },
  { date: "22.04", value: 430000, invested: 420000, index: 105.4 },
  { date: "29.04", value: 419000, invested: 425000, index: 102.0 },
  { date: "06.05", value: 441000, invested: 430000, index: 107.8 },
  { date: "13.05", value: 458000, invested: 435000, index: 111.9 },
  { date: "20.05", value: 449000, invested: 438000, index: 109.2 },
  { date: "27.05", value: 467000, invested: 442000, index: 113.6 },
  { date: "03.06", value: 472000, invested: 445000, index: 115.4 },
  { date: "10.06", value: 455054, invested: 448000, index: 118.3 },
];

// Сравнение с рынком — для блока «Без Б против рынка».
export interface BenchRow { name: string; retRubPct: number; isMe?: boolean; }
export const mockBench: BenchRow[] = [
  { name: "Портфель Без Б", retRubPct: 12.4, isMe: true },
  { name: "Bitcoin", retRubPct: 9.8 },
  { name: "S&P 500", retRubPct: 6.1 },
  { name: "Золото", retRubPct: 4.3 },
  { name: "Вклад ₽ (18%)", retRubPct: 3.0 },
  { name: "Доллар (кэш)", retRubPct: 1.2 },
];

// Журнал сделок — для ленты-дневника.
export interface JournalEntry {
  date: string;
  side: "buy" | "sell";
  ticker: string;
  amountUsd: number;
  price: number;
  sharePct: number;
  reason: string;
}
export const mockJournal: JournalEntry[] = [
  { date: "10.06", side: "buy", ticker: "BTC", amountUsd: 300, price: 79010, sharePct: 35, reason: "Плановая закупка (DCA)" },
  { date: "06.06", side: "buy", ticker: "NVDA", amountUsd: 250, price: 131.2, sharePct: 12, reason: "Долгосрочный тренд" },
  { date: "27.05", side: "sell", ticker: "TSLA", amountUsd: 200, price: 366.0, sharePct: 16, reason: "Ребаланс портфеля" },
  { date: "20.05", side: "buy", ticker: "ETH", amountUsd: 250, price: 1726, sharePct: 16, reason: "Докупка на просадке" },
  { date: "13.05", side: "buy", ticker: "GDX", amountUsd: 300, price: 79.4, sharePct: 12, reason: "Свободный кэш" },
];

// Пользователь прототипа (в реальности — из Telegram initData).
export const mockUser = { name: "Дмитрий", isAdmin: true, isPremium: false };
