import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Inverse — Adversarial Legal Research",
  description: "Find the authorities capable of defeating your proposition, not just supporting it.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
