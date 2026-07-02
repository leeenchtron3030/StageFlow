# mock_data

## Purpose

This directory is reserved for safe mock data used by tests, examples, and local development.

## What Belongs Here

- Synthetic fixtures approved by future Engineering Directives.
- Small sample files that do not contain real conference, session, speaker, sponsor, attendee, or media data.
- Data sets used to exercise tests or examples after the relevant implementation layer exists.

## What Does Not Belong Here

- Real production data.
- Personally identifiable information.
- Raw media captures, recordings, transcripts, or exports.
- Database dumps or generated runtime state.

## Expected Future Directives

- ED-0002 Backend Foundation may add backend fixtures.
- ED-0003 Frontend Foundation may add frontend fixtures.
- Future testing directives may add scenario-specific mock data.
