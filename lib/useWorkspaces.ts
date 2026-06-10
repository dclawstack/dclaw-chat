"use client";

import { useCallback, useEffect, useState } from "react";
import { listWorkspaces, Workspace } from "./api";

const STORAGE_KEY = "dclaw_workspace";

/** Read the currently-selected workspace id (e.g. for one-off API calls). */
export function getStoredWorkspaceId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(STORAGE_KEY);
}

export interface UseWorkspacesResult {
  workspaces: Workspace[];
  currentId: string | null;
  setCurrent: (id: string | null) => void;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

/**
 * Minimal current-workspace state: lists workspaces and persists the
 * selected id in localStorage. Full workspace management UI is out of scope.
 */
export function useWorkspaces(): UseWorkspacesResult {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const ws = await listWorkspaces();
      setWorkspaces(ws);
      // Keep the stored selection if still valid, otherwise default to first.
      const stored = getStoredWorkspaceId();
      const valid = stored && ws.some((w) => w.id === stored) ? stored : ws[0]?.id ?? null;
      setCurrentId(valid);
      if (valid) window.localStorage.setItem(STORAGE_KEY, valid);
      else window.localStorage.removeItem(STORAGE_KEY);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load workspaces");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setCurrent = useCallback((id: string | null) => {
    setCurrentId(id);
    if (typeof window === "undefined") return;
    if (id) window.localStorage.setItem(STORAGE_KEY, id);
    else window.localStorage.removeItem(STORAGE_KEY);
  }, []);

  return { workspaces, currentId, setCurrent, isLoading, error, refresh };
}
