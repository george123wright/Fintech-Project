import type { PortfolioNarrative } from "../types/api";

type Props = {
  narrative: PortfolioNarrative | null | undefined;
};

function toneColors(tone: string): { border: string; badge: string } {
  if (tone === "positive") {
    return { border: "rgba(61, 214, 140, 0.45)", badge: "rgba(61, 214, 140, 0.18)" };
  }
  if (tone === "negative") {
    return { border: "rgba(240, 91, 91, 0.45)", badge: "rgba(240, 91, 91, 0.16)" };
  }
  return { border: "rgba(123, 110, 246, 0.35)", badge: "rgba(123, 110, 246, 0.14)" };
}

export default function PortfolioNarrativePanel({ narrative }: Props) {
  if (!narrative?.cards?.length) return null;

  return (
    <div style={{ marginBottom: 24 }}>
      <div className="kicker" style={{ marginBottom: 10 }}>
        What matters right now
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
        {narrative.cards.map((card) => {
          const colors = toneColors(card.tone);
          return (
            <div
              key={card.id}
              className="surface-soft"
              style={{
                padding: 14,
                border: `1px solid ${colors.border}`,
                borderRadius: 14,
                display: "grid",
                gap: 10,
              }}
            >
              <div className="row-between" style={{ alignItems: "flex-start", gap: 8 }}>
                <div style={{ fontSize: 15, fontWeight: 700 }}>{card.title}</div>
                <span
                  style={{
                    padding: "4px 8px",
                    borderRadius: 999,
                    textTransform: "capitalize",
                    fontSize: 10,
                    background: colors.badge,
                    color: "var(--text)",
                    border: `1px solid ${colors.border}`,
                  }}
                >
                  {card.tone}
                </span>
              </div>
              <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.65 }}>{card.summary}</div>
              {card.evidence_chips?.length ? (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {card.evidence_chips.map((chip, idx) => (
                    <span
                      key={`${card.id}-${idx}-${chip.label}`}
                      style={{
                        border: "1px solid var(--border)",
                        borderRadius: 999,
                        padding: "4px 8px",
                        fontSize: 10,
                        color: "var(--muted)",
                      }}
                    >
                      {chip.label}: <strong style={{ color: "var(--text)" }}>{chip.value}</strong>
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
