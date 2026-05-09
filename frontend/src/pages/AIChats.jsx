import { useEffect, useState } from "react";
import PageHeader from "@/components/PageHeader";
import api from "@/services/api";

export default function AIChats() {
    const [threads, setThreads] = useState([]);
    const [messages, setMessages] = useState([]);
    const [selectedConversationId, setSelectedConversationId] = useState("");

    useEffect(() => {
        let mounted = true;
        async function loadThreads() {
            try {
                const { data } = await api.get("transactions/chat_conversations/");
                const convos = data.conversations || [];
                if (mounted) {
                    setThreads(convos);
                    if (convos[0]?.conversation_id) {
                        setSelectedConversationId(convos[0].conversation_id);
                    }
                }
            } catch {
                if (mounted) setThreads([]);
            }
        }
        loadThreads();
        return () => {
            mounted = false;
        };
    }, []);

    useEffect(() => {
        if (!selectedConversationId) return;
        let mounted = true;
        async function loadMessages() {
            try {
                const { data } = await api.get("transactions/chat_history/", {
                    params: { conversation_id: selectedConversationId },
                });
                if (mounted) setMessages(data.messages || []);
            } catch {
                if (mounted) setMessages([]);
            }
        }
        loadMessages();
        return () => {
            mounted = false;
        };
    }, [selectedConversationId]);

    return (
        <section className="grid gap-4">
            <PageHeader title="AI Chats" subtitle="Conversation thread viewer for audit, tuning, and support." />

            <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
                <aside className="rounded-2xl border border-stroke bg-card p-3 shadow-glow">
                    {threads.map((thread) => (
                        <button
                            key={thread.conversation_id}
                            type="button"
                            onClick={() => setSelectedConversationId(thread.conversation_id)}
                            className="mb-2 w-full rounded-xl border border-transparent bg-white/5 p-3 text-left hover:border-stroke hover:bg-white/10"
                        >
                            <p className="text-sm font-semibold text-text">Conversation</p>
                            <p className="truncate text-xs text-muted">{thread.preview}</p>
                            <p className="mt-1 text-[11px] text-muted">{new Date(thread.last_message_at).toLocaleString()}</p>
                        </button>
                    ))}
                </aside>

                <article className="rounded-2xl border border-stroke bg-card p-6 shadow-glow">
                    <p className="mb-4 text-sm text-muted">Thread Viewer</p>
                    <div className="space-y-4">
                        {messages.map((msg, idx) => (
                            <div
                                key={`${msg.created_at}-${idx}`}
                                className={
                                    msg.role === "ai"
                                        ? "ml-auto max-w-[75%] rounded-xl bg-primary/20 p-3 text-sm text-text"
                                        : "max-w-[75%] rounded-xl bg-white/10 p-3 text-sm text-text"
                                }
                            >
                                <span className="mb-1 block text-[11px] uppercase tracking-wide text-muted">{msg.role}</span>
                                {msg.message}
                            </div>
                        ))}
                    </div>
                </article>
            </div>
        </section>
    );
}
