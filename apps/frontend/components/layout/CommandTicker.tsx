const ITEMS = [
  "BAKKE NEVER DETERMINES WHAT HAPPENED",
  "SCORES ARE EVIDENCE CONSISTENCY ONLY — NOT PROBABILITY",
  "SIMILAR CASES ARE REFERENCE ONLY — NEVER INJECTED AS FACT",
  "VIDEOS ARE 3D ANIMATED RECONSTRUCTIONS — NOT RECORDED FOOTAGE",
  "EVERY STEP IS AUDITED",
];

export function CommandTicker() {
  const row = ITEMS.map((t, i) => (
    <span
      key={i}
      className="mx-6 inline-flex items-center gap-2 whitespace-nowrap text-[10px] uppercase tracking-[0.22em] text-[#3f5575]"
    >
      <span aria-hidden="true" className="text-[#4cc9f0]/50">▸</span> {t}
    </span>
  ));
  return (
    <div className="relative overflow-hidden border-b border-[#0d1c38] bg-[#04070f]">
      <div className="ticker">
        <div className="flex">{row}</div>
        <div className="flex" aria-hidden="true">
          {row}
        </div>
      </div>
    </div>
  );
}
