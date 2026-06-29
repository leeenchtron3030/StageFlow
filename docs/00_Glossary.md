StageFlow Glossary

Document: docs/00_Glossary.md
Specification Version: 1.0
Status: Approved (Foundational)
Depends On: PRODUCT_CONSTITUTION.md
Referenced By: All Specifications

⸻

Purpose

This glossary defines the official terminology used throughout StageFlow.

Every specification document, source file, API endpoint, database schema, and user interface should use these definitions consistently.

If a term is defined here, it should not be redefined elsewhere.

⸻

Terminology Categories

The glossary is divided into four groups:

* Business Objects
* Editorial Objects
* Technical Objects
* Operational Terms

⸻

Business Objects

Organization

The highest-level owner of one or more events.

Examples:

* Ethereum Foundation
* The Last Bookstore
* TED
* SXSW

An Organization owns branding, users, assets, and events.

⸻

Event

A scheduled production managed by StageFlow.

Examples:

* Devcon Mumbai 2026
* ETHDenver
* Literary Festival 2027

An Event contains stages, sessions, speakers, editorial settings, and branding.

⸻

Stage

A physical or virtual presentation area producing media.

Examples:

* Main Stage
* Community Stage
* Music Stage

Each Stage has its own ingest source.

⸻

Session

The primary editorial object.

A Session represents one continuous scheduled presentation.

Examples:

* Keynote
* Panel
* Workshop
* Interview
* Performance

Everything produced by StageFlow ultimately belongs to a Session.

⸻

Speaker

An individual participating in one or more Sessions.

A Speaker exists independently of any individual Session.

⸻

Editorial Objects

Session Timeline

A continuous editorial representation of a Session.

The Session Timeline exists independently of underlying media files.

Reviewers interact with the Session Timeline rather than individual recordings.

⸻

Timeline Segment

A portion of a Session Timeline corresponding to newly available media and transcript information.

Timeline Segments connect Media Chunks to the continuous Session Timeline.

Users generally never see Timeline Segments.

⸻

Candidate Moment

A proposed editorial highlight generated either automatically or manually.

A Candidate Moment has not yet been approved.

Candidate Moments may become Clips after review.

⸻

Clip

A human-approved editorial selection.

A Clip represents publishable content.

Every Clip originates from a Candidate Moment.

⸻

Hot Moment

An urgency designation.

A Hot Moment indicates content requiring immediate reviewer attention.

Hot Moment is independent of editorial tier.

⸻

Editorial Brief

A structured description of editorial priorities.

Examples include:

* priority topics
* excluded subjects
* event goals
* desired messaging
* campaign themes

Editorial Briefs guide the Editorial Intelligence Service.

⸻

Session Package

The complete collection of deliverables associated with a Session.

May include:

* Full Talk
* Approved Clips
* Transcript
* Captions
* Metadata
* Delivery Assets

The Session Package is the primary deliverable provided to presenters and stakeholders.

⸻

Technical Objects

Media Chunk

A recorded media file produced by the recording system.

Media Chunks exist for operational reliability.

They are not editorial objects.

⸻

Transcript Segment

A timestamped portion of transcribed speech corresponding to newly processed media.

Transcript Segments combine to form a complete Session Transcript.

⸻

Session Transcript

The continuously growing transcript associated with a Session.

The Session Transcript is treated as one continuous document.

⸻

Export

A rendered media asset.

Examples:

* Vertical
* Square
* Landscape

One Clip may generate multiple Exports.

⸻

Delivery

The process of providing completed Session Packages to recipients.

Delivery may occur via:

* secure download link
* QR code
* manual transfer
* future automated integrations

⸻

Activity

A permanent record of a meaningful system event.

Examples:

* Session Started
* Candidate Created
* Clip Approved
* Package Completed

Activities power the live ticker, audit trail, and event replay.

⸻

Job

An asynchronous unit of work executed by the processing system.

Examples:

* transcription
* rendering
* package assembly
* delivery generation

Jobs are invisible to most users.

⸻

Operational Terms

Live Review

Human review occurring while a Session is still active.

⸻

Technical Verification

The final review performed before a Session Package is delivered.

⸻

Archive

Permanent storage of all media, metadata, transcripts, decisions, and activity generated during an Event.

Archives are never automatically deleted.

⸻

Simulation Mode

A replay environment used to test workflows, train staff, and measure system performance without affecting live production.

⸻

Continuous Editorial Pipeline

The operational philosophy that all possible work begins immediately rather than waiting for Session completion.

⸻

Graceful Degradation

The ability of StageFlow to continue delivering useful functionality when one or more subsystems become unavailable.

⸻

Offline-First Operation

The ability to conduct an entire event using only local infrastructure without requiring Internet connectivity.

⸻

Naming Conventions

Throughout StageFlow:

Business-facing language should remain simple and intuitive.

Internal implementation names may be more technical but should map directly to glossary terms.

Avoid introducing synonyms for defined objects.

Example:

Use Candidate Moment consistently.

Do not alternatively refer to it as:

* Suggested Clip
* Proposed Highlight
* AI Clip
* Clip Candidate

⸻

Reserved Terms

The following names are reserved and should retain their specific meanings throughout the project:

* Organization
* Event
* Stage
* Session
* Speaker
* Session Timeline
* Timeline Segment
* Media Chunk
* Transcript Segment
* Session Transcript
* Candidate Moment
* Clip
* Hot Moment
* Export
* Session Package
* Editorial Brief
* Delivery
* Activity
* Archive
* Simulation Mode

⸻

Glossary Governance

New terminology should only be added when existing terms cannot accurately describe new functionality.

Redundant or overlapping terminology should be avoided.

The glossary exists to reduce ambiguity, not increase it.
