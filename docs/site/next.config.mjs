/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["192.168.1.2"],
  experimental: {
    useTypeScriptCli: false,
  },
  output: "export",
  trailingSlash: true,
  poweredByHeader: false,
  // next dev does not serve public/slides/index.html at /slides/ when
  // trailingSlash is on. The static export and Vercel do. This rewrite
  // makes the dev server match that URL. It is a no-op for the export,
  // which copies public/slides/index.html itself.
  async rewrites() {
    return [
      { source: "/slides", destination: "/slides/index.html" },
      { source: "/slides/", destination: "/slides/index.html" },
    ];
  },
};

export default nextConfig;
