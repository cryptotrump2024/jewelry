import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Engine Admin",
  description: "Jewelry configuration engine — admin",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <a href="/templates" className="brand">
            Engine Admin
          </a>
          <nav>
            <a href="/templates">Templates</a>
          </nav>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
