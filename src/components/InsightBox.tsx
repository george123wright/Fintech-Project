type Props = {
  text: string;
};

export default function InsightBox({ text }: Props) {
  return (
    <div className="insight">
      <span style={{ color: "var(--accent)" }}>Lens Analysis - </span>
      <span>{text}</span>
    </div>
  );
}
