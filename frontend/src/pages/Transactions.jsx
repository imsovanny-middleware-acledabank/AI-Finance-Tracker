import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import api from "@/services/api";

const columns = [
    { key: "date", label: "Date" },
    { key: "type", label: "Type" },
    { key: "amount_display", label: "Amount" },
    { key: "user", label: "User" },
    { key: "category", label: "Category" },
];

export default function Transactions() {
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(false);
    const [meta, setMeta] = useState({ page: 1, total_pages: 1, count: 0 });
    const [filters, setFilters] = useState({
        search: "",
        type: "",
        category: "",
        sort_by: "date",
        sort_order: "desc",
        page: 1,
        page_size: 10,
    });

    useEffect(() => {
        let mounted = true;

        async function loadTransactions() {
            setLoading(true);
            try {
                const { data } = await api.get("transactions/", { params: filters });
                if (mounted) {
                    setRows(Array.isArray(data) ? data : data.results || []);
                    setMeta({
                        page: data.page || 1,
                        total_pages: data.total_pages || 1,
                        count: data.count || 0,
                    });
                }
            } catch {
                if (mounted) {
                    setRows([
                        { id: 1, date: "2026-05-01", type: "expense", amount_display: "$44.00", user: "123456", category: "Food" },
                        { id: 2, date: "2026-05-01", type: "income", amount_display: "$300.00", user: "234567", category: "Salary" },
                    ]);
                    setMeta({ page: 1, total_pages: 1, count: 2 });
                }
            } finally {
                if (mounted) setLoading(false);
            }
        }

        loadTransactions();
        return () => {
            mounted = false;
        };
    }, [filters]);

    const action = useMemo(
        () => (
            <div className="flex gap-2">
                <button type="button" className="rounded-xl border border-stroke bg-white/10 px-3 py-2 text-sm text-muted hover:bg-white/20">
                    Bulk Ops
                </button>
                <button
                    type="button"
                    className="rounded-xl bg-gradient-to-r from-primary to-success px-4 py-2 text-sm font-semibold text-black"
                >
                    + Add Transaction
                </button>
            </div>
        ),
        []
    );

    return (
        <section className="grid gap-4">
            <PageHeader
                title="Transactions"
                subtitle="Table, filters, and bulk operations for all financial records."
                action={action}
            />

            <div className="grid gap-3 rounded-2xl border border-stroke bg-card p-4 md:grid-cols-5">
                <input
                    value={filters.search}
                    onChange={(e) => setFilters((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
                    placeholder="Search note/category"
                    className="rounded-xl border border-stroke bg-white/5 px-3 py-2 text-sm text-text outline-none"
                />
                <select
                    value={filters.type}
                    onChange={(e) => setFilters((prev) => ({ ...prev, type: e.target.value, page: 1 }))}
                    className="rounded-xl border border-stroke bg-white/5 px-3 py-2 text-sm text-text outline-none"
                >
                    <option value="">All types</option>
                    <option value="income">Income</option>
                    <option value="expense">Expense</option>
                </select>
                <input
                    value={filters.category}
                    onChange={(e) => setFilters((prev) => ({ ...prev, category: e.target.value, page: 1 }))}
                    placeholder="Category"
                    className="rounded-xl border border-stroke bg-white/5 px-3 py-2 text-sm text-text outline-none"
                />
                <select
                    value={filters.sort_by}
                    onChange={(e) => setFilters((prev) => ({ ...prev, sort_by: e.target.value }))}
                    className="rounded-xl border border-stroke bg-white/5 px-3 py-2 text-sm text-text outline-none"
                >
                    <option value="date">Sort: Date</option>
                    <option value="amount">Sort: Amount</option>
                    <option value="category">Sort: Category</option>
                    <option value="type">Sort: Type</option>
                    <option value="created_at">Sort: Created</option>
                </select>
                <select
                    value={filters.sort_order}
                    onChange={(e) => setFilters((prev) => ({ ...prev, sort_order: e.target.value }))}
                    className="rounded-xl border border-stroke bg-white/5 px-3 py-2 text-sm text-text outline-none"
                >
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
            </div>

            {loading ? (
                <div className="rounded-2xl border border-stroke bg-card p-8 text-center text-muted">Loading transactions...</div>
            ) : (
                <>
                    <DataTable columns={columns} rows={rows} />
                    <div className="flex items-center justify-between rounded-xl border border-stroke bg-card px-4 py-3 text-sm text-muted">
                        <span>
                            {meta.count} records · page {meta.page}/{meta.total_pages}
                        </span>
                        <div className="flex gap-2">
                            <button
                                type="button"
                                disabled={meta.page <= 1}
                                onClick={() => setFilters((prev) => ({ ...prev, page: Math.max(1, prev.page - 1) }))}
                                className="rounded-lg border border-stroke px-3 py-1 disabled:opacity-40"
                            >
                                Prev
                            </button>
                            <button
                                type="button"
                                disabled={meta.page >= meta.total_pages}
                                onClick={() => setFilters((prev) => ({ ...prev, page: prev.page + 1 }))}
                                className="rounded-lg border border-stroke px-3 py-1 disabled:opacity-40"
                            >
                                Next
                            </button>
                        </div>
                    </div>
                </>
            )}
        </section>
    );
}
