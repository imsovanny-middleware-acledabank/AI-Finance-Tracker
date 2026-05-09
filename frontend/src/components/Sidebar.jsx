import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { NavLink } from "react-router-dom";
import clsx from "clsx";
import { navItems } from "@/data/navigation";

export default function Sidebar({ collapsed, onToggle }) {
    return (
        <aside
            className={clsx(
                "h-screen border-r border-stroke bg-card/90 backdrop-blur-xl transition-all duration-200",
                collapsed ? "w-20 p-3" : "w-72 p-4"
            )}
        >
            <div className="mb-6 flex items-center justify-between">
                {!collapsed && (
                    <h1 className="bg-gradient-to-r from-primary to-accent bg-clip-text text-xl font-bold text-transparent">
                        AI Finance Admin
                    </h1>
                )}
                <button
                    type="button"
                    onClick={onToggle}
                    className="rounded-xl border border-stroke bg-white/5 p-2 text-muted hover:bg-white/10 hover:text-text"
                    aria-label="Toggle sidebar"
                >
                    {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
                </button>
            </div>

            <nav className="space-y-2">
                {navItems.map((item) => {
                    const Icon = item.icon;
                    return (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            className={({ isActive }) =>
                                clsx(
                                    "group flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm transition",
                                    isActive
                                        ? "border-primary/40 bg-gradient-to-r from-primary to-accent text-black"
                                        : "border-transparent text-muted hover:border-stroke hover:bg-white/10 hover:text-text"
                                )
                            }
                        >
                            <Icon size={18} className="shrink-0" />
                            {!collapsed && <span>{item.label}</span>}
                        </NavLink>
                    );
                })}
            </nav>
        </aside>
    );
}
