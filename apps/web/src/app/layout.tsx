import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "小文星球",
  description: "AI 语文陪练 MVP",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
