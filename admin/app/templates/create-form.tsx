"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type Category = { id: string; name: string; slug: string };

export function CreateTemplateForm({ categories }: { categories: Category[] }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    const resp = await fetch("/api/engine/admin/templates", {
      method: "POST",
      body: JSON.stringify({
        category_id: form.get("category_id"),
        code: form.get("code"),
        name: form.get("name"),
        style: form.get("style") || null,
      }),
    });
    setBusy(false);
    if (!resp.ok) {
      setError(await resp.text());
      return;
    }
    router.refresh();
    (event.target as HTMLFormElement).reset?.();
  }

  return (
    <form className="row" onSubmit={onSubmit}>
      <select name="category_id" required>
        {categories.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      <input name="code" placeholder="code (e.g. hidden-halo)" required />
      <input name="name" placeholder="Name" required />
      <input name="style" placeholder="style (optional)" />
      <button disabled={busy}>Create</button>
      {error && <span className="error">{error}</span>}
    </form>
  );
}
