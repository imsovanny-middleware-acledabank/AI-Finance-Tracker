import {
    BadgeDollarSign,
    Bot,
    ChartNoAxesCombined,
    Settings,
    Users,
    Wallet,
} from "lucide-react";

export const navItems = [
    { to: "/", label: "Dashboard", icon: ChartNoAxesCombined },
    { to: "/transactions", label: "Transactions", icon: BadgeDollarSign },
    { to: "/users", label: "Users", icon: Users },
    { to: "/budgets", label: "Budgets", icon: Wallet },
    { to: "/chats", label: "AI Chats", icon: Bot },
    { to: "/settings", label: "Settings", icon: Settings },
];
