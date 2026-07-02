import { ImportForm } from "./form";

export default function ImportsPage() {
  return (
    <>
      <h1>Diamond price import</h1>
      <p style={{ color: "var(--muted)" }}>
        Paste CSV with columns: stone_type, shape, carat_min, carat_max, color,
        clarity, price_per_carat, currency. Always dry-run first — commit is
        idempotent (re-importing the same file changes nothing).
      </p>
      <ImportForm />
    </>
  );
}
