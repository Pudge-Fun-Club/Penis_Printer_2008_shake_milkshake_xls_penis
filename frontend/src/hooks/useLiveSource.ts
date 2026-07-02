import { useEffect } from "react";
import type { useLiveStream } from "../features/stream/hooks/useLiveStream";

type Live = ReturnType<typeof useLiveStream>;

/** The three live-stream effects every broadcasting view repeats: push a fresh
 * snapshot when the watched content changes, switch to a placeholder while the
 * view is hidden, and surface connection errors. Auto-start conditions differ
 * per view and stay at the call site. */
export function useLiveSource(
  live: Live,
  opts: {
    visible: boolean;
    hiddenReason: string;
    onError: (message: string) => void;
    /** Values whose change should re-broadcast the current snapshot. */
    snapshotDeps: unknown[];
  }
) {
  const { visible, hiddenReason, onError } = opts;

  useEffect(() => {
    if (live.state === "live") live.sendSnapshot("snapshot");
    // The caller owns the list of values that invalidate the snapshot.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...opts.snapshotDeps, live.state]);

  useEffect(() => {
    if (visible || live.state !== "live") return;
    live.sendPlaceholder(hiddenReason);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, live.state, hiddenReason]);

  useEffect(() => {
    if (live.error) onError(live.error);
  }, [live.error, onError]);
}
