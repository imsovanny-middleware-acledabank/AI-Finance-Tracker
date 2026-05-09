import KpiCard from "@/components/KpiCard";
import PageHeader from "@/components/PageHeader";

const kpis = [
    { label: "Revenue", value: "$12,430", delta: "+8.4% vs last month" },
    { label: "Expenses", value: "$7,540", delta: "+3.1% vs last month" },
    { label: "Users", value: "2,184", delta: "+112 this week" },
    { label: "Transactions", value: "14,902", delta: "+9.7% processed" },
];

export default function Dashboard() {
    return (
        <section className="grid gap-6">
            <PageHeader
                title="Dashboard"
                subtitle="Executive overview of financial performance, usage, and AI activity."
            />

            <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
                {kpis.map((kpi) => (
                    <KpiCard key={kpi.label} {...kpi} />
                ))}
            </div>

            <article className="rounded-2xl border border-stroke bg-card p-6 shadow-glow backdrop-blur-xl">
                <p className="mb-4 text-sm text-muted">Analytics Chart</p>
                <div className="flex h-72 items-center justify-center rounded-xl border border-dashed border-stroke text-muted">
                    Plug in Chart.js or Recharts with live KPI series
                </div>
            </article>
        </section>
    );
}
