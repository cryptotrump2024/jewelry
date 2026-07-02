"use client";

import { useState } from "react";

type ImportReport = {
  job_id: string;
  dry_run: boolean;
  status: string;
  stats: { rows: number; ok: number; errors: number; created: number; updated: number };
  rows: { status: string; raw: Record<string, string>; messages: { errors: string[] } | null }[];
};

const EXAMPLE = `stone_type,shape,carat_min,carat_max,color,clarity,price_per_carat,currency
lab_diamond,oval,0.30,0.49,G,SI1,800,EUR
lab_diamond,oval,0.50,0.69,G,SI1,950,EUR`;

export function ImportForm() {
  const [csv, setCsv] = useState("");
  const [report, setReport] = useState<ImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(dryRun: boolean) {
    setBusy(true);
    setError(null);
    const resp = await fetch("/api/engine/admin/pricing/imports/diamond-prices", {
      method: "POST",
      body: JSON.stringify({ csv_text: csv, dry_run: dryRun }),
    });
    setBusy(false);
    if (!resp.ok) {
      setError(await resp.text());
      return;
    }
    setReport(await resp.json());
  }

  return (
    <>
      <div className="card">
        <textarea
          value={csv}
          onChange={(e) => setCsv(e.target.value)}
          placeholder={EXAMPLE}
          rows={10}
          style={{
            width: "100%",
            fontFamily: "ui-monospace, monospace",
            fontSize: "0.85rem",
            padding: "0.6rem",
            border: "1px solid var(--border)",
            borderRadius: "6px",
          }}
        />
        <p>
          <button className="secondary" onClick={() => run(true)} disabled={busy || !csv.trim()}>
            Dry run
          </button>{" "}
          <button
            onClick={() => run(false)}
            disabled={busy || !csv.trim() || !report || report.stats.errors > 0}
            title={
              !report
                ? "dry-run first"
                : report.stats.errors > 0
                  ? "fix the errors first"
                  : "write to the price tables"
            }
          >
            Commit
          </button>
          {error && <span className="error"> {error}</span>}
        </p>
      </div>

      {report && (
        <div className="card">
          <h2>
            {report.dry_run ? "Dry-run report" : "Import result"}{" "}
            <span className={`badge ${report.stats.errors === 0 ? "published" : ""}`}>
              {report.status}
            </span>
          </h2>
          <p>
            {report.stats.rows} rows · {report.stats.ok} ok · {report.stats.errors} errors
            {!report.dry_run &&
              ` · ${report.stats.created} created · ${report.stats.updated} updated`}
          </p>
          {report.rows.some((r) => r.status === "error") && (
            <table>
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Problems</th>
                </tr>
              </thead>
              <tbody>
                {report.rows
                  .filter((r) => r.status === "error")
                  .map((r, i) => (
                    <tr key={i}>
                      <td>
                        <code>{Object.values(r.raw).join(",")}</code>
                      </td>
                      <td className="error">{r.messages?.errors.join("; ")}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </>
  );
}
