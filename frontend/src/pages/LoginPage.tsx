import { CreditCard } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, type Tokens } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { wsUrl } from "../lib/live";

const CARD_READER = import.meta.env.VITE_CARD_READER ?? "CARD-01";

type DemoAccount = { role: string; username: string; password: string };

const ROLE_LABEL: Record<string, string> = { CirculationClerk: "Circulation Clerk" };

export function LoginPage() {
  const { login, loginWithTokens } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [waitingForCard, setWaitingForCard] = useState(false);
  const socket = useRef<WebSocket | null>(null);
  const [demoAccounts, setDemoAccounts] = useState<DemoAccount[]>([]);

  useEffect(() => () => socket.current?.close(), []);

  // Public demonstration instances list sign-in details; everywhere else the list is empty.
  useEffect(() => {
    api<DemoAccount[]>("/auth/demo-accounts")
      .then((accounts) => setDemoAccounts(Array.isArray(accounts) ? accounts : []))
      .catch(() => setDemoAccounts([]));
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  async function tapCard() {
    setError(null);
    try {
      const { challenge_id } = await api<{ challenge_id: string }>("/auth/smartcard/challenge", {
        method: "POST",
        body: JSON.stringify({ reader_code: CARD_READER }),
      });
      setWaitingForCard(true);
      const ws = new WebSocket(wsUrl("/ws/card", { reader: CARD_READER, challenge_id }));
      socket.current = ws;
      const timeout = setTimeout(() => {
        ws.close();
        setWaitingForCard(false);
        setError("No card was tapped. Please try again.");
      }, 60_000);
      ws.onmessage = async () => {
        clearTimeout(timeout);
        ws.close();
        try {
          const tokens = await api<Tokens>("/auth/smartcard", {
            method: "POST",
            body: JSON.stringify({ reader_code: CARD_READER, challenge_id }),
          });
          await loginWithTokens(tokens);
          navigate("/");
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Card sign-in failed");
        } finally {
          setWaitingForCard(false);
        }
      };
    } catch (err) {
      setWaitingForCard(false);
      setError(err instanceof ApiError ? err.message : "Card reader unavailable");
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 py-8">
      <form onSubmit={submit} className="w-80 space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-semibold text-indigo-700">Nexus sign in</h1>
        <label className="block text-sm">
          Username or card number
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label className="block text-sm">
          Password
          <input
            type="password"
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        <button disabled={busy} className="w-full rounded bg-indigo-600 py-2 text-white disabled:opacity-50">
          Sign in
        </button>
        <button
          type="button"
          onClick={() => void tapCard()}
          disabled={waitingForCard}
          className="flex w-full items-center justify-center gap-2 rounded border border-slate-300 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          <CreditCard size={16} aria-hidden />
          {waitingForCard ? `Tap your card on ${CARD_READER}…` : "Tap staff card"}
        </button>
      </form>
      {demoAccounts.length > 0 && (
        <section aria-labelledby="demo-accounts" className="w-80 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm">
          <h2 id="demo-accounts" className="font-semibold text-amber-900">
            Demo accounts
          </h2>
          <p className="mt-1 text-xs text-amber-800">Synthetic data on a demonstration instance.</p>
          <ul className="mt-3 space-y-2">
            {demoAccounts.map((a) => (
              <li key={a.username} className="flex items-center justify-between gap-2">
                <span>
                  <span className="font-medium">{ROLE_LABEL[a.role] ?? a.role}</span>
                  <br />
                  <code className="text-xs text-slate-700">
                    {a.username} / {a.password}
                  </code>
                </span>
                <button
                  type="button"
                  aria-label={`Use the ${ROLE_LABEL[a.role] ?? a.role} account`}
                  onClick={() => {
                    setUsername(a.username);
                    setPassword(a.password);
                  }}
                  className="rounded border border-amber-300 bg-white px-2 py-1 text-xs hover:bg-amber-100"
                >
                  Use
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
