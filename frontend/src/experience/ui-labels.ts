/** Presentation vocabulary only. Never use these labels in API or storage values. */
export const uiLabels = {
  details: "Details",
  editorial: "Editorial review",
  moment: "Moment",
  momentPlural: "moments",
  refreshMoment: "Refresh moment details.",
  reviewOutcome: { reject: "Moment rejected.", revise_range: "Range revision requested; moment location preserved.", defer: "Moment deferred.", approve_and_create_clip: "Review recorded." },
  approval: { unreviewed: "Awaiting review", approved: "Approved", rejected: "Rejected", revoked: "Approval withdrawn" },
  orderedByRecorder: "Ordered by recorder time",
  reviewMoment: "Review moment",
  singlePoint: "Single point: set start and end",
  rangeTime: "time into Session (mm:ss)",
  origin: { declared: "Marked", derived: "Suggested" },
  review: { unreviewed: "Awaiting review", approved: "Approved", rejected: "Rejected", revision_requested: "Range revision requested", deferred: "Deferred" },
  qualification: { unqualified: "Recorder time (unverified)", qualified: "Recorder time (verified)", rejected: "Recorder time (rejected)", expired: "Recorder time (verification expired)" },
  estimate: "Estimate",
  estimatedStart: "Estimated start",
  recorderLimitation: "Recorder start and length are unverified",
  newerTiming: "A newer timing estimate exists",
  live: "Live · connected",
  sessionTools: "Session tools",
  recordings: "Recordings",
  transcript: "Automatic transcript: may contain errors",
  assignment: { registered: "Found", associated: "In this Session", stabilizing: "Still recording", unresolved: "Needs a decision", conflict: "Claimed by two Sessions", conflicting: "Claimed by two Sessions" },
  lifecycle: { fixture: "Development fixture", declared: "Set by producer", observed: "Observed", derived: "Estimated", inferred: "Inferred", external: "External" },
  activity: { presentation_active: "Presentation active", presentation_ended: "Presentation ended", expected: "Expected" },
  package: { assembling: "Assembling", ready_for_review: "Ready for review", in_review: "In review", correction_required: "Review required", complete: "Complete" },
  upToDate: "Up to date",
  outOfDate: "Out of date: inputs changed",
  lockedOrder: "Order locked when proposed",
  renderCreated: "Requested",
  renderUpdated: "Last updated",
  renderNewestFirst: "Newest requests first.",
  renderMoreOperations: "Showing the latest 100 render operations. More operations exist.",
  render: { pending: "Rendering...", leased: "Rendering...", running: "Rendering...", succeeded: "Done", terminal_failed: "Failed", cancelled: "Cancelled", retry_scheduled: "Waiting to retry" },
  order: { media_timing: "Recorder time", timing_evidence: "Recorder time", registration_time: "Arrival time (no recorder time)" },
  layout: "Layout",
  slot: { opening_bumper: "Intro", title_card: "Title", sponsor_card: "Sponsor", outro: "Outro", session_media: "Recording", opening: "Intro", recording: "Recording" },
  testSetup: "Test setup · 1 stage · not event-ready",
  humanReview: "Suggestions need human review. No review or clip approval is automatic.",
} as const;

export function timingLabel(value?: string | null): string {
  return value && value in uiLabels.qualification ? uiLabels.qualification[value as keyof typeof uiLabels.qualification] : "";
}
export function renderLabel(value: string): string {
  return uiLabels.render[value as keyof typeof uiLabels.render] ?? value.replaceAll("_", " ");
}
export function slotLabel(value: string): string {
  return uiLabels.slot[value as keyof typeof uiLabels.slot] ?? value.replaceAll("_", " ");
}
export function renderProfileLabel(id: string, version: string): string {
  return id === "h264-nvenc-1080p-video" ? (version === "3" ? "1080p with audio (v3)" : `1080p (v${version})`) : `${id} (v${version})`;
}
export function unplacedRecordings(count: number): string {
  return `${count} ${count === 1 ? "recording needs" : "recordings need"} a decision: no Session fits ${count === 1 ? "it" : "them"}. Nothing was deleted.`;
}
export function assignmentReason(reasons: readonly string[], fallback: string): string {
  if (reasons.includes("no_safely_eligible_session")) return "No Session matches this recording's time.";
  return fallback;
}

export function outputConfirmation(action: "propose" | "render" | "approve" | "reject", item: import("./assembly-api.ts").AssemblyItem | null, _packageRevision: number, templateName?: string, quality?: string): string {
  const consequence = action === "propose"
    ? `Lock a new Assembly proposal using ${templateName ?? "the selected Event template"}.`
    : action === "render" ? `Queue a render of the approved Assembly in ${quality ?? "1080p with audio (v3)"}.`
    : `${action === "approve" ? "Approve" : "Reject"} this Assembly, including its locked recording order and layout.`;
  if (action === "propose") return `${consequence}\nRecording order and layout will be locked. Recordings may use arrival time or unverified recorder time; review the result before approval.`;
  const members = item?.revision.membership ?? [];
  const fallback = members.flatMap((m, i) => m.order_source === "registration_time" ? [i + 1] : []);
  const timing = members.flatMap((m, i) => m.order_source === "timing_evidence" && m.order_evidence_qualification !== "qualified" ? [`${i + 1}: ${timingLabel(m.order_evidence_qualification) || "Recorder time (verification unknown)"}`] : []);
  return [consequence,
    fallback.length ? `Arrival time (no recorder time): recordings ${fallback.join(", ")}. Arrival time does not tell you when content was recorded.` : "",
    timing.length ? `${timing.join("; ")}. Timing is an estimate.` : "",
    `Layout: ${item?.revision.bindings.filter((b) => b.outcome === "bound").map((b) => slotLabel(b.slot_key)).join(", ") || "No packaging"}.`,
  ].filter(Boolean).join("\n");
}


export const renderQualityLabels = {
  title: "Render quality", default: "Default", change: "Change", preset: "Preset",
  video: "Video bitrate", audio: "Audio bitrate", history: "Previous settings",
  consequence: "Applies to renders requested from now on. Existing outputs keep their quality.",
  confirm: "Confirm quality", review: "Review change", cancel: "Cancel",
  unavailable: "Render quality unavailable. Refresh before choosing quality or requesting a render.",
  readOnly: "Choosing quality requires a live Event and configured operator identity.",
  saved: "Render quality chosen.", changed: "Render quality changed. Review the current setting before confirming again.",
  failed: "Quality change not confirmed. Refresh and review the current setting.",
  unknown: "Connection lost; outcome unknown. Retry the same command.", retry: "Retry same command",
  working: "Saving quality...", again: "Render again at current quality",
  presets: { "h264-nvenc-1080p-video": "1080p Standard", "h264-nvenc-1080p-high": "1080p High", "h264-nvenc-720p": "720p Compact" },
} as const;
export function renderQualityLabel(value: { profile_id: string; profile_version: string; video_bit_rate?: number | null; audio_bit_rate?: number | null }): string {
  const defaults = value.profile_id === "h264-nvenc-1080p-video" && value.profile_version === "3" ? [8000000, 192000]
    : value.profile_id === "h264-nvenc-1080p-high" && value.profile_version === "1" ? [14000000, 256000]
    : value.profile_id === "h264-nvenc-720p" && value.profile_version === "1" ? [4000000, 128000] : undefined;
  if (!defaults) return renderProfileLabel(value.profile_id, value.profile_version);
  const name = renderQualityLabels.presets[value.profile_id as keyof typeof renderQualityLabels.presets];
  return `${name} · video ${(value.video_bit_rate ?? defaults[0]) / 1000000} Mbit/s · audio ${(value.audio_bit_rate ?? defaults[1]) / 1000} kbit/s`;
}
export function renderSettingProvenance(value: import("./rendering-api.ts").EventRenderSetting): string {
  return value.version === null ? renderQualityLabels.default : `Chosen by ${value.selected_by} · ${value.selected_at}`;
}
export function videoBitrateLabel(value: number): string { return `${value / 1000000} Mbit/s`; }
export function audioBitrateLabel(value: number): string { return `${value / 1000} kbit/s`; }
