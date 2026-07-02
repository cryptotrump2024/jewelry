"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type GroupRow = { id: string; key: string; name: string };
type RuleSet = { id: string; version: number; status: string };

export function AttachGroupForm({
  templateId,
  groups,
  nextStep,
}: {
  templateId: string;
  groups: GroupRow[];
  nextStep: number;
}) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  if (groups.length === 0) return null;

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const resp = await fetch(`/api/engine/admin/templates/${templateId}/option-groups`, {
      method: "POST",
      body: JSON.stringify({
        option_group_id: form.get("option_group_id"),
        step_order: Number(form.get("step_order")),
        is_required: form.get("is_required") === "on",
      }),
    });
    if (!resp.ok) {
      setError(await resp.text());
      return;
    }
    setError(null);
    router.refresh();
  }

  return (
    <form className="row" onSubmit={onSubmit} style={{ marginTop: "0.75rem" }}>
      <select name="option_group_id" required>
        {groups.map((g) => (
          <option key={g.id} value={g.id}>
            {g.name} ({g.key})
          </option>
        ))}
      </select>
      <input
        name="step_order"
        type="number"
        defaultValue={nextStep}
        style={{ width: "5rem" }}
        aria-label="step order"
      />
      <label>
        <input name="is_required" type="checkbox" defaultChecked /> required
      </label>
      <button className="secondary">Attach group</button>
      {error && <span className="error">{error}</span>}
    </form>
  );
}

export function NewRuleSetButton({ templateId }: { templateId: string }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  async function create() {
    const resp = await fetch(`/api/engine/admin/templates/${templateId}/rule-sets`, {
      method: "POST",
    });
    if (!resp.ok) {
      setError(await resp.text());
      return;
    }
    setError(null);
    router.refresh();
  }

  return (
    <p>
      <button className="secondary" onClick={create}>
        New draft rule set
      </button>
      {error && <span className="error"> {error}</span>}
    </p>
  );
}

export function RuleSetActions({ ruleSet }: { ruleSet: RuleSet }) {
  const router = useRouter();
  const [report, setReport] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function simulate() {
    setBusy(true);
    setError(null);
    const resp = await fetch(`/api/engine/admin/rule-sets/${ruleSet.id}/simulate`);
    setBusy(false);
    if (!resp.ok) {
      setError(await resp.text());
      return;
    }
    setReport(await resp.json());
  }

  async function publish() {
    setBusy(true);
    setError(null);
    const resp = await fetch(`/api/engine/admin/rule-sets/${ruleSet.id}/publish`, {
      method: "POST",
    });
    setBusy(false);
    const body = await resp.json().catch(() => null);
    if (!resp.ok) {
      // 422 carries the simulation report explaining the refusal.
      setError(
        body?.detail?.message
          ? `${body.detail.message} — see report`
          : `publish failed (${resp.status})`,
      );
      if (body?.detail?.report) setReport(body.detail.report);
      return;
    }
    setReport(body.report);
    router.refresh();
  }

  return (
    <div style={{ marginBottom: "1rem" }}>
      <p>
        Version {ruleSet.version}{" "}
        <span className={`badge ${ruleSet.status}`}>{ruleSet.status}</span>{" "}
        <button className="secondary" onClick={simulate} disabled={busy}>
          Simulate
        </button>{" "}
        {ruleSet.status === "draft" && (
          <button onClick={publish} disabled={busy}>
            Publish
          </button>
        )}
        {error && <span className="error"> {error}</span>}
      </p>
      {report != null && <pre className="report">{JSON.stringify(report, null, 2)}</pre>}
    </div>
  );
}
