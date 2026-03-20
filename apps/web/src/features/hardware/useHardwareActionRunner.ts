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
  ) {
    try {
      setActionName(name);
      setError(null);
      setActionFeedback({
        action: name,
        message: messages.pending,
        tone: "info",
      });
      await action();
      await refresh({ silent: true });
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
