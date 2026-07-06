import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LoL AI Platform",
  description: "League of Legends analysis workspace"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
