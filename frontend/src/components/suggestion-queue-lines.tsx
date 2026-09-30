import Link from "next/link";
import type { SuggestionQueueItem } from "../experience/session-suggestions-api.ts";
import { suggestionLabels as labels } from "../experience/ui-labels.ts";
import { closerLook } from "../experience/session-suggestions.ts";

export function SuggestionQueueLines({ items, stages }: { items?: SuggestionQueueItem[]; stages: { id: string; key: string; name: string }[] }) {
  if (!items) return <p role="status">{labels.queueUnavailable}</p>;
  const lines = stages.flatMap((stage) => {
    const item = items.find((i) => i.stage_id === stage.id && i.decision_type === "presentation_confirmation_pending" && i.subject_kind === "stage_suggestions" && i.action_reference === `stage:${stage.id}:suggestions`);
    if (!item) return [];
    const count = (key: string) => { const code = item.reason_codes.find((c) => new RegExp(`^${key}:\\d+$`).test(c)); return code ? Number(code.split(":")[1]) : undefined; };
    const open = count("open_count"), weak = count("weak_count");
    if (open === 0) return [];
    const summary = open === undefined ? "Suggestions to review" : `${open} ${open === 1 ? "suggestion" : "suggestions"} to review${weak ? ` (${closerLook(weak)})` : ""}`;
    return [<li key={stage.id}><Link className="text-link" href={`/stages/${encodeURIComponent(stage.key)}#suggested-presentations`}>{stage.name}</Link><span>{summary}</span></li>];
  });
  return lines.length ? <section className="suggestion-queue-lines" aria-label="Suggestions to review"><h2>Suggestions to review</h2><ul>{lines}</ul></section> : null;
}
