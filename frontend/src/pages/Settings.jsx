import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import PageHeader from "@/components/PageHeader";

function SettingsRow({ icon, iconBg, label, sub, right, onClick, danger }) {
    const bg = iconBg || "bg-indigo-500/20";
    return (
        <button
            type="button"
            onClick={onClick}
            className="flex w-full appearance-none items-center gap-1 border-0 bg-transparent px-1.5 py-0 text-left outline-none transition-colors hover:bg-white/5 active:bg-white/10"
        >
            <span className={"flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full text-[8px] " + bg}>
                {icon}
            </span>
            <span className="min-w-0 flex-1">
                <span className={"block text-[10px] font-medium leading-tight " + (danger ? "text-red-400" : "text-text")}>
                    {label}
                </span>
                {sub && <span className="block truncate text-[8px] text-muted leading-none">{sub}</span>}
            </span>
            {right !== undefined ? (
                <span className="shrink-0 text-[8px] text-muted">{right}</span>
            ) : (
                <svg className="h-2 w-2 shrink-0 text-muted/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
            )}
        </button>
    );
}

function SettingsToggleRow({ icon, iconBg, label, sub, checked, onChange }) {
    const bg = iconBg || "bg-indigo-500/20";
    return (
        <div className="flex w-full items-center gap-1 px-1.5 py-0">
            <span className={"flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full text-[8px] " + bg}>
                {icon}
            </span>
            <span className="min-w-0 flex-1">
                <span className="block text-[10px] font-medium leading-tight text-text">{label}</span>
                {sub && <span className="block truncate text-[8px] text-muted leading-none">{sub}</span>}
            </span>
            <button
                type="button"
                role="switch"
                aria-checked={checked}
                onClick={() => onChange(!checked)}
                className={"relative h-3 w-5 shrink-0 rounded-full transition-colors " + (checked ? "bg-indigo-500" : "bg-white/20")}
            >
                <span className={"absolute top-px h-2 w-2 rounded-full bg-white shadow transition-transform " + (checked ? "translate-x-2" : "translate-x-px")} />
            </button>
        </div>
    );
}

function SettingsGroup({ title, children }) {
    return (
        <div className="mb-0.5">
            <p className="mb-0 px-1 text-[7px] font-semibold uppercase tracking-widest text-muted/70">{title}</p>
            <div className="overflow-hidden rounded-xl border border-stroke bg-card shadow-glow divide-y divide-stroke/50">
                {children}
            </div>
        </div>
    );
}

export default function Settings() {
    const { user, logout } = useAuth();
    const [darkMode, setDarkMode] = useState(false);
    const [language] = useState("English");
    const [currency] = useState("USD");

    return (
        <section className="grid gap-0">
            <PageHeader title="Settings" subtitle="Manage your account and preferences." />

            <div className="mx-auto w-full max-w-xs">
                <SettingsGroup title="General Settings">
                    <SettingsRow icon="👤" iconBg="bg-blue-500/20" label="Edit Profile" sub="Name, photo, contact info" />
                    <SettingsRow
                        icon="🪪"
                        iconBg="bg-purple-500/20"
                        label="User ID"
                        sub="Telegram ID"
                        right={<span className="font-mono text-xs text-muted">{user?.telegram_id ?? "—"}</span>}
                    />
                    <SettingsRow icon="💱" iconBg="bg-green-500/20" label="Exchange Rate" sub="USD → KHR live rate" />
                </SettingsGroup>

                <SettingsGroup title="Personalization">
                    <SettingsToggleRow
                        icon="🌙"
                        iconBg="bg-slate-500/20"
                        label="Dark Mode"
                        sub="Switch appearance"
                        checked={darkMode}
                        onChange={setDarkMode}
                    />
                    <SettingsRow icon="🌐" iconBg="bg-cyan-500/20" label="Language" sub="App display language" right={language} />
                </SettingsGroup>

                <SettingsGroup title="Data Management">
                    <SettingsRow icon="💵" iconBg="bg-yellow-500/20" label="Currency Preference" sub="Display amounts in" right={currency} />
                    <SettingsRow icon="📄" iconBg="bg-emerald-500/20" label="Export CSV" sub="Download transaction history" />
                    <SettingsRow icon="🗂️" iconBg="bg-orange-500/20" label="Export PDF" sub="Download summary report" />
                </SettingsGroup>

                <SettingsGroup title="Security">
                    <SettingsRow icon="🔒" iconBg="bg-red-500/20" label="Change Passcode / PIN" sub="Update your login PIN" />
                </SettingsGroup>

                <SettingsGroup title="Support & About">
                    <SettingsRow icon="💬" iconBg="bg-indigo-500/20" label="Contact Support" sub="Get help from our team" />
                    <SettingsRow icon="ℹ️" iconBg="bg-sky-500/20" label="About App" sub="Version, licenses, credits" />
                </SettingsGroup>

                <SettingsGroup title="System">
                    <SettingsRow icon="🚪" iconBg="bg-red-500/15" label="Log Out" danger right={null} onClick={logout} />
                </SettingsGroup>
            </div>
        </section>
    );
}
