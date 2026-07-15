import type { NextConfig } from "next";

const isGithubPages = process.env.GITHUB_PAGES === "true";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true
  },
  ...(isGithubPages
    ? {
        basePath: "/LoL_AI_Platform",
        assetPrefix: "/LoL_AI_Platform/"
      }
    : {})
};

export default nextConfig;
