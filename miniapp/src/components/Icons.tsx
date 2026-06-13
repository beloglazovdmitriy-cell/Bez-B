// Набор SVG-иконок «Без Б». Все рисуются текущим цветом (currentColor),
// поэтому красятся через CSS color. Линейный стиль, viewBox 24×24.
type P = { size?: number; className?: string };

const base = (size: number, className?: string) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  className,
});

export const IconPortfolio = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <path d="M21 12a9 9 0 1 1-9-9v9z" />
    <path d="M21 12A9 9 0 0 0 12 3v9z" />
  </svg>
);

export const IconChart = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <path d="M3 3v18h18" />
    <path d="M7 14l4-4 3 3 5-6" />
  </svg>
);

export const IconJournal = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" />
    <path d="M8 7h7M8 11h7" />
  </svg>
);

export const IconTrade = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v8M8 12h8" />
  </svg>
);

export const IconProfile = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
  </svg>
);

export const IconCopy = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15V5a2 2 0 0 1 2-2h10" />
  </svg>
);

export const IconShare = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <circle cx="18" cy="5" r="3" />
    <circle cx="6" cy="12" r="3" />
    <circle cx="18" cy="19" r="3" />
    <path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" />
  </svg>
);

export const IconBell = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.7 21a2 2 0 0 1-3.4 0" />
  </svg>
);

export const IconLock = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <rect x="4" y="11" width="16" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </svg>
);

export const IconCheck = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <path d="M20 6L9 17l-5-5" />
  </svg>
);

export const IconCrown = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <path d="M3 7l4 4 5-7 5 7 4-4-2 13H5z" />
  </svg>
);

export const IconChannel = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <path d="M22 3L2 11l6 2 2 6 4-5 5 4z" />
  </svg>
);

export const IconArrowDown = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <path d="M12 5v14M19 12l-7 7-7-7" />
  </svg>
);

export const IconArrowUp = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <path d="M12 19V5M5 12l7-7 7 7" />
  </svg>
);

export const IconWallet = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <path d="M3 7a2 2 0 0 1 2-2h14v4" />
    <path d="M3 7v10a2 2 0 0 0 2 2h15V9H5a2 2 0 0 1-2-2z" />
    <circle cx="16" cy="14" r="1.3" fill="currentColor" stroke="none" />
  </svg>
);

export const IconChevron = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <path d="M9 6l6 6-6 6" />
  </svg>
);

// Бренд-знак «Без Б»: монета цвета бренда с кириллической «Б» и вертикальными
// штрихами в духе ₿ — узнаваемо по-крипто, но это «Без Б», а не биткоин.
export const IconLogo = ({ size = 24, className }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" className={className}>
    <circle cx="12" cy="12" r="11.5" fill="#26a69a" />
    <g fill="#0e1117">
      <rect x="9.0" y="3.6" width="1.5" height="3.2" rx="0.5" />
      <rect x="12.2" y="3.6" width="1.5" height="3.2" rx="0.5" />
      <rect x="9.0" y="17.2" width="1.5" height="3.2" rx="0.5" />
      <rect x="12.2" y="17.2" width="1.5" height="3.2" rx="0.5" />
      <text x="11.6" y="12.6" textAnchor="middle" dominantBaseline="central"
        fontFamily="Arial, Helvetica, sans-serif" fontSize="13.5" fontWeight="700">Б</text>
    </g>
  </svg>
);

// Единый бренд-знак как в шапке: «Bez» + монета-логотип в роли «Б».
// Используется везде вместо текстовых «Без Б» / «@BezBlogfin».
export const Brand = ({ size = 15, className }: { size?: number; className?: string }) => (
  <span className={"brand-inline" + (className ? " " + className : "")}>
    Bez <IconLogo size={size} className="brand-btc" />
  </span>
);

export const IconScenario = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <circle cx="5" cy="12" r="2" />
    <path d="M7 12h4" />
    <path d="M11 12c4 0 4-6 8-6M11 12c4 0 4 6 8 6" />
    <circle cx="20" cy="6" r="1.6" />
    <circle cx="20" cy="18" r="1.6" />
  </svg>
);

export const IconAI = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <path d="M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8z" />
    <path d="M18 14l.9 2.1L21 17l-2.1.9L18 20l-.9-2.1L15 17l2.1-.9z" />
  </svg>
);

export const IconCalc = ({ size = 24, className }: P) => (
  <svg {...base(size, className)}>
    <rect x="4" y="3" width="16" height="18" rx="2" />
    <path d="M8 7h8" />
    <path d="M8 11h2M12 11h2M16 11h0.01M8 15h2M12 15h2M16 15h0.01M8 18h2" />
  </svg>
);

// Логотип Bitcoin (заливка, фирменный оранжевый). Без stroke — отдельный svg.
export const IconBitcoin = ({ size = 24, className }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" className={className} fill="#f7931a">
    <path d="M23.638 14.904c-1.602 6.43-8.113 10.34-14.542 8.736C2.67 22.05-1.244 15.525.362 9.105 1.962 2.67 8.475-1.243 14.9.358c6.43 1.605 10.342 8.115 8.738 14.548v-.002zm-6.35-4.613c.24-1.59-.974-2.45-2.64-3.03l.54-2.153-1.315-.328-.525 2.107c-.345-.087-.705-.167-1.064-.25l.526-2.127-1.32-.33-.54 2.165c-.285-.067-.565-.132-.84-.2l-1.815-.45-.35 1.407s.974.225.955.236c.535.136.63.486.615.766l-1.477 5.92c-.075.18-.24.45-.614.35.015.02-.96-.24-.96-.24l-.66 1.51 1.71.426.93.242-.54 2.19 1.32.327.54-2.17c.36.1.705.19 1.05.273l-.51 2.154 1.32.33.545-2.19c2.24.427 3.93.257 4.64-1.774.57-1.637-.03-2.58-1.217-3.196.854-.193 1.5-.76 1.68-1.93h.01zm-3.01 4.22c-.404 1.64-3.157.75-4.05.53l.72-2.9c.896.23 3.757.67 3.33 2.37zm.41-4.24c-.37 1.49-2.662.735-3.405.55l.654-2.64c.744.18 3.137.52 2.75 2.084v.006z" />
  </svg>
);
