import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { engineFetch } from "@/lib/engine";
import { money } from "@/lib/tenant";
import { CheckoutForm } from "./form";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Checkout",
  robots: { index: false },
};

type QuoteDetail = {
  id: string;
  status: string;
  expires_at: string | null;
  configuration: {
    selections: Record<string, string>;
    non_returnable?: boolean;
  };
  total: { amount_minor: number; currency: string };
  itemized: Record<string, number>;
};

export default async function CheckoutPage({
  params,
}: {
  params: Promise<{ quoteId: string }>;
}) {
  const { quoteId } = await params;
  let quote: QuoteDetail;
  try {
    quote = await engineFetch<QuoteDetail>(`/api/v1/quotes/${quoteId}`);
  } catch {
    notFound();
  }
  if (quote.status !== "open") notFound();

  const deposit = Math.ceil(quote.total.amount_minor / 2);

  return (
    <>
      <h1>Your order</h1>
      <div className="configurator">
        <div className="panel">
          <h3>Configuration</h3>
          <table className="breakdown">
            <tbody>
              {Object.entries(quote.configuration.selections).map(([group, option]) => (
                <tr key={group}>
                  <td>{group.replaceAll("_", " ")}</td>
                  <td>{String(option)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3 style={{ marginTop: "1.25rem" }}>Price</h3>
          <table className="breakdown">
            <tbody>
              {Object.entries(quote.itemized).map(([component, minor]) => (
                <tr key={component}>
                  <td>{component.replaceAll("_", " ")}</td>
                  <td>{money(minor, quote.total.currency)}</td>
                </tr>
              ))}
              <tr>
                <td>
                  <strong>Total (incl. VAT)</strong>
                </td>
                <td>
                  <strong>{money(quote.total.amount_minor, quote.total.currency)}</strong>
                </td>
              </tr>
              <tr>
                <td>Production deposit due now (50%)</td>
                <td>{money(deposit, quote.total.currency)}</td>
              </tr>
            </tbody>
          </table>
          {quote.configuration.non_returnable && (
            <p className="note">
              This configuration is personalised and therefore exempt from the
              right of withdrawal.
            </p>
          )}
          <p className="note">
            The remaining balance is due before shipping. Your price is locked
            from this point — later metal-market moves do not affect it.
          </p>
        </div>
        <div className="panel">
          <h3>Your details</h3>
          <CheckoutForm quoteId={quote.id} />
        </div>
      </div>
    </>
  );
}
