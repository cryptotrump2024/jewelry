import Link from "next/link";
import { engineFetch } from "@/lib/engine";
import { CreateTemplateForm } from "./create-form";

type TemplateRow = { id: string; code: string; name: string; status: string };
type Category = { id: string; name: string; slug: string };

export const dynamic = "force-dynamic";

export default async function TemplatesPage() {
  const [templates, categories] = await Promise.all([
    engineFetch<TemplateRow[]>("/admin/templates"),
    engineFetch<Category[]>("/admin/categories"),
  ]);

  return (
    <>
      <h1>Templates</h1>
      <table>
        <thead>
          <tr>
            <th>Code</th>
            <th>Name</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {templates.map((t) => (
            <tr key={t.id}>
              <td>
                <Link href={`/templates/${t.id}`}>{t.code}</Link>
              </td>
              <td>{t.name}</td>
              <td>
                <span className={`badge ${t.status}`}>{t.status}</span>
              </td>
            </tr>
          ))}
          {templates.length === 0 && (
            <tr>
              <td colSpan={3}>No templates yet — create the first one below.</td>
            </tr>
          )}
        </tbody>
      </table>

      <div className="card" style={{ marginTop: "1.5rem" }}>
        <h2>New template</h2>
        <CreateTemplateForm categories={categories} />
      </div>
    </>
  );
}
