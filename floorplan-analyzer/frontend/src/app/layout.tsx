import type { Metadata } from "next";
import type { ReactNode } from "react";
import "../styles.css";

export const metadata: Metadata = {
  title: "平面図 面積・壁面積 解析",
  description: "平面図の部屋・壁・ドアを解析し、床面積と壁面積の算出根拠を確認できます。",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="ja"><body>{children}</body></html>;
}
