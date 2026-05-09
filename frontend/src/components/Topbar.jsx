import { Bell, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function Topbar() {
    const navigate = useNavigate();
    const { user, role, logout } = useAuth();

    const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.username || "User";

    return (
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-stroke bg-card/90 px-6 py-4 backdrop-blur-xl">
            <label className="flex w-full max-w-xl items-center gap-3 rounded-xl border border-stroke bg-white/5 px-3 py-2 focus-within:ring-2 focus-within:ring-primary/40">
                <Search size={16} className="text-muted" />
                <input
                    placeholder="Search transactions, users, budgets..."
                    className="w-full bg-transparent text-sm text-text placeholder:text-muted outline-none"
                />
            </label>

            <div className="ml-4 flex items-center gap-3">
                <button
                    type="button"
                    className="rounded-xl border border-stroke bg-white/10 p-2.5 text-muted hover:bg-white/20 hover:text-text"
                    aria-label="Notifications"
                >
                    <Bell size={16} />
                </button>
                <div className="rounded-xl border border-stroke bg-white/10 px-3 py-2 text-sm text-text">
                    {displayName} · {role}
                </div>
                <button
                    type="button"
                    onClick={async () => {
                        await logout();
                        navigate("/", { replace: true });
                        window.location.href = "/login/";
                    }}
                    className="rounded-xl border border-stroke bg-white/10 px-3 py-2 text-sm text-muted hover:bg-white/20 hover:text-text"
                >
                    Logout
                </button>
            </div>
        </header>
    );
}
