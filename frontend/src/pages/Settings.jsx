import PageHeader from "@/components/PageHeader";

const settingsGroups = [
    { title: "Authentication", items: ["Session timeout", "2FA requirement", "Password policy"] },
    { title: "Integrations", items: ["Telegram bot token", "Exchange rate provider", "Webhook endpoints"] },
    { title: "Notifications", items: ["Budget alerts", "System alerts", "Audit digest"] },
];

export default function Settings() {
    return (
        <section className="grid gap-4">
            <PageHeader title="Settings" subtitle="Control platform behaviors, integrations, and security policies." />

            <div className="grid gap-4 lg:grid-cols-3">
                {settingsGroups.map((group) => (
                    <article key={group.title} className="rounded-2xl border border-stroke bg-card p-5 shadow-glow">
                        <h3 className="mb-3 font-semibold text-text">{group.title}</h3>
                        <ul className="space-y-2 text-sm text-muted">
                            {group.items.map((item) => (
                                <li key={item} className="rounded-lg bg-white/5 px-3 py-2">
                                    {item}
                                </li>
                            ))}
                        </ul>
                    </article>
                ))}
            </div>
        </section>
    );
}
