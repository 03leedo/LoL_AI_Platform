import type { Metadata } from "next";
import "./globals.css";

import { GlobalNav } from "@/components/GlobalNav";

export const metadata: Metadata = {
  title: "LoL.AI — 증거 기반 전적 분석",
  description: "League of Legends analysis workspace"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>
        <GlobalNav />
        {children}
      </body>
    </html>
  );
}
