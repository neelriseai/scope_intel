# Project Overview

This project defines a deterministic system to guide AI assistants (Claude, Cursor, Codex) in consuming fewer tokens during debugging, input document reading, and output generation.

## Core Idea
- Do not scan entire repositories.
- Narrow context in three stages:
  1. Identify target feature.
  2. Retrieve compact scope slice.
  3. Open only minimal code/tests.

## Benefits
- Reduced token waste.
- Faster context retrieval.
- Clear separation of **global reusable heuristics** vs **repo-specific truth**.
