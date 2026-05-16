import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "MIRROR",
  description: "Calibration-first AI trading agents"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

