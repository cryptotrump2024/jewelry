// Brand/display config comes from the engine's tenant settings — the engine
// never hardcodes brand or domain (open decision #1), and neither do we.

import { engineFetch } from "@/lib/engine";

type TenantMe = {
  tenant_id: string;
  slug: string;
  settings: {
    branding?: { display_name?: string };
    defaults?: { market?: string; locale?: string; currency?: string };
  };
};

export async function getTenant(): Promise<{
  brandName: string;
  market: string;
  currency: string;
}> {
  try {
    const me = await engineFetch<TenantMe>("/tenant/me");
    return {
      brandName: me.settings.branding?.display_name ?? "Atelier",
      market: me.settings.defaults?.market ?? "NL",
      currency: me.settings.defaults?.currency ?? "EUR",
    };
  } catch {
    return { brandName: "Atelier", market: "NL", currency: "EUR" };
  }
}

export function money(minor: number, currency: string): string {
  return new Intl.NumberFormat("nl-NL", { style: "currency", currency }).format(minor / 100);
}
