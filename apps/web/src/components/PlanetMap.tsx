import Link from "next/link";

export function PlanetMap({
  studentId,
  places,
}: {
  studentId: string;
  places: string[];
}) {
  function hrefForPlace(place: string) {
    if (place.includes("句子")) {
      return `/children/${studentId}/sentence`;
    }
    if (place.includes("作文")) {
      return `/children/${studentId}/essay`;
    }
    return `/children/${studentId}/reading`;
  }

  return (
    <nav
      aria-label="地图"
      className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm"
    >
      <h2 className="text-xl font-bold">地图</h2>
      <div className="mt-4 flex flex-wrap gap-3">
        {places.map((place) => {
          const isReadingCanyon = place.includes("阅读");
          if (isReadingCanyon) {
            return (
              <span
                key={place}
                aria-disabled="true"
                className="rounded-lg border border-[var(--wen-border)] bg-[var(--wen-bg)] px-4 py-2 font-semibold text-[var(--wen-muted)]"
              >
                {place} · 即将开放
              </span>
            );
          }

          return (
            <Link
              key={place}
              className="rounded-lg border border-[var(--wen-border)] px-4 py-2 font-semibold"
              href={hrefForPlace(place)}
            >
              {place}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
