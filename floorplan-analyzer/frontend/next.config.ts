import type { NextConfig } from "next";
import { networkInterfaces } from "node:os";

// 開発サーバーを LAN の IP（例: http://192.168.x.x:5173）や別の端末から開くと、Next.js は /_next/* の
// 開発用リソースをクロスオリジンとして遮断し、画面の JS が動かず解析が始まらない。
// この PC の IPv4 アドレスを起動時に自動で許可し、それ以外のホストは DEV_ALLOWED_ORIGINS（カンマ区切り）で追加する。
// allowedDevOrigins は next dev だけに効く設定で、本番ビルドには影響しない。
const lanHosts = Object.values(networkInterfaces())
  .flatMap((addresses) => addresses ?? [])
  .filter((address) => address.family === "IPv4" && !address.internal)
  .map((address) => address.address);
const extraHosts = (process.env.DEV_ALLOWED_ORIGINS ?? "")
  .split(",")
  .map((host) => host.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: [...new Set([...lanHosts, ...extraHosts])],
};

export default nextConfig;
