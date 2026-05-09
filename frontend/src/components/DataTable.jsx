export default function DataTable({ columns, rows }) {
    return (
        <div className="overflow-x-auto rounded-2xl border border-stroke bg-card shadow-glow">
            <table className="w-full text-sm">
                <thead className="bg-white/5 text-left text-muted">
                    <tr>
                        {columns.map((col) => (
                            <th key={col.key} className="px-4 py-3 font-medium">
                                {col.label}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row, index) => (
                        <tr key={row.id ?? index} className="border-t border-stroke/80 hover:bg-white/5">
                            {columns.map((col) => (
                                <td key={col.key} className="px-4 py-3 text-text">
                                    {row[col.key]}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
