import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { engineFetch } from "@/lib/engine";
import { getTenant } from "@/lib/tenant";
import { Configurator } from "./configurator";

export type TemplateDetail = {
  id: string;
  code: string;
  name: string;
  style: string | null;
  components: { kind: string; name: string }[];
  option_groups: {
    key: string;
    name: string;
    step_order: number;
    is_required: boolean;
    default_option_code: string | null;
    options: { code: string; label: string }[];
  }[];
};

export const dynamic = "force-dynamic";

async function loadTemplate(code: string): Promise<TemplateDetail | null> {
  try {
    return await engineFetch<TemplateDetail>(`/api/v1/templates/by-code/${code}`);
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code } = await params;
  const template = await loadTemplate(code);
  if (!template) return {};
  return {
    title: `${template.name} — configure your engagement ring`,
    description: `Configure the ${template.name}: metal, diamond, carat and size with instant transparent pricing. Made to order.`,
    alternates: { canonical: `/rings/${template.code}` },
  };
}

export default async function RingPage({
  params,
  searchParams,
}: {
  params: Promise<{ code: string }>;
  searchParams: Promise<{ c?: string }>;
}) {
  const { code } = await params;
  const { c: shareCode } = await searchParams;
  const template = await loadTemplate(code);
  if (!template) notFound();

  // Shared configuration (?c=...) reproduces the exact selection (07 §9.6).
  let initialSelections: Record<string, string> | null = null;
  if (shareCode) {
    try {
      const shared = await engineFetch<{ selections: Record<string, string> }>(
        `/api/v1/config/${shareCode}`,
      );
      initialSelections = shared.selections;
    } catch {
      initialSelections = null;
    }
  }

  const tenant = await getTenant();

  // SEO fundamentals ship with the page (Phase 7): ProductGroup JSON-LD from
  // engine data. The full variant/offer layer (indexable_configurations)
  // arrives in Phase 9.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ProductGroup",
    name: template.name,
    productGroupID: template.code,
    brand: { "@type": "Brand", name: tenant.brandName },
    category: "Engagement Rings",
    variesBy: template.option_groups.map((g) => g.name),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <h1>{template.name}</h1>
      {template.style && <p className="note">Style: {template.style} · made to order</p>}
      <Configurator template={template} initialSelections={initialSelections} />
    </>
  );
}
