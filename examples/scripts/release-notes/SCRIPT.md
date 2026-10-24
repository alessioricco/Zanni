---
name: release-notes
version: 0.1.0
mission: Turn a changelog into release notes people want to read, every change covered, checked by a verifier.
parts:
  writer:
    description: Drafts the release notes from the changelog and the style guide.
    suggested: ../../roles/notes-writer
    writes: [notes/]
  editor:
    description: Revises the draft for clarity and tone, keeping every change.
    suggested: ../../roles/notes-editor
    writes: [notes/]
stage:
  expects: [changelog.md, style.md, checks/structure.py]
gates: [publish]
verifiers:
  notes-structure:
    description: notes/release-notes.md has the style guide's sections, and mentions every change in the changelog
    command: [python3, checks/structure.py]
    timeout: 60
stop:
  max_rounds: 1
  done_when: [notes-structure]
---

# Release notes

The stage holds `changelog.md`, the raw list of this release's changes, each with its issue number, and `style.md`,
how the notes should read. The work is `notes/release-notes.md`.

## Scene 1: Draft
The **writer** reads `changelog.md` and `style.md`, and writes `notes/release-notes.md`: every change, in the
sections the style guide names, written for the people who use the product.

## Scene 2: Edit
The **editor** reads the draft, `changelog.md` and `style.md`, and revises `notes/release-notes.md` in place: clearer,
shorter, the same changes. The editor and the writer never work at the same time.
*Verifier:* `notes-structure`. If it fails, give the editor one more cue with what it says is missing.

**Gate: publish.** A person reads the notes and approves them. On a rejection, the editor revises with the note.

When `notes-structure` passes on the approved notes, the play is done.
