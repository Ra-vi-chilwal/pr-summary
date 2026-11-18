/** A handful of 16px line icons, drawn here so we don't ship an icon library. */
const PATHS = {
  menu: "M2.5 4h11M2.5 8h11M2.5 12h11",
  close: "M4 4l8 8M12 4l-8 8",
  arrow: "M3 8h10M9 4l4 4-4 4",
  lock: "M4.5 7V5a3.5 3.5 0 0 1 7 0v2M3.5 7h9v6.5h-9z",
  external: "M9 3h4v4M13 3L7.5 8.5M11 9.5V13H3V5h3.5",
  copy: "M5.5 5.5V3h7.5v7.5h-2.5M3 5.5h7.5V13H3z",
} as const;

export function Icon({ name, label }: { name: keyof typeof PATHS; label?: string }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
