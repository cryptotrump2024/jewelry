"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function MockPay({
  paymentId,
  orderId,
}: {
  paymentId: string;
  orderId: string | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pay() {
    setBusy(true);
    setError(null);
    const resp = await fetch(`/api/engine/api/v1/payments/${paymentId}/mock-complete`, {
      method: "POST",
    });
    setBusy(false);
    if (!resp.ok) {
      setError("Payment failed — please try again.");
      return;
    }
    router.push(orderId ? `/order/${orderId}` : "/");
  }

  return (
    <>
      <button className="cta" onClick={pay} disabled={busy}>
        {busy ? "Processing…" : "Pay deposit now"}
      </button>
      {error && <p className="reason">{error}</p>}
    </>
  );
}
