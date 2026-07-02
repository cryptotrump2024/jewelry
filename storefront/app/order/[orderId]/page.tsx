import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { engineFetch } from "@/lib/engine";
import { money } from "@/lib/tenant";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Order confirmation",
  robots: { index: false },
};

type OrderDetail = {
  id: string;
  status: string;
  currency: string;
  totals: { total_minor: number; deposit_minor: number };
  items: { configuration: Record<string, string>; non_returnable: boolean }[];
  payments: { kind: string; status: string; amount_minor: number }[];
};

const STATUS_COPY: Record<string, string> = {
  awaiting_deposit: "Awaiting your deposit",
  in_production: "Deposit received — your ring is entering production",
  paid: "Paid in full",
};

export default async function OrderPage({
  params,
}: {
  params: Promise<{ orderId: string }>;
}) {
  const { orderId } = await params;
  let order: OrderDetail;
  try {
    order = await engineFetch<OrderDetail>(`/api/v1/orders/${orderId}`);
  } catch {
    notFound();
  }
  const item = order.items[0];

  return (
    <>
      <h1>Thank you</h1>
      <div className="panel" style={{ maxWidth: "560px" }}>
        <p>
          <strong>{STATUS_COPY[order.status] ?? order.status}</strong>
        </p>
        <p className="note">
          Order <code>{order.id}</code>
        </p>
        <table className="breakdown">
          <tbody>
            {item &&
              Object.entries(item.configuration).map(([group, option]) => (
                <tr key={group}>
                  <td>{group.replaceAll("_", " ")}</td>
                  <td>{String(option)}</td>
                </tr>
              ))}
            <tr>
              <td>
                <strong>Total</strong>
              </td>
              <td>
                <strong>{money(order.totals.total_minor, order.currency)}</strong>
              </td>
            </tr>
            {order.payments.map((p, i) => (
              <tr key={i}>
                <td>
                  {p.kind.replaceAll("_", " ")} ({p.status})
                </td>
                <td>{money(p.amount_minor, order.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {item?.non_returnable && (
          <p className="note">
            Personalised item — exempt from the right of withdrawal.
          </p>
        )}
        <p className="note">
          The balance is due before shipping. We&apos;ll keep you updated by
          email as production progresses.
        </p>
      </div>
    </>
  );
}
