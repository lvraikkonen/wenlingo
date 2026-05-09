export function PlanetMap({ places }: { places: string[] }) {
  return (
    <nav aria-label="地图">
      {places.map((place) => (
        <a key={place} href="#">
          {place}
        </a>
      ))}
    </nav>
  );
}
