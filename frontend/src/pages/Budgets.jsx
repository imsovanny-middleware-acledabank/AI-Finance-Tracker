import { useEffect, useState } from "react";
import PageHeader from "@/components/PageHeader";
import api from "@/services/api";

export default function Budgets() {
    const [budgetCards, setBudgetCards] = useState([]);

    useEffect(() => {
        let mounted = true;
        async function loadBudgets() {
            try {
                const { data } = await api.get("budgets/", { params: { page: 1, page_size: 20 } });
                if (mounted) {
                    setBudgetCards(
                        (data.results || []).map((item) => ({
                            name: item.category,
                            spent: `$${Number(item.spent_amount || 0).toFixed(2)}`,
                            limit: `$${Number(item.limit_amount || 0).toFixed(2)}`,
                            status: item.status === "over" ? "Over" : "Safe",
                            pct: Math.min(Number(item.percentage_used || 0), 100),
                        }))
                    );
                }
            } catch {
                if (mounted) setBudgetCards([]);
            }
        }
        loadBudgets();
        return () => {
            mounted = false;
        };
    }, []);

    return (
        <section className="grid gap-4">
            <PageHeader title="Budgets" subtitle="Monitor envelope budgets, threshold alerts, and overruns." />

            <div className="grid gap-4 lg:grid-cols-2">
                {budgetCards.map((b) => (
                    <article key={b.name} className="rounded-2xl border border-stroke bg-card p-5 shadow-glow">
                        <div className="mb-3 flex items-center justify-between">
                            <h3 className="font-semibold text-text">{b.name}</h3>
                            <span className={b.status === "Over" ? "text-danger" : "text-success"}>{b.status}</span>
                        </div>
                        <p className="text-sm text-muted">
                            Spent {b.spent} / Limit {b.limit}
                        </p>
                        <div className="mt-3 h-2 rounded-full bg-white/10">
                            <div
                                className={b.status === "Over" ? "h-2 rounded-full bg-danger" : "h-2 rounded-full bg-success"}
                                style={{ width: `${b.pct ?? (b.status === "Over" ? 100 : 70)}%` }}
                            />
                        </div>
                    </article>
                ))}
            </div>
        </section>
    );
}
