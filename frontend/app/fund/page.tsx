import Image from "next/image";
import fundScreenshot from "@/src/스크린샷 2026-07-13 162257.png";

export default function FundPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6 py-10">
        <p className="mb-4"> Gemini API를 살 돈이 없어요 ㅠㅠ</p> 
        <p className="mb-4">불쌍한 개발자에게 후원해주시기 바랍니다.</p>
        <Image src={fundScreenshot} alt="fund" />
    </main>
  );
}
