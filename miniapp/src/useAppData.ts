import { useEffect, useState } from "react";
import {
  loadSummary, loadHistory, loadBench, loadJournal, loadUser,
  type Summary, type HistoryPoint, type BenchRow, type JournalEntry,
} from "./data";
import {
  mockSummary, mockHistory, mockBench, mockJournal, mockUser,
} from "./mock";

export interface AppData {
  summary: Summary;
  history: HistoryPoint[];
  bench: BenchRow[];
  journal: JournalEntry[];
  user: typeof mockUser;
  loading: boolean;
  reload: () => void;
}

// Стартуем с мок-данных (чтобы не было мигания пустотой), затем подменяем
// реальными из API. Если API недоступен — мок и остаётся.
export function useAppData(): AppData {
  const [summary, setSummary] = useState<Summary>(mockSummary);
  const [history, setHistory] = useState<HistoryPoint[]>(mockHistory);
  const [bench, setBench] = useState<BenchRow[]>(mockBench);
  const [journal, setJournal] = useState<JournalEntry[]>(mockJournal);
  const [user, setUser] = useState(mockUser);
  const [loading, setLoading] = useState(true);

  // Грузим независимо: кто кто узнан владелец (user) и быстрые данные не должны
  // ждать медленные котировки (/api/summary, /api/compare). Иначе вкладка «Сделки»
  // (зависит от user.isAdmin) появляется только после самого медленного запроса.
  function refresh() {
    loadUser().then(setUser).catch(() => {});
    loadSummary().then(setSummary).catch(() => {});
    loadHistory().then(setHistory).catch(() => {});
    loadBench().then(setBench).catch(() => {});
    loadJournal().then(setJournal).catch(() => {}).finally(() => setLoading(false));
  }

  useEffect(() => { refresh(); }, []);

  return { summary, history, bench, journal, user, loading, reload: refresh };
}
