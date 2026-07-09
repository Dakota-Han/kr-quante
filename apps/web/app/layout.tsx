import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "kr-quante",
  description: "Korea overnight lead-lag ETF trading dashboard"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
