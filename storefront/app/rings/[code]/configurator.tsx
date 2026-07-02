"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { TemplateDetail } from "./page";

type PriceResponse = {
  validity: { status: string; reasons: { code: string; message: string }[]; degraded: boolean };
  itemized?: Record<string, number>;
  total?: { amount_minor: number; currency: string };
  estimated_range?: { min: number; max: number; currency: string };
  non_returnable?: boolean;
  config_hash: string;
};

function money(minor: number, currency: string): string {
  return new Intl.NumberFormat("nl-NL", { style: "currency", currency }).format(minor / 100);
}

export function Configurator({
  template,
  initialSelections,
}: {
  template: TemplateDetail;
  initialSelections: Record<string, string> | null;
}) {
  const steps = useMemo(
    () => [...template.option_groups].sort((a, b) => a.step_order - b.step_order),
    [template.option_groups],
  );

  const [selections, setSelections] = useState<Record<string, string>>(() => {
    if (initialSelections) return initialSelections;
    const defaults: Record<string, string> = {};
    for (const g of steps) {
      const fallback = g.is_required ? g.options[0]?.code : undefined;
      const chosen = g.default_option_code ?? fallback;
      if (chosen) defaults[g.key] = chosen;
    }
    return defaults;
  });
  const [price, setPrice] = useState<PriceResponse | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const requestSeq = useRef(0);

  const fetchPrice = useCallback(
    async (current: Record<string, string>) => {
      const seq = ++requestSeq.current;
      const resp = await fetch("/api/engine/api/v1/config/price", {
        method: "POST",
        body: JSON.stringify({ template_id: template.id, selections: current }),
      });
      if (!resp.ok || seq !== requestSeq.current) return;
      setPrice(await resp.json());
    },
    [template.id],
  );

  useEffect(() => {
    fetchPrice(selections);
    setShareUrl(null);
  }, [fetchPrice, selections]);

  function choose(groupKey: string, optionCode: string) {
    setSelections((prev) => {
      const next = { ...prev };
      if (prev[groupKey] === optionCode && !isRequired(groupKey)) {
        delete next[groupKey]; // optional groups can be unselected
      } else {
        next[groupKey] = optionCode;
      }
      return next;
    });
  }

  function isRequired(groupKey: string): boolean {
    return steps.find((g) => g.key === groupKey)?.is_required ?? false;
  }

  async function share() {
    const resp = await fetch("/api/engine/api/v1/config/share", {
      method: "POST",
      body: JSON.stringify({ template_id: template.id, selections }),
    });
    if (!resp.ok) return;
    const { code } = await resp.json();
    const url = `${window.location.origin}/rings/${template.code}?c=${code}`;
    setShareUrl(url);
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      /* clipboard unavailable — the URL is still shown */
    }
  }

  const status = price?.validity.status;

  return (
    <div className="configurator">
      <div className="panel">
        {steps.map((group, index) => (
          <div className="step" key={group.key}>
            <h3>
              {index + 1}. {group.name}
              {!group.is_required && <span className="note"> (optional)</span>}
            </h3>
            <div className="choices">
              {group.options.map((option) => (
                <button
                  key={option.code}
                  className={`choice ${selections[group.key] === option.code ? "selected" : ""}`}
                  onClick={() => choose(group.key, option.code)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="panel">
        {!price && <p className="note">Calculating…</p>}
        {price && (
          <>
            {status === "purchasable" && price.total && (
              <>
                <div className="price-total">
                  {money(price.total.amount_minor, price.total.currency)}
                </div>
                <div className="price-status">
                  incl. VAT · made to order{price.validity.degraded ? " · price indicative" : ""}
                </div>
              </>
            )}
            {status === "quote_only" && (
              <>
                {price.estimated_range && (
                  <div className="price-total">
                    {money(price.estimated_range.min, price.estimated_range.currency)} –{" "}
                    {money(price.estimated_range.max, price.estimated_range.currency)}
                  </div>
                )}
                <div className="price-status">
                  estimated range — we&apos;ll confirm the exact price in a quote
                </div>
              </>
            )}
            {status === "invalid" && (
              <div>
                {price.validity.reasons.map((r, i) => (
                  <p className="reason" key={i}>
                    {r.message}
                  </p>
                ))}
              </div>
            )}

            {price.non_returnable && (
              <p className="note">
                This configuration is personalised and therefore not returnable.
              </p>
            )}

            {price.itemized && status !== "invalid" && (
              <table className="breakdown">
                <tbody>
                  {Object.entries(price.itemized).map(([component, minor]) => (
                    <tr key={component}>
                      <td>{component.replaceAll("_", " ")}</td>
                      <td>{money(minor, price.total?.currency ?? "EUR")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <p style={{ marginTop: "1.25rem" }}>
              <button className="cta" disabled={status !== "purchasable"}>
                {status === "purchasable" ? "Continue to order" : "Resolve selection first"}
              </button>{" "}
              <button className="cta secondary" onClick={share}>
                Share
              </button>
            </p>
            {status === "quote_only" && (
              <p>
                <button className="cta secondary">Request a quote</button>
              </p>
            )}
            {shareUrl && (
              <p className="note">
                Link copied: <code>{shareUrl}</code>
              </p>
            )}
            <p className="note">Ordering flow arrives with the checkout phase.</p>
          </>
        )}
      </div>
    </div>
  );
}
