import React, { createContext, useCallback, useContext, useState } from "react";

export interface ToastMessage {
  id: number;
  type: "success" | "error" | "info";
  title: string;
  detail?: string;
}

interface WorkspaceContextValue {
  days: number;
  setDays: (d: number) => void;
  sourceId: number | null;
  setSourceId: (id: number | null) => void;
  inspectedRecordId: number | null;
  openRecordInspector: (recordId: number) => void;
  closeRecordInspector: () => void;
  toasts: ToastMessage[];
  pushToast: (type: ToastMessage["type"], title: string, detail?: string) => void;
  dismissToast: (id: number) => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [days, setDays] = useState<number>(30);
  const [sourceId, setSourceId] = useState<number | null>(null);
  const [inspectedRecordId, setInspectedRecordId] = useState<number | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const pushToast = useCallback((type: ToastMessage["type"], title: string, detail?: string) => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((prev) => [...prev.slice(-3), { id, type, title, detail }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <WorkspaceContext.Provider
      value={{
        days,
        setDays,
        sourceId,
        setSourceId,
        inspectedRecordId,
        openRecordInspector: setInspectedRecordId,
        closeRecordInspector: () => setInspectedRecordId(null),
        toasts,
        pushToast,
        dismissToast,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return ctx;
}
