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

  useEffect(() => {
    let alive = true;
    Promise.all([loadSummary(), loadHistory(), loadBench(), loadJournal(), loadUser()])
      .then(([s, h, b, j, u]) => {
        if (!alive) return;
        setSummary(s); setHistory(h); setBench(b); setJournal(j); setUser(u);
      })
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, []);

  return { summary, history, bench, journal, user, loading };
}
