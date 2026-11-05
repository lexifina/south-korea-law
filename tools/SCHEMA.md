# gitlaw_common: the corpus.json contract

Existing repositories receive this standard through `build.py --append --refresh-docs`:
one new documentation commit, with existing law commits and tag objects preserved.
New trailers appear only on future commits; a documentation rollout never re-emits them
on existing commits. A cold build requires an empty target. `build`, `prepare` and the
full-history writer refuse any target with existing Git refs, and the append writer
refuses replacement of an existing tag.

The goal is one builder for every country. Each country's law is recorded as one corpus, `corpus.json` (optionally split into `corpus.d/` parts), beside the country's static docs in `repo/` (`README.md` with the standard sections, `LICENSE`, and optionally `tools/<local-name>.py` as a thin wrapper around `tools/on.py`).

The shared builder turns `corpus.json` into the git repository. It produces:

- the commits, streamed through `git fast-import`
- the tags and the future branch
- `REPRODUCE.md` and `data/versions.json`
- `corpus.json` at the root: the repository's description of itself for global-law's readers (ISO path, language,
  history, record dates, citation rule; global-law MCP.md, "How a corpus describes itself"). An output, not this
  input: every field is derived from the input and the built history, and `country` may give `corpus`, `history` or
  `corpus_kind` itself. A `repo/corpus.json` written by hand is kept instead
- `tools/on.py`, `tools/check_repo.py` and `tools/build.py`
- the site data
- the checks

The commands are:

    python -X utf8 build.py <country folder> --repo <repository> --docs-date YYYY-MM-DD
    python -X utf8 check.py <repository> --corpus <country folder>/corpus.json
    python -X utf8 build.py <country folder> --repo <empty folder> --docs-date D --compare <repository>

`--docs-date` is required: use the day the data was retrieved, never the run day. The builder empties the target and keeps `origin`. It refuses to run if the target holds anything other than an earlier build.

The published root `corpus.json` is a descriptor, distinct from this input. Set `country.path` to the written-out
global-law path when its hierarchy cannot be derived unambiguously from the country code and place. It uses ASCII
place slugs, keeps disambiguating `-regency`, and drops `-city` below a state. `country.scope` is `all-acts` or
`selected-acts` (the default). `country.history` is `in-force`, `replayed` (with `verification`), `as-enacted`,
`current-only`, or `metadata-only`. The descriptor includes the act count, publisher, and future branch. Static
`repo/corpus.json` fields are retained and augmented. `data/repo.json` is removed in that same documentation commit;
readers still fall back to it for old commits.

`data/acts.json` records each act's static facts and status. Optional act fields are `id`, `eli`, `law_kind`,
`enacted`, `published`, `in_force`, `repealed`, `repealed_by`, `expired`, and `status`. Dates of an act's first named
law supply missing original dates; a baseline's record-start date is never invented as the act's commencement.
Statuses are `in force`, `repealed`, `expired`, `not yet in force`, and `as captured`.

`data/provisions.tsv` is sorted by provision path and `from`. Columns are `path`, `act`, `from`, `to`, `status`,
`kind`, `law`, `text_as_of`, `commit`, `text_source`, and `sha256`. An unchanged provision keeps its interval across
changes to other provisions. A replacement ends the prior interval the preceding day; a deletion is an explicit
repealed row. Same-day intermediate versions keep that same day as their last day. Correction ranges split the
applicable intervals and refer to the correction's actual commit. Commit IDs come from git after a fast-import
checkpoint; missing provenance is an error.

`data/laws.csv` separates canonical commit `kind` from instrument `law_kind`. `data/versions.json` adds inclusive
`to`, lifecycle `status`, and nullable `text_as_of` to every version. The regenerated commits ledger normalizes old
kind spellings without changing the commits that it describes.

## Images in law text (corpus standard section 5a)

New corpus builds require `source_images`, the count independently taken from the official source (including an
explicit zero). For an existing corpus, a missing field means not surveyed: appends, corrections and full rebuilds warn, and
image completeness stays unknown. Set `country.image_inventory_required: true` to require surveys on its new
writes too. A supplied inventory must balance referenced images and omission notices; a known shortfall fails
new writes. New law and correction commits carry `Corpus-standard: 1`, distinguishing them from pinned legacy
rows whose image defects warn. Missing surveys are never inferred to be zero or complete.

An empty rebuild target does not make an existing corpus new. `--compare` supplies the earlier repository as
publication context; a source folder's successful publisher receipt also supplies that context for a cold rebuild.
A scaffold, sign-off marker or `jurisdiction.json` saying `built` alone does not. Explicit image-inventory opt-in
still requires the survey in every case, and known inventory shortfalls still fail.

Kept images are listed in the version's `images`: `file` (a local path under the source folder), `sha256`, `ext`
(optional when the filename supplies it), `media_type`, `source_url`, and the source's `caption`. Their bytes must
come from the same official host as the text and match the hash. The builder reads local bytes only. Provision
text must already contain `![caption](assets/<sha256>.<ext>)` at the source position; the builder never inserts or
transcribes law text. Files over 25 MB must use an omission notice. Assets are marked binary and never re-encoded.

An omission is listed in `images_omitted` with `source_ref`, `description`, `reason` (`licence`, `not extractable`,
or `too large`), and optional `normative` (defaults to true). Its provision contains exactly
`[Image omitted: <source_ref>; <description>; reason: <reason>]`. A normative omission makes the act incomplete,
even though it satisfies the count check. Logos/decorations may explicitly set `normative: false`.

`data/assets.tsv` records path, act, sha256, byte count, media type, source URL, and the actual first commit. Act
metadata includes referenced and omitted counts, source count (null if unknown), and `images_complete`.
`complete` additionally requires an explicit source-verification assertion (`complete: true` on the act or version);
image accounting alone does not prove that all of an act's text was captured. Existing text
gets a missing image through a labelled correction with `Reason: image restored`, never a history rewrite.

## Jurisdiction hierarchy

The same documentation commit regenerates `jurisdiction.json` from the descriptor path, preserving unrelated
static fields. Levels are `country` (the EU: `supranational`) only at the top; `national`, `federal`, `bund`, `union`, or `uk` for a whole
jurisdiction; `state`, `province`, `region`, `canton`, `entity`, `territory`, `district`, `autonomous city`, or
`autonomous community` for first-level units; and `municipality` or `regency` below them. A place name is never a
level. Set `country.jurisdiction_level` to the source's type; without one, use `subdivision`, as global-law's
`tools/describe.py` does. The parity fixture retains that upstream file at commit `95b8164` unchanged.

Countries and their whole-jurisdiction folders use alpha-2 codes. First-level units require country-prefixed
ISO 3166-2 codes (`subdivision_code` may override `country.code`). Below that, the code is `parent_code` plus the
uppercased place slug; this intentionally identifies a non-ISO local code. `parent` is the written-out parent
path, not a guess from the repository name. ISO code membership must be supplied correctly by the source metadata;
the builder checks its structure and prefix, not an external ISO registry.

## corpus.json

### Older versions and the current tip

An older newly discovered act may be appended when its files are new. An older version of an existing file must
be supplied as a labelled correction. Ordinary appends that move a file's in-force date backwards are refused
before an import starts. The appender also checks the complete planned tip against the source versions in force
on `--docs-date`; it never writes an older text and leaves HEAD there. Corrections retain their range semantics
and restore current text before the append closes. This builder chooses refusal, rather than automatic re-apply
commits, for an invalid ordinary append.

Check 11 compares HEAD blobs directly with those source versions. It reports `tip_errors` for new law commits
and `tip_warnings` for already-pinned history; a documentation refresh does not relabel old law as new. The
incremental and full append gates both include the tip check.

All dates are ISO `YYYY-MM-DD`. All text is UTF-8 with `\n` line endings. Keys and values are plain JSON.

```json
{
  "country": {
    "code": "CL", "name": "Chile", "slug": "chile", "lang": "es",
    "tz": "America/Santiago",
    "future_branch": "futuro",
    "publisher": {"name": "Biblioteca del Congreso Nacional (LeyChile)", "email": "bcn@leychile.invalid"},
    "default_in_force_rule": {"text": "Código Civil art. 7: a law is binding from its publication in the Diario Oficial",
                              "source": "https://www.bcn.cl/leychile/navegar?idNorma=172986"},
    "licence_note": "exact attribution line the source requires"
  },
  "sources": [
    {"name": "LeyChile (BCN)", "url": "https://www.bcn.cl/leychile", "retrieved": "2026-10-28", 
     "licence": "…", "notes": "…"}
  ],
  "laws": {
    "ley-21200": {
      "label": "Ley 21.200",
      "title": "Modifica el capítulo XV de la Constitución Política de la República",
      "kind": "law",
      "enacted": "2019-12-23",
      "published": "2019-12-24",
      "url": "https://www.bcn.cl/leychile/navegar?idNorma=1140340",
      "temporary_until": null,
      "restores": null,
      "note": null
    }
  },
  "acts": [
    {
      "slug": "constitucion",
      "short": "CPR",
      "title": "Constitución Política de la República de Chile",
      "url": "https://www.bcn.cl/leychile/navegar?idNorma=242302",
      "first_law": "dl-1980-1150",
      "earlier_laws": [],
      "versions": [
        {
          "from": "1981-03-11",
          "source_url": "https://…version…",
          "sha256": "sha256 of the source bytes this version was parsed from",
          "units": {
            "art-019": {"label": "Art. 19", "kind": "art", "text": "one paragraph per line\nnext paragraph\n"},
            "disp-transitoria-01": {"label": "Disposición transitoria primera", "kind": "transitional", "text": "…"}
          },
          "credits": {"art-019": ["ley-21200"], "art-020": ["ley-21200", "ley-20050"]},
          "note": "optional: anything a reader of this version should know"
        }
      ]
    }
  ],
  "applies": [
    {"law": "ley-21200", "provision": "art-019",
     "groups": [{"conditions": [{"kind": "commenced_on_or_after", "date": "2020-01-01"}], "set_by": "Ley 21.200, art. 2 transitorio"}]}
  ],
  "decisions": ["Every decision made by hand, one sentence each, so it is printed in REPRODUCE.md."],
  "ai_use": ["What a model did at data-build time, with counts. Write 'none' if none."]
}
```

### The rules the builder enforces (do not work around them)

**Unit keys and text**
- A unit key becomes the file path `<act slug>/<key>.md`.
- Keys must be lowercase ASCII `[a-z0-9-]` and sort naturally. Zero-pad numbers: `art-005`, `art-005-bis`.
- A unit's text is one paragraph or item per line, so blame works line by line, and it ends with `\n`.
- The first line may be a heading (`# Art. 19`). Keep volatile metadata (version numbers, source URLs) out of the text.
- Normalise publisher typesetting once, when the corpus is written: NBSP becomes a space, collapse runs of spaces, use one form of quotes and dashes, and drop footnote markers.

**Versions and dates**
- `source_url` writes `Text-source:`. `consolidated`, if supplied, is an ISO date, never a URL.
- `text_as_of` is an explicit ISO capture day. `in_force_unknown: true` uses `retrieved` (or `from`) as that capture
  day on a baseline. Supply `in_force_basis` when `from` is a retrieval/capture day. Source commencement dates take
  precedence; explanatory prose is never parsed to invent a capture assertion.
- `retroactive` names the source provision authorizing a date before enactment; the trailer begins `yes;`.
  A day before 1500 requires `country.record_note` explaining the record.
- `versions` is ordered by `from`.
- `from` is the day the version took effect: the in-force date, not the publication date. When the source gives only the publication date, apply the country's `default_in_force_rule`, or the law's own vigencia clause, when the corpus is written. Write that down in `decisions`.
- Versions with `from` after the build's `--docs-date` go on `future_branch`.

**Credits**
- `credits` maps every unit that differs from the previous version (added, changed or removed) to the law(s) that changed it.
- The builder writes one commit per law per in-force day, holding exactly the units credited to that law.
- A changed unit with no credit is committed separately, by the `publisher`, labelled "unexplained".
- Never guess a credit. If two laws are credited to one unit on the same day, the unit goes in the later law's commit and both are named in its message.
- The first version is credited to `first_law` if it is the act as enacted. Otherwise (`first_law: null`) it is credited to the publisher as "oldest version available", naming `earlier_laws`.

**Laws**
- New commit `Kind` values are `law`, `baseline`, `correction`, `uncredited`, `printing`, `court`, `treaty`, and
  `documentation`. An unnamed first version is `baseline`; later unnamed text changes are `uncredited`.
- Input `kind` also accepts instrument names. These produce `Kind: law` with `Law-kind:` set from `law_kind`, or
  from the old instrument kind. The closed instrument list is `constitution`, `constitutional-amendment`, `act`,
  `code`, `decree`, `decree-law`, `regulation`, `ordinance`, `legal-notice`, `referendum`, `other`.
- Existing commits are read through the historical mapping; they are never rewritten. For existing repositories,
  use `build.py --append --refresh-docs` to add one documentation commit with no new law.
  `--compare <unchanged published clone>` checks every old commit and tag object, permitting only appended docs.
- A court ruling that strikes or conditions text is `kind: "court"`, for example Colombia C-xxx/yy (inexequible) and Brazil STF ADI. It is credited like a law, with the decision date as `enacted` and the date it took effect on the text as the version `from`.
- Temporary measures that lapse, such as Brazil's Medidas Provisórias and Argentina's DNU, set `temporary_until`. The lapse is a version credited to the law with `restores` set.
- The email is derived as `<law key>@<publisher-domain>.invalid`, so law keys must also be ASCII `[a-z0-9-]`.

**Applicability and data quality**
- A law may carry a `note`: one or two plain sentences that the commit message prints instead of the standard line for its kind. Use it for events that change no words, such as a referendum that was rejected or a ruling that only interprets. Credit such an event to the provisions it concerns in that version's `credits`, so it gets a commit with `Words-changed: no`; it needs a version (a `from` day) of its own only if the source has one.
- A version may omit `units`: it then reads as the version before it. Use this for an event that changed no words, with `credits` naming the provisions it concerns. Its commit names them in `Affecting:` and in the subject ("…, wording unchanged").
- **Large acts:** instead of `units`, a version may give `changes`: `{unit key: unit, or null to remove it}`, applied to the version before it. Use this for any act with many versions. It keeps part files small: GitHub rejects files over 100 MB.
- **Two versions on one day:** a version may share its `from` day with the one before it if it is marked `"same_day": true`. Example: a law that repeals provisions on the very day the act first applies. Its commits come after the earlier version's on that day. check.py compares the day's state with the last version of the day, and the day before with the last version before it.
- `applies` is only for typed applicability from transitional provisions.
- Leave `applies` empty rather than invent.
- No model output is treated as legal text.

## Splitting one country across several agents: corpus.d/

A country may also have `corpus.d/*.json` parts beside (or instead of) `corpus.json`. Each part holds `acts`, and optionally `laws`, `sources`, `applies`, `decisions` and `ai_use`. One part takes `country` if corpus.json is absent.

How parts are read:
- In file-name order (`20-codigo-civil.json`).
- Laws are merged by key. The same key in two files must have the same label, or the build stops.
- The build and check.py all read the merged corpus.

How to work with them:
- Each agent owns only its own part file and writes it atomically: write `.tmp`, then rename.
- Act slugs must not collide across parts, except for an explicit correction part below.

### Correction parts

A later part may declare `"corrects": "20-codigo-civil.json"`. Every entry in its `acts` array replaces the complete
act with the same slug from that earlier part, at its existing position in the merged corpus. Other acts remain
unchanged. The original part file is never edited. Include every version and all metadata needed for each replacement;
this is not a per-field or per-version merge. Other part fields keep the merge rules above.

The target must be an earlier loaded part's exact file name, including `.json`, not a path or `corpus.json`. Every
replacement slug must occur exactly once in the loaded corpus and still belong to that target. Missing targets,
slugs absent from the target, ambiguous duplicates and repeated corrections within one part are errors. To correct
an already corrected act again, name its most recent correction part. Split corrections of different original parts
into separate files. An undeclared duplicate remains an error; a correction cannot hide it.

A corpus withdrawal retains the act's historical slug and version dates, supplies `units: {}` and `credits: {}` for
the withdrawn versions, and explains the editorial withdrawal in its metadata. This withdraws the corpus's assertion
of that text; it does not assert legislative repeal. The loader preserves those entries and metadata as supplied.
This field only selects the merged input; it does not authorize rewriting published history or bypass publication
and append checks. With verified-only loading, both the target and its correction must pass the existing part filter.


## Per-act publisher (optional, 2026-10-29)
An act may carry `"publisher": {"name": ..., "email": "...@<domain>.invalid"}` when its text comes from a different source than the country's publisher (for example a ministry's revised edition, SILEP, Veritas). That act's "oldest version available" commit and its unexplained changes are then authored by it. A commit spanning acts with different publishers uses the country's. Corpora without the field build byte-identically to before.
# Documentation rollout for own builders

Own builders can pass their complete normalized corpus input to
`rollout.py <input-folder> --repo <published-clone> --docs-date YYYY-MM-DD --expected-head <published-SHA>`.
It verifies the input against published versions and current text, then appends at most one
documentation commit containing the standard descriptor, jurisdiction and data indexes.
It preserves native tools, source manifests, root documentation and act READMEs. It does
not emit law commits or tags. A changed published head, incomplete act inventory, unpublished
version, or changed law text stops the rollout before a commit is made.
The shared-builder rollout remains `build.py --append --refresh-docs`.

Documentation author and committer timestamps use the earlier of local noon on
`--docs-date` and the current time. An identical docs-only refresh is skipped.
Within a main-branch append, committer timestamps remain nondecreasing and may
share that ceiling instead of advancing past it. If an existing published head
already exceeds the ceiling, a changed docs update is refused until the date/time
permits it; that published commit is never rewritten.
