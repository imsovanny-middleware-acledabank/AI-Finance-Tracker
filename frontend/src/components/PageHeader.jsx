export default function PageHeader({ title, subtitle, action }) {
    return (
        <div className="mb-5 flex items-start justify-between gap-4">
            <div>
                <h1 className="text-2xl font-semibold text-text">{title}</h1>
                {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
            </div>
            {action}
        </div>
    );
}
