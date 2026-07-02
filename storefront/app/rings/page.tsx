import type { Metadata } from "next";
import Link from "next/link";
import { engineFetch } from "@/lib/engine";

type TemplateRow = { id: string; code: string; name: string; style: string | null };

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Engagement rings",
  description:
    "Configurable engagement rings, made to order. Choose metal, diamond and size with live transparent pricing.",
};

export default async function RingsPage() {
  const templates = await engineFetch<TemplateRow[]>(
    "/api/v1/templates?category=engagement-ring",
  );
  return (
    <>
      <h1>Engagement rings</h1>
      <p className="note">
        Every ring is made to order. Configure yours — the price updates
        instantly and shows exactly what you pay for.
      </p>
      <div className="grid">
        {templates.map((t) => (
          <Link key={t.id} className="tile" href={`/rings/${t.code}`}>
            <strong>{t.name}</strong>
            {t.style && <div className="style">{t.style}</div>}
          </Link>
        ))}
        {templates.length === 0 && <p>The collection is being prepared.</p>}
      </div>
    </>
  );
}
