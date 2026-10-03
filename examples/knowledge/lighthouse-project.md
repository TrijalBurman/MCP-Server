# Lighthouse project

Lighthouse is a small offline study assistant. Its goal is to help a student find
their own notes and continue project work without repeating old context.

## Goals

- Search local lecture notes, Markdown, text-based PDFs, and source code.
- Show the filename behind each answer.
- Keep explicit project decisions across restarts.
- Draft a project plan using a model running on the laptop.

## Storage decision

Use a local SQLite database for extracted document text, searchable chunks,
conversation history, and project memories. Keep original source files in their
existing folders. Never send document contents to a paid API.

## First milestone

Create a tiny reference library, verify retrieval with known facts, and compare a
summary with its cited source text before indexing a larger collection.

## Open question

Scanned PDFs contain image pages. A future version may add local OCR, but the
first milestone supports PDFs with extractable text only.
