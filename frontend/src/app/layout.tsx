import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "EDGAR Insider Alpha",
  description: "Real-time insider buying signals from SEC EDGAR Form 4 filings",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-surface-900 text-white antialiased`}>
        {children}
      </body>
    </html>
  );
}
