import { useEffect, useState } from "react";
import { apiAnalyze, type Pf } from "../data";
import { IconAI } from "./Icons";

// Окно AI-разбора портфеля: при открытии запрашивает разбор и показывает текст.
export default function AnalysisSheet({ pf, onClose }: { pf: Pf; onClose: () => void }) {
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    apiAnalyze(pf)
      .then((t) => alive && setText(t))
      .catch((e) => alive && setErr((e as Error).message))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [pf]);

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grip" />
        <div className="sheet-title"><IconAI size={20} /> AI-разбор портфеля</div>

        {loading && <div className="muted-note">Анализирую портфель…</div>}
        {err && <div className="form-error">{err}</div>}
        {text && <div className="ai-text">{text}</div>}

        <button className="sheet-cancel" onClick={onClose}>Закрыть</button>
      </div>
    </div>
  );
}
