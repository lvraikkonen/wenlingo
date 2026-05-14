export function PlanetMap({ places }: { places: string[] }) {
  return (
    <nav
      aria-label="地图"
      className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm"
    >
      <h2 className="text-xl font-bold">地图</h2>
      <div className="mt-4 flex flex-wrap gap-3">
        {places.map((place) => (
          <a
            key={place}
            className="rounded-lg border border-[var(--wen-border)] px-4 py-2 font-semibold"
            href="#"
          >
            {place}
          </a>
        ))}
      </div>
    </nav>
  );
}
