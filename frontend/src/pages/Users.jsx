import { useEffect, useState } from "react";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import api from "@/services/api";

const columns = [
    { key: "name", label: "Name" },
    { key: "telegram_id", label: "Telegram ID" },
    { key: "phone", label: "Phone" },
    { key: "role", label: "Role" },
];

export default function Users() {
    const [rows, setRows] = useState([]);

    useEffect(() => {
        let mounted = true;
        async function loadUsers() {
            try {
                const { data } = await api.get("users/", { params: { page: 1, page_size: 20 } });
                if (mounted) setRows(data.results || []);
            } catch {
                if (mounted) setRows([]);
            }
        }
        loadUsers();
        return () => {
            mounted = false;
        };
    }, []);

    return (
        <section className="grid gap-4">
            <PageHeader title="Users" subtitle="User lifecycle, authentication state, and account health." />
            <DataTable columns={columns} rows={rows} />
        </section>
    );
}
