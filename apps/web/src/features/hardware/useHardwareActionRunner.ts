import { useState } from "react";

import type { ActionFeedback, ActionName } from "./hardwareDashboardTypes";

export function useHardwareActionRunner({
  refresh,
  setError,
}: {
  refresh: (options?: { silent?: boolean; allowInitialAutoStart?: boolean }) => Promise<void>;
  setError: (message: string | null) => void;
}) {
  const [actionName, setActionName] = useState<ActionName>(null);
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null);

  async function runAction(
    name: Exclude<ActionName, null>,
    action: () => Promise<unknown>,
    messages: {
      pending: string;
      success: string;
    },
    options?: {
      onSuccess?: (result: unknown) => void;
      ignoreRefreshErrors?: boolean;
    },
  ) {
    try {
      setActionName(name);
      setError(null);
      setActionFeedback({
        action: name,
        message: messages.pending,
        tone: "info",
      });
      const result = await action();
      options?.onSuccess?.(result);
      try {
        await refresh({ silent: true });
      } catch (refreshError) {
        if (!options?.ignoreRefreshErrors) {
          throw refreshError;
        }
      }
      setActionFeedback({
        action: name,
        message: messages.success,
        tone: "success",
      });
    } catch (actionError) {
      const message =
        actionError instanceof Error ? actionError.message : "Action failed.";
      setError(message);
      setActionFeedback({
        action: name,
        message,
        tone: "error",
      });
    } finally {
      setActionName(null);
    }
  }

  return {
    actionName,
    actionFeedback,
    runAction,
  };
}
