export default function RightPanel({ title = "Context", children }) {
    return (
        <aside className="hidden w-80 shrink-0 border-l border-stroke bg-card/80 p-4 backdrop-blur-xl xl:block">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">{title}</h3>
            <div className="space-y-3">{children}</div>
        </aside>
    );
}
