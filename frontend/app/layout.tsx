import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "StageFlow · Operational Console",
  description: "Local-first StageFlow Producer and Editorial operational interface",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="operational-dark">
      <body>{children}</body>
    </html>
  );
}
