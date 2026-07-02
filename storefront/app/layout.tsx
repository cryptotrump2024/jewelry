import type { Metadata } from "next";
import { getTenant } from "@/lib/tenant";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const tenant = await getTenant();
  return {
    title: { default: tenant.brandName, template: `%s · ${tenant.brandName}` },
    description:
      "Design your engagement ring: choose metal, diamond and setting with instant transparent pricing.",
  };
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const tenant = await getTenant();
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <a href="/" className="brand">
            {tenant.brandName}
          </a>
          <nav>
            <a href="/rings">Engagement rings</a>
          </nav>
        </header>
        <main>{children}</main>
        <footer className="site-footer">
          <p>Made to order · Fully itemized pricing · EU consumer rights respected</p>
        </footer>
      </body>
    </html>
  );
}
