import type { ReactNode } from "react";

export const metadata = {
  title: "小文星球",
  description: "AI 语文陪练 MVP",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
