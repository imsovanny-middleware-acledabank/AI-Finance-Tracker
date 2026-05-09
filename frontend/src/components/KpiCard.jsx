export default function KpiCard({ label, value, delta }) {
    return (
        <article className="rounded-2xl border border-stroke bg-card p-5 shadow-glow backdrop-blur-xl">
            <p className="text-sm text-muted">{label}</p>
            <h2 className="mt-2 text-2xl font-bold text-text">{value}</h2>
            <p className="mt-1 text-xs text-success">{delta}</p>
        </article>
    );
}
