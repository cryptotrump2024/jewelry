"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { PricingConfig } from "./page";

async function put(path: string, body: unknown): Promise<string | null> {
  const resp = await fetch(`/api/engine${path}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return resp.ok ? null : await resp.text();
}

function Row({
  label,
  defaultValue,
  onSave,
  suffix,
}: {
  label: string;
  defaultValue: string;
  onSave: (value: string) => Promise<string | null>;
  suffix?: string;
}) {
  const [value, setValue] = useState(defaultValue);
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setState("saving");
    const err = await onSave(value);
    if (err) {
      setError(err);
      setState("error");
    } else {
      setError(null);
      setState("saved");
      setTimeout(() => setState("idle"), 1500);
    }
  }

  return (
    <tr>
      <td>{label}</td>
      <td>
        <input value={value} onChange={(e) => setValue(e.target.value)} style={{ width: "8rem" }} />{" "}
        {suffix}
      </td>
      <td>
        <button className="secondary" onClick={save} disabled={state === "saving"}>
          {state === "saved" ? "Saved ✓" : "Save"}
        </button>
        {state === "error" && <span className="error"> {error}</span>}
      </td>
    </tr>
  );
}

export function PricingEditor({ config }: { config: PricingConfig }) {
  const router = useRouter();
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null);

  async function refreshMetals() {
    const resp = await fetch("/api/engine/admin/pricing/refresh-metals", { method: "POST" });
    const body = await resp.json();
    setRefreshMsg(
      resp.ok ? `${body.snapshots_written} prices refreshed` : "refresh failed",
    );
    router.refresh();
  }

  return (
    <>
      <div className="card">
        <h2>Labor</h2>
        <table>
          <tbody>
            {config.labor.map((row) => (
              <Row
                key={row.id}
                label={`${row.operation} (${row.basis.replaceAll("_", " ")})`}
                defaultValue={(row.amount_minor / 100).toFixed(2)}
                suffix={row.currency}
                onSave={(v) =>
                  put(`/admin/pricing/labor/${row.id}`, {
                    amount_minor: Math.round(parseFloat(v) * 100),
                  })
                }
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Margin</h2>
        <table>
          <tbody>
            {config.margins.map((row) => (
              <Row
                key={row.id}
                label={row.market ?? "tenant default"}
                defaultValue={row.value}
                suffix={row.type === "percent" ? "(fraction, e.g. 0.60 = 60%)" : "fixed"}
                onSave={(v) => put(`/admin/pricing/margins/${row.id}`, { value: v })}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Buffers</h2>
        <table>
          <tbody>
            {config.buffers.map((row) => (
              <Row
                key={row.id}
                label={row.kind.replaceAll("_", " ")}
                defaultValue={row.value}
                suffix={row.type === "percent" ? "(fraction)" : "minor units"}
                onSave={(v) => put(`/admin/pricing/buffers/${row.id}`, { value: v })}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>VAT</h2>
        <table>
          <tbody>
            {config.vat_rules.map((row) => (
              <Row
                key={row.id}
                label={`${row.market} ${row.price_includes_vat ? "(inclusive)" : "(exclusive)"}`}
                defaultValue={row.rate}
                suffix="(fraction, e.g. 0.21)"
                onSave={(v) => put(`/admin/pricing/vat/${row.id}`, { rate: v })}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Metal prices</h2>
        <table>
          <thead>
            <tr>
              <th>Metal</th>
              <th>€/g</th>
              <th>Source</th>
              <th>Fetched</th>
            </tr>
          </thead>
          <tbody>
            {config.latest_metal_prices.map((p, i) => (
              <tr key={i}>
                <td>
                  {p.metal}
                  {p.karat ? ` ${p.karat}k` : ""}
                </td>
                <td>{p.price_per_gram}</td>
                <td>{p.source}</td>
                <td>{new Date(p.fetched_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>
          <button className="secondary" onClick={refreshMetals}>
            Refresh now
          </button>
          {refreshMsg && <span style={{ color: "var(--muted)" }}> {refreshMsg}</span>}
        </p>
      </div>
    </>
  );
}
