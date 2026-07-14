/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  async rewrites() {
    // 프론트는 항상 같은 origin의 /api/*로만 호출하고, 여기서 실제 웹서버로
    // 프록시한다. VM에 배포했을 때 브라우저가 "localhost"를 자기 자신의
    // 컴퓨터로 오인하는 문제를 막기 위함 (DESIGN.md "배포 구조" — BFF 패턴).
    return [
      { source: "/api/:path*", destination: "http://localhost:8000/:path*" },
    ];
  },
};

module.exports = nextConfig;