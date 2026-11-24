import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, AlertCircle, Lock, ShieldCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const DEMO_ACCOUNTS = [
  { email: "lead.analyst@pulseiq.gov", role: "Admin / Lead Analyst", dept: "Civic Intelligence Directorate" },
  { email: "senior.analyst@pulseiq.gov", role: "Senior Analyst", dept: "Infrastructure & Policy Desk" },
  { email: "analyst@pulseiq.gov", role: "Analyst", dept: "Public Sentiment & Events Unit" },
  { email: "viewer@pulseiq.gov", role: "Viewer (Read-Only)", dept: "Executive Policy Briefing" },
];

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("lead.analyst@pulseiq.gov");
  const [password, setPassword] = useState("PulseIQ!2026");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-workspace">
      {/* Left Deep Navy Brand Panel */}
      <div className="hidden w-[440px] shrink-0 flex-col justify-between bg-navy-900 p-10 text-slate-300 lg:flex">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white shadow">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <div className="text-lg font-semibold tracking-tight text-white">PulseIQ</div>
              <div className="text-[10px] font-medium uppercase tracking-[0.16em] text-indigo-300">
                Enterprise Public Intelligence
              </div>
            </div>
          </div>

          <h1 className="mt-10 text-2xl font-semibold leading-snug tracking-tight text-white">
            Evidence-backed civic trend monitoring and public discussion intelligence.
          </h1>
          <p className="mt-3 text-xs leading-relaxed text-slate-400">
            Designed for policy, infrastructure, and civic operations analysts to detect emerging public themes,
            audit aggregate tone, verify primary source records, and author traceable intelligence briefings.
          </p>

          <div className="mt-8 space-y-3 border-t border-navy-700/80 pt-6 text-xs">
            <div className="flex items-start gap-2.5">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              <div>
                <p className="font-medium text-slate-200">Full Source Attribution & Auditability</p>
                <p className="text-[11px] text-slate-400">
                  Original source text stored independently from NLP outputs with human-in-the-loop override tracking.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-2.5">
              <Lock className="mt-0.5 h-4 w-4 shrink-0 text-indigo-400" />
              <div>
                <p className="font-medium text-slate-200">Ethical Public-Data Boundaries</p>
                <p className="text-[11px] text-slate-400">
                  Permitted public feeds and clearly labelled synthetic datasets only. Zero individual political profiling.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="font-mono text-[10px] text-slate-500">
          PULSEIQ ENTERPRISE v1.0 · POSTGRESQL + REDIS + CELERY + SCIKIT-LEARN NLP
        </div>
      </div>

      {/* Right Sign-In Form */}
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-md space-y-5">
          <div className="surface-panel p-7">
            <div className="mb-6">
              <h2 className="text-lg font-semibold tracking-tight text-slate-900">Analyst Sign In</h2>
              <p className="mt-1 text-xs text-slate-500">
                Authenticate with your PulseIQ enterprise workspace credentials.
              </p>
            </div>

            {error && (
              <div className="mb-4 flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800">
                <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="micro-label block mb-1">Work Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-field py-2"
                />
              </div>
              <div>
                <label className="micro-label block mb-1">Password</label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field py-2"
                />
              </div>
              <button
                type="submit"
                disabled={submitting}
                className="btn-primary w-full py-2.5 text-xs font-semibold"
              >
                {submitting ? "Authenticating..." : "Enter Intelligence Workspace"}
              </button>
            </form>
          </div>

          {/* Pre-seeded Role-Based Accounts */}
          <div className="surface-panel p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="micro-label">Pre-Seeded Role Accounts (Click to Fill)</span>
              <span className="font-mono text-[10px] text-slate-400">PW: PulseIQ!2026</span>
            </div>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {DEMO_ACCOUNTS.map((acc) => (
                <button
                  key={acc.email}
                  type="button"
                  onClick={() => {
                    setEmail(acc.email);
                    setPassword("PulseIQ!2026");
                  }}
                  className={`rounded border px-2.5 py-2 text-left transition ${
                    email === acc.email
                      ? "border-indigo-400 bg-indigo-50/60"
                      : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <div className="text-[11px] font-semibold text-slate-800">{acc.role}</div>
                  <div className="truncate font-mono text-[10px] text-slate-500">{acc.email}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
