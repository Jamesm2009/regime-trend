import "./globals.css";

export const metadata = {
  title: "regime-trend",
  description: "Market regime detection — HMM-based, multivariate (SPY, VIX, TNX)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans">{children}</body>
    </html>
  );
}
