import { useEffect, useState } from "react";
import {
  loadSummary, loadHistory, loadBench, loadJournal, loadUser,
  type Summary, type HistoryPoint, type BenchRow, type JournalEntry, type Pf,
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
export function useAppData(pf: Pf): AppData {
  const [summary, setSummary] = useState<Summary>(mockSummary);
  const [history, setHistory] = useState<HistoryPoint[]>(mockHistory);
  const [bench, setBench] = useState<BenchRow[]>(mockBench);
  const [journal, setJournal] = useState<JournalEntry[]>(mockJournal);
  const [user, setUser] = useState(mockUser);
  const [loading, setLoading] = useState(true);

  // Грузим независимо (быстрые данные не ждут медленные котировки). user не зависит
  // от портфеля; остальное перечитывается при смене выбранного портфеля pf.
  function refresh() {
    loadUser().then(setUser).catch(() => {});
    loadSummary(pf).then(setSummary).catch(() => {});
    loadHistory(pf).then(setHistory).catch(() => {});
    loadBench(pf).then(setBench).catch(() => {});
    loadJournal(pf).then(setJournal).catch(() => {}).finally(() => setLoading(false));
  }

  useEffect(() => { refresh(); }, [pf]);

  return { summary, history, bench, journal, user, loading, reload: refresh };
}
