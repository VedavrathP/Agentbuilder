import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Orchestra — AI Agent Orchestration",
  description:
    "Create, configure, and orchestrate AI agents into collaborative workflows.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <header className="border-b bg-card/60 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-6">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              Orchestra
            </Link>
            <nav className="flex items-center gap-4 text-sm text-muted-foreground">
              <Link
                href="/agents"
                className="hover:text-foreground transition-colors"
              >
                Agents
              </Link>
              <Link
                href="/workflows"
                className="hover:text-foreground transition-colors"
              >
                Workflows
              </Link>
              <Link
                href="/telegram"
                className="hover:text-foreground transition-colors"
              >
                Telegram
              </Link>
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <Toaster richColors position="top-right" />
      </body>
    </html>
  );
}
