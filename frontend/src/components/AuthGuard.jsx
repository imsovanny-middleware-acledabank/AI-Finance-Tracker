import { useAuth } from "@/context/AuthContext";

export default function AuthGuard({ children, allowedRoles = ["viewer", "manager", "admin"] }) {
    const { loading, isAuthenticated, role } = useAuth();

    if (loading) {
        return <div className="grid min-h-screen place-items-center bg-bg text-muted">Loading session…</div>;
    }

    if (!isAuthenticated) {
        window.location.href = "/login/?next=/app/";
        return null;
    }

    if (!allowedRoles.includes(role)) {
        return (
            <div className="grid min-h-screen place-items-center bg-bg text-text">
                <div className="rounded-2xl border border-stroke bg-card p-8 text-center">
                    <h2 className="text-xl font-semibold">Access denied</h2>
                    <p className="mt-2 text-sm text-muted">Your role ({role}) cannot access this page.</p>
                </div>
            </div>
        );
    }

    return children;
}
