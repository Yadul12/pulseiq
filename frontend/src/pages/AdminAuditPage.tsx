import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Shield, Users } from "lucide-react";
import { apiRequest } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { User } from "../types";

interface AuditEntry {
  id: number;
  actor_email: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  details: Record<string, unknown>;
  ip_address?: string | null;
  created_at: string;
}

export const AdminAuditPage: React.FC = () => {
  const { canWrite } = useAuth();
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");

  const { data: users = [] } = useQuery<User[]>({
    queryKey: ["users-list"],
    queryFn: () => apiRequest<User[]>("/auth/users"),
    enabled: canWrite,
  });

  const { data: auditData, isLoading } = useQuery<{
    total: number;
    page: number;
    page_size: number;
    items: AuditEntry[];
  }>({
    queryKey: ["audit-logs", page, actionFilter],
    queryFn: () =>
      apiRequest(
        `/audit-logs?page=${page}&page_size=20${
          actionFilter.trim() ? `&action=${encodeURIComponent(actionFilter.trim())}` : ""
        }`
      ),
  });

  const totalPages = Math.max(1, Math.ceil((auditData?.total ?? 0) / 20));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-base font-semibold tracking-tight text-slate-900">Audit Trail & Role-Based Access</h1>
        <p className="text-xs text-slate-500">
          Immutable log of analyst logins, topic configuration changes, ingestion executions, classification overrides, and report generation
        </p>
      </div>

      {/* Team Directory */}
      {canWrite && users.length > 0 && (
        <div className="surface-panel overflow-hidden">
          <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-3">
            <Users className="h-4 w-4 text-indigo-700" />
            <h2 className="section-heading">Workspace RBAC Directory</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-2">Analyst</th>
                  <th className="px-3 py-2">Email</th>
                  <th className="px-3 py-2">Department</th>
                  <th className="px-3 py-2">Role</th>
                  <th className="px-4 py-2 text-right">Last Sign-In</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="px-4 py-2 font-medium text-slate-900">{u.full_name}</td>
                    <td className="px-3 py-2 font-mono text-[11px] text-slate-600">{u.email}</td>
                    <td className="px-3 py-2 text-slate-600">{u.department}</td>
                    <td className="px-3 py-2">
                      <span className="rounded border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase text-indigo-800">
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-mono text-[10px] text-slate-500">
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Immutable Audit Log */}
      <div className="surface-panel overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-indigo-700" />
            <h2 className="section-heading">Governance Audit Log ({auditData?.total.toLocaleString() ?? 0})</h2>
          </div>
          <input
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setPage(1);
            }}
            placeholder="Filter action (e.g. override, report, topic)..."
            className="input-field w-64"
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 bg-slate-50 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-2">Timestamp</th>
                <th className="px-3 py-2">Actor</th>
                <th className="px-3 py-2">Action</th>
                <th className="px-3 py-2">Resource</th>
                <th className="px-4 py-2">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="p-6 text-center text-slate-400">
                    Loading audit log...
                  </td>
                </tr>
              ) : (
                (auditData?.items ?? []).map((entry) => (
                  <tr key={entry.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2 font-mono text-[10px] text-slate-500 whitespace-nowrap">
                      {new Date(entry.created_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2 font-mono text-[11px] text-slate-700">{entry.actor_email}</td>
                    <td className="px-3 py-2">
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] font-medium text-slate-800">
                        {entry.action}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-[10px] text-indigo-700">
                      {entry.resource_type}
                      {entry.resource_id ? `#${entry.resource_id}` : ""}
                    </td>
                    <td className="max-w-md truncate px-4 py-2 font-mono text-[10px] text-slate-500">
                      {JSON.stringify(entry.details)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/70 px-4 py-2 text-xs text-slate-600">
          <span className="font-mono text-[11px] tabular-nums">
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-1.5">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="btn-secondary px-2 py-1">
              <ChevronLeft className="h-3.5 w-3.5" /> Prev
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="btn-secondary px-2 py-1"
            >
              Next <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
