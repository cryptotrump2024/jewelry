import { engineFetch } from "@/lib/engine";
import { PricingEditor } from "./editor";

export const dynamic = "force-dynamic";

export type PricingConfig = {
  labor: {
    id: string;
    operation: string;
    basis: string;
    amount_minor: number;
    currency: string;
  }[];
  margins: {
    id: string;
    template_id: string | null;
    market: string | null;
    type: string;
    value: string;
  }[];
  buffers: { id: string; kind: string; type: string; value: string; currency: string | null }[];
  vat_rules: { id: string; market: string; rate: string; price_includes_vat: boolean }[];
  latest_metal_prices: {
    metal: string;
    karat: number | null;
    price_per_gram: string;
    currency: string;
    source: string;
    fetched_at: string;
  }[];
};

export default async function PricingPage() {
  const config = await engineFetch<PricingConfig>("/admin/pricing/config");
  return (
    <>
      <h1>Pricing configuration</h1>
      <p style={{ color: "var(--muted)" }}>
        Every number the pricing engine uses. Edits apply to new price
        computations immediately; historical orders keep their snapshots.
      </p>
      <PricingEditor config={config} />
    </>
  );
}
