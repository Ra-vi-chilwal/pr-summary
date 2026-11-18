/** Placeholder shapes that match the content they stand in for. Hidden from screen readers. */
export function Skeleton({ width = "100%", height }: { width?: string; height?: string }) {
  return <span className="skeleton" aria-hidden="true" style={{ width, height }} />;
}

export function RowSkeletons({ count = 4 }: { count?: number }) {
  return (
    <ul className="rows" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <li key={i} className="row">
          <span className="status-dot" />
          <span style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            <Skeleton width={`${55 - i * 7}%`} />
            <Skeleton width="30%" height="0.7em" />
          </span>
          <Skeleton width="5rem" />
        </li>
      ))}
    </ul>
  );
}
