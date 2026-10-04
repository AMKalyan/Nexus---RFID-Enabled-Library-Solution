# Nexus frontend

React + TypeScript single-page app for staff (circulation, cataloguing, tagging, inventory, gate monitor, reports, administration) and patrons (OPAC, own loans).

```bash
npm ci
npm run dev      # http://localhost:5173, proxies /api to the backend on :8000
npm test         # unit tests (vitest)
npm run build    # production bundle served by nginx
```

Access tokens are held in memory only. Every permission is enforced by the API; the UI only hides actions a role cannot use.
