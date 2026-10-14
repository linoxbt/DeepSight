export function Shell({
  children,
}: {
  active?: string;
  children: React.ReactNode;
}) {
  return <div className="document">{children}</div>;
}
