import Link from "next/link";

export function ConstructionState({
  title,
  body,
  primaryHref,
  secondaryHref,
}: {
  title: string;
  body: string;
  primaryHref: string;
  secondaryHref?: string;
}) {
  return (
    <section className="mx-auto max-w-3xl rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-bold">{title}</h1>
      <p className="mt-3 text-[var(--wen-muted)]">{body}</p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link
          className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white"
          href={primaryHref}
        >
          回到小文星球
        </Link>
        {secondaryHref ? (
          <Link
            className="rounded-lg border border-[var(--wen-border)] px-4 py-2 font-semibold"
            href={secondaryHref}
          >
            去完成今日推荐
          </Link>
        ) : null}
      </div>
    </section>
  );
}
