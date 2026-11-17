import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "올인원 AI 마케팅 자동화",
  description: "주제와 스타일만 고르면 숏폼·쓰레드·블로그를 한 번에 만들고 4대 채널에 발행합니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
