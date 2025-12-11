## Frontend (Next.js + Vercel AI SDK)

This UI streams responses from the LangGraph backend via the Vercel AI SDK data
stream protocol.

### Run locally
```bash
npm install
npm run dev
# open http://localhost:3000
```

Environment:
- `NEXT_PUBLIC_API_BASE` (optional) — backend base URL, defaults to `http://localhost:8000`

### What it does
- Uses `useChat` from `@ai-sdk/react` with a custom transport to `POST /chat`.
- Renders a simple chat UI that streams reasoning + final answers.
