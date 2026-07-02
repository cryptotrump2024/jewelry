import { engineFetch } from "@/lib/engine";
import { PricePreview } from "./price-preview";
import { AttachGroupForm, NewRuleSetButton, RuleSetActions } from "./widgets";

type TemplateDetail = {
  id: string;
  code: string;
  name: string;
  style: string | null;
  status: string;
  option_groups: {
    id: string;
    key: string;
    name: string;
    step_order: number;
    is_required: boolean;
    options: { id: string; code: string; label: string; is_active: boolean }[];
  }[];
  rule_sets: { id: string; version: number; status: string }[];
};

type GroupRow = { id: string; key: string; name: string };

export const dynamic = "force-dynamic";

export default async function TemplatePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [template, allGroups] = await Promise.all([
    engineFetch<TemplateDetail>(`/admin/templates/${id}`),
    engineFetch<GroupRow[]>("/admin/option-groups"),
  ]);
  const attachedIds = new Set(template.option_groups.map((g) => g.id));
  const attachable = allGroups.filter((g) => !attachedIds.has(g.id));

  return (
    <>
      <h1>
        {template.name} <span className={`badge ${template.status}`}>{template.status}</span>
      </h1>
      <p style={{ color: "var(--muted)" }}>
        code <code>{template.code}</code>
        {template.style ? ` · style ${template.style}` : ""}
      </p>

      <div className="card">
        <h2>Option groups (configurator steps)</h2>
        {template.option_groups.length === 0 && <p>None attached yet.</p>}
        <table>
          <tbody>
            {template.option_groups.map((g) => (
              <tr key={g.id}>
                <td>#{g.step_order}</td>
                <td>
                  <strong>{g.name}</strong> <code>{g.key}</code>
                  {g.is_required ? "" : " (optional)"}
                </td>
                <td>
                  {g.options
                    .filter((o) => o.is_active)
                    .map((o) => o.code)
                    .join(", ") || "no options"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <AttachGroupForm
          templateId={template.id}
          groups={attachable}
          nextStep={template.option_groups.length + 1}
        />
      </div>

      <PricePreview templateId={template.id} groups={template.option_groups} />

      <div className="card">
        <h2>Rule sets</h2>
        {template.rule_sets.length === 0 && <p>No rule sets yet.</p>}
        {template.rule_sets.map((rs) => (
          <RuleSetActions key={rs.id} ruleSet={rs} />
        ))}
        <NewRuleSetButton templateId={template.id} />
      </div>
    </>
  );
}
