# How this repository was made ({{NAME}})

This file is written by the build on {{DOCS_DATE}}, the day the source data was retrieved.

## Sources

| Source | Address | Retrieved | Licence |
| --- | --- | --- | --- |
{{SOURCES}}

Every word of law in this repository comes from these sources. Lexifina reads them and records each act's dated versions, and the laws that made each change, in one corpus file. This repository is built from that file.

## What is in it

| Act | Title | Versions | Span |
| --- | --- | ---: | --- |
{{ACTS}}

The build made {{COMMITS}} commits:

| Commits | Kind |
| ---: | --- |
| {{START_COMMITS}} | baseline texts where the record starts |
| {{LAW_COMMITS}} | named laws, court decisions and treaties |
| {{UNEXPLAINED}} | changes no amendment note explains, credited to the publisher |
| {{CORRECTIONS}} | corrections to the existing record |
| {{PRINTING}} | printing or layout changes |

Other counts:
- {{FUTURE}} commits on the branch `{{FUTURE_BRANCH}}`: laws not yet in force on {{DOCS_DATE}}.
- {{CLAMPED}} commits dated 1 January 1970: in force before 1970, with the real day in their `In-force` trailer.
- {{LAWS}} laws in the record.
- {{TAGS}} tags.

## Dates

Each commit is dated at noon ({{TZ}}) on the day the change took effect. The other dates, enacted and published, are trailers.

When a law gives no date of its own, the default rule applies: {{RULE}} {{RULE_SOURCE}}

## How the history is built

`tools/build.py` turns the corpus into this history in one pass: one commit per law, on the day it took effect. The same corpus always gives the same commit hashes. `tools/check_repo.py` reads every version back from git and compares it with the corpus. `tools/on.py` shows the law as it stood on any date. The corpus format is described in `tools/SCHEMA.md`.

- Corpus: sha256 `{{CORPUS_SHA}}` ({{CORPUS_BYTES}} bytes).
- Builder blob hashes (`git hash-object`): `build.py` `{{BUILD_BLOB}}`, `check.py` `{{CHECK_BLOB}}`, `on.py` `{{ON_BLOB}}`.
- {{PYTHON}}; {{GIT}}.

## Checks

{{CHECK}}

{{REBUILD}}

## Decisions made by hand

{{DECISIONS}}

## What AI did and did not do

The source readers and builders were developed under Lexifina's direction with coding assistants, including Claude Code and Codex.

No model wrote, translated or corrected legal text. No model runs at build time. Every word of law in this repository comes from the official sources above.

The commit messages are written by `build.py` from the source data.

Model use at data-build time:
{{AI_USE}}
