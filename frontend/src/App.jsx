import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "@/layouts/AppLayout";
import AuthGuard from "@/components/AuthGuard";
import { AuthProvider } from "@/context/AuthContext";
import Dashboard from "@/pages/Dashboard";
import Transactions from "@/pages/Transactions";
import Users from "@/pages/Users";
import Budgets from "@/pages/Budgets";
import AIChats from "@/pages/AIChats";
import Settings from "@/pages/Settings";

export default function App() {
    return (
        <AuthProvider>
            <Routes>
                <Route
                    element={
                        <AuthGuard>
                            <AppLayout />
                        </AuthGuard>
                    }
                >
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/transactions" element={<Transactions />} />
                    <Route path="/users" element={<AuthGuard allowedRoles={["admin"]}><Users /></AuthGuard>} />
                    <Route path="/budgets" element={<Budgets />} />
                    <Route path="/chats" element={<AIChats />} />
                    <Route path="/settings" element={<AuthGuard allowedRoles={["admin"]}><Settings /></AuthGuard>} />
                </Route>
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </AuthProvider>
    );
}
