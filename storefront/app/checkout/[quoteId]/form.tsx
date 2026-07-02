"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function CheckoutForm({ quoteId }: { quoteId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(event.currentTarget);

    const orderResp = await fetch("/api/engine/api/v1/orders", {
      method: "POST",
      body: JSON.stringify({
        quote_id: quoteId,
        customer: { email: form.get("email"), name: form.get("name") },
      }),
    });
    if (!orderResp.ok) {
      const body = await orderResp.json().catch(() => null);
      setError(body?.detail ?? "Could not create the order.");
      setBusy(false);
      return;
    }
    const order = await orderResp.json();

    const intentResp = await fetch("/api/engine/api/v1/payments/intent", {
      method: "POST",
      body: JSON.stringify({ order_id: order.id, kind: "deposit_production" }),
    });
    if (!intentResp.ok) {
      setError("Could not start the payment.");
      setBusy(false);
      return;
    }
    const intent = await intentResp.json();
    router.push(`/checkout/pay/${intent.payment_id}?order=${order.id}`);
  }

  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: "0.75rem" }}>
      <label>
        Name
        <br />
        <input name="name" required style={{ width: "100%" }} className="choice" />
      </label>
      <label>
        Email
        <br />
        <input
          name="email"
          type="email"
          required
          style={{ width: "100%" }}
          className="choice"
        />
      </label>
      <button className="cta" disabled={busy}>
        {busy ? "Preparing payment…" : "Pay deposit"}
      </button>
      {error && <p className="reason">{error}</p>}
      <p className="note">
        Payment is processed by our payment provider; we never see your card
        details.
      </p>
    </form>
  );
}
