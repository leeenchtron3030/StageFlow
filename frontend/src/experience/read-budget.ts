/** A shared wall-clock deadline, including response-body reads and queued work. */
export function createReadBudget(milliseconds = 5_000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), milliseconds);
  return {
    signal: controller.signal,
    async read<T>(read: () => Promise<T>): Promise<T> {
      if (controller.signal.aborted) throw new Error("read_budget_exhausted");
      return new Promise<T>((resolve, reject) => {
        const exhausted = () => reject(new Error("read_budget_exhausted"));
        controller.signal.addEventListener("abort", exhausted, { once: true });
        Promise.resolve().then(read).then(resolve, reject).finally(() => {
          controller.signal.removeEventListener("abort", exhausted);
        });
      });
    },
    dispose() { clearTimeout(timer); },
  };
}
export type ReadBudget = ReturnType<typeof createReadBudget>;
