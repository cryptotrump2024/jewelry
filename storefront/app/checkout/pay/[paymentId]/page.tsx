import type { Metadata } from "next";
import { MockPay } from "./mock-pay";

export const metadata: Metadata = {
  title: "Payment",
  robots: { index: false },
};

export default async function PayPage({
  params,
  searchParams,
}: {
  params: Promise<{ paymentId: string }>;
  searchParams: Promise<{ order?: string }>;
}) {
  const { paymentId } = await params;
  const { order } = await searchParams;
  return (
    <>
      <h1>Deposit payment</h1>
      <div className="panel" style={{ maxWidth: "480px" }}>
        <p className="note">
          Sandbox payment — the live payment provider (iDEAL, cards) is
          connected at launch. Completing this behaves exactly like a real
          payment.
        </p>
        <MockPay paymentId={paymentId} orderId={order ?? null} />
      </div>
    </>
  );
}
