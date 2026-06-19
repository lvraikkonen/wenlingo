import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen px-5 py-8 sm:px-8">
      <h1 className="text-4xl font-bold text-[var(--wen-ink)]">小文星球</h1>
      <p className="mt-4 max-w-xl text-[var(--wen-muted)]">
        从登录开始，继续孩子的阅读与写作练习。
      </p>
      <Link
        href="/alpha/start"
        className="mt-6 inline-flex rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white shadow-sm transition hover:brightness-105"
      >
        进入 Alpha 登录
      </Link>
    </main>
  );
}
