"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type Group = {
  key: string;
  name: string;
  is_required: boolean;
  options: { code: string; label: string; is_active: boolean }[];
};

type PreviewResponse = {
  validation: { status: string; reasons: { code: string; message: string }[] };
  price: {
    status: string;
    currency: string;
    total_minor: number | null;
    range_min_minor: number | null;
    range_max_minor: number | null;
    itemized: Record<string, number>;
    reasons: { code: string; message: string }[];
    degraded: boolean;
    non_returnable: boolean;
  } | null;
};

function money(minor: number, currency: string): string {
  return new Intl.NumberFormat("nl-NL", { style: "currency", currency }).format(minor / 100);
}

export function PricePreview({
  templateId,
  groups,
}: {
  templateId: string;
  groups: Group[];
}) {
  const usable = useMemo(
    () => groups.filter((g) => g.options.some((o) => o.is_active)),
    [groups],
  );
  const [selections, setSelections] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      usable.map((g) => [g.key, g.options.find((o) => o.is_active)?.code ?? ""]),
    ),
  );
  const [result, setResult] = useState<PreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchPreview = useCallback(
    async (current: Record<string, string>) => {
      const resp = await fetch(`/api/engine/admin/templates/${templateId}/price-preview`, {
        method: "POST",
        body: JSON.stringify({ selections: current }),
      });
      if (!resp.ok) {
        setError(`preview failed (${resp.status})`);
        setResult(null);
        return;
      }
      setError(null);
      setResult(await resp.json());
    },
    [templateId],
  );

  useEffect(() => {
    fetchPreview(selections);
  }, [fetchPreview, selections]);

  const price = result?.price ?? null;
  const validation = result?.validation ?? null;

  return (
    <div className="card">
      <h2>Live price preview</h2>
      <div className="row" style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {usable.map((g) => (
          <label key={g.key} style={{ display: "grid", fontSize: "0.8rem", gap: "0.15rem" }}>
            {g.name}
            <select
              value={selections[g.key] ?? ""}
              onChange={(e) =>
                setSelections((prev) => ({ ...prev, [g.key]: e.target.value }))
              }
            >
              {!g.is_required && <option value="">—</option>}
              {g.options
                .filter((o) => o.is_active)
                .map((o) => (
                  <option key={o.code} value={o.code}>
                    {o.label}
                  </option>
                ))}
            </select>
          </label>
        ))}
      </div>

      {error && <p className="error">{error}</p>}

      {validation && validation.status === "invalid" && (
        <div style={{ marginTop: "1rem" }}>
          <span className="badge" style={{ color: "var(--danger)" }}>
            invalid
          </span>
          <ul>
            {validation.reasons.map((r, i) => (
              <li key={i} className="error">
                {r.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {price && validation?.status !== "invalid" && (
        <div style={{ marginTop: "1rem" }}>
          <p>
            <span className={`badge ${price.status === "purchasable" ? "published" : "draft"}`}>
              {price.status}
            </span>{" "}
            {price.total_minor != null && (
              <strong style={{ fontSize: "1.2rem" }}>
                {money(price.total_minor, price.currency)}
              </strong>
            )}
            {price.total_minor == null &&
              price.range_min_minor != null &&
              price.range_max_minor != null && (
                <strong>
                  {money(price.range_min_minor, price.currency)} –{" "}
                  {money(price.range_max_minor, price.currency)} (estimate)
                </strong>
              )}
            {price.non_returnable && <span className="badge"> non-returnable</span>}
          </p>
          {price.reasons.length > 0 && (
            <ul>
              {price.reasons.map((r, i) => (
                <li key={i} style={{ color: "var(--muted)" }}>
                  {r.message}
                </li>
              ))}
            </ul>
          )}
          <table style={{ marginTop: "0.5rem" }}>
            <tbody>
              {Object.entries(price.itemized).map(([component, minor]) => (
                <tr key={component}>
                  <td>{component.replaceAll("_", " ")}</td>
                  <td style={{ textAlign: "right" }}>{money(minor, price.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
