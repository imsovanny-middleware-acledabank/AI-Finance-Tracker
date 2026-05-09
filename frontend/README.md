# Premium Admin SPA (React + Tailwind)

This folder contains a production-ready SPA skeleton for AI Finance Bot admin.

## Information Architecture (IA)

### Primary navigation
- Dashboard (KPIs + chart area)
- Transactions (table + filters + bulk ops)
- Users
- Budgets
- AI Chats (thread viewer)
- Settings

### Global patterns
- Topbar: search, notifications, profile
- Sidebar: collapsible, icon + label
- Content: cards + data tables
- Right panel: contextual filters by current route

## Tech stack
- React + React Router
- Tailwind CSS
- Axios service layer with token interceptor
- Vite build system

## Key files
- `src/layouts/AppLayout.jsx` — shell layout + right panel behavior
- `src/data/navigation.js` — IA navigation source of truth
- `src/services/api.js` — API client (`VITE_API_BASE_URL`)
- `src/pages/*` — route pages

## Environment
Create `.env` from `.env.example`:
- `VITE_API_BASE_URL=http://localhost:8000/api/`

## Run locally
1. install dependencies (`npm install`)
2. start dev server (`npm run dev`)
3. build for production (`npm run build`)
