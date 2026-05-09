import { useMemo, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";
import RightPanel from "@/components/RightPanel";

const panelConfig = {
    "/": {
        title: "Dashboard Filters",
        chips: ["This month", "KHR + USD", "Top categories"],
    },
    "/transactions": {
        title: "Transaction Filters",
        chips: ["Date range", "Category", "Amount", "Status"],
    },
    "/users": {
        title: "User Segments",
        chips: ["Active users", "New users", "High spenders"],
    },
    "/budgets": {
        title: "Budget Controls",
        chips: ["Monthly caps", "Alert thresholds", "Over-budget"],
    },
    "/chats": {
        title: "AI Chat Controls",
        chips: ["Model", "Escalations", "Flagged intents"],
    },
    "/settings": {
        title: "System Controls",
        chips: ["Roles", "Integrations", "Notifications"],
    },
};

export default function AppLayout() {
    const [collapsed, setCollapsed] = useState(false);
    const { pathname } = useLocation();

    const panel = useMemo(() => panelConfig[pathname] ?? panelConfig["/"], [pathname]);

    return (
        <div className="flex h-screen bg-bg text-text">
            <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />

            <div className="flex min-w-0 flex-1 flex-col">
                <Topbar />
                <div className="flex min-h-0 flex-1">
                    <main className="min-w-0 flex-1 overflow-auto p-6">
                        <Outlet />
                    </main>
                    <RightPanel title={panel.title}>
                        {panel.chips.map((chip) => (
                            <button
                                key={chip}
                                type="button"
                                className="w-full rounded-xl border border-stroke bg-white/5 px-3 py-2 text-left text-sm text-muted hover:bg-white/10 hover:text-text"
                            >
                                {chip}
                            </button>
                        ))}
                    </RightPanel>
                </div>
            </div>
        </div>
    );
}
