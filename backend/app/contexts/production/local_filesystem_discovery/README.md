# Local Filesystem Candidate Discovery

ED-0053 is StageFlow's first concrete media-source adapter. It implements only the
ED-0052 `MediaCandidateDiscoveryPort`: one caller-supplied request inspects one
explicitly configured local-file or mounted-volume target, once.

The adapter supports an expected single file or the immediate children of one
shallow directory. It never recurses, follows symlinks, expands wildcards, watches,
polls, retries, opens media content, or retains discovery history. A directory binding
has an explicit entry-examination bound independent of the request's candidate bound.
An oversized directory is blocked without returning an arbitrary enumeration-order
subset. Eligible entries are filtered and ordered deterministically before candidate
truncation.

For shallow-directory discovery, POSIX platforms that expose descriptor-based
`os.scandir` plus no-follow directory-open flags bind enumeration and child inspection to
the validated directory object. The opened descriptor identity must match the initial
target identity. Windows and other platforms without that Python/OS support use pathname
inspection with identity revalidation after enumeration and again after child
inspection. Persistent missing, inaccessible, symlinked, non-directory, or changed
targets fail closed and return no candidates. The fallback cannot detect a transient
swap-and-restore entirely between checkpoints, and filesystems without meaningful
device/object identifiers receive only type/symlink revalidation. Deployments must not
claim stronger guarantees. Later media-content access must independently revalidate its
own target and authority.

Eligibility is immutable configuration: extension matching, deliberate allow-all,
hidden-entry handling, regular-file enforcement, excluded suffixes, and optional
extension-derived hints are explicit. Extensions and filenames remain descriptive;
they do not validate media, establish production context, or prove finalization.
Active and zero-byte files may therefore remain candidates.

Candidate identities use Runtime, host, volume, target, normalized location, and an
opaque stable filesystem object token when the platform supplies one. Location-scoped
fallback remains deterministic and carries first-class limitations. Deployment profile
is provenance, not a trust tier or identity input.

Agent, Node, and Development Runtime profiles map to first-class canonical candidate
provenance. In particular, Development remains `development`; it is not converted to
`unknown` and metadata is not required to recover it. `unknown` remains available only
for genuinely unavailable or unresolved provenance in the shared media contract.
Profile does not affect eligibility, ordering, identity, readiness, or future asset
meaning.

The request's timezone-aware `requested_at` anchors candidate first observation,
discovery wrappers, and result start/completion. No wall clock or duration measurement
is used. Stage and recording-block context come only from the ED-0050 target binding.

This package performs read-only metadata inspection only. It does not assess size
stability, write state, readability, finalization, completion, or readiness; construct
a Completed Media Asset or Production Event; transfer or persist media; use networking;
or create a command, worker, daemon, queue, watcher, or service.
