# How this repository was made (South Korea)

This file is written by the build on 2026-10-28, the day the source data was retrieved.

## Sources

| Source | Address | Retrieved | Licence |
| --- | --- | --- | --- |
| 법제처 국가법령정보센터 Open API (National Law Information Center, Ministry of Government Legislation) | <https://www.law.go.kr/DRF/> | 2026-10-28 | Statutes are not copyright works (저작권법 제7조); law.go.kr offers its data for reuse (공공누리 / KOGL) |

Every word of law in this repository comes from these sources. Lexifina reads them and records each act's dated versions, and the laws that made each change, in one corpus file. This repository is built from that file.

## What is in it

| Act | Title | Versions | Span |
| --- | --- | ---: | --- |
| `heonbeop` | 대한민국헌법 | 10 | 1948-07-17 to 1988-02-25 |
| `minbeop` | 민법 | 36 | 1960-01-01 to 2026-03-17 |
| `hyeongbeop` | 형법 | 34 | 1953-10-03 to 2026-10-02 |
| `gaeinjeongbo-bohobeop` | 개인정보 보호법 | 20 | 2011-09-30 to 2027-07-01 |

The build made 147 commits:

| Commits | Kind |
| ---: | --- |
| 4 | first version of an act |
| 99 | one law on its in-force day |
| 44 | changes no amendment note explains, credited to the publisher |

Other counts:
- 3 commits on the branch `future`: laws not yet in force on 2026-10-28.
- 18 commits dated 1 January 1970: in force before 1970, with the real day in their `In-force` trailer.
- 89 laws in the record.
- 189 tags.

## Dates

Each commit is dated at noon (Asia/Seoul) on the day the change took effect. The other dates, enacted and published, are trailers.

When a law gives no date of its own, the default rule applies: 대한민국헌법 제53조 제7항: 법률은 특별한 규정이 없는 한 공포한 날로부터 20일을 경과함으로써 효력을 발생한다 (a law takes effect 20 days after promulgation unless it provides otherwise). Every version here carries law.go.kr's own 시행일자 (in-force date), which already applies this rule or the law's own 부칙. https://www.law.go.kr/법령/대한민국헌법

## How the history is built

`tools/build.py` turns the corpus into this history in one pass: one commit per law, on the day it took effect. The same corpus always gives the same commit hashes. `tools/check_repo.py` reads every version back from git and compares it with the corpus. `tools/on.py` shows the law as it stood on any date. The corpus format is described in `tools/SCHEMA.md`.

- Corpus: sha256 `6a63a1b640bd6ff3005edcbae802d66d7fafdddd5b82eea56a7565d2e92ab49e` (2770374 bytes).
- Builder blob hashes (`git hash-object`): `build.py` `a4faa25af85facb64b956b372f6b528aafdd7ec1`, `check.py` `3e59cb6f05eccb94a9ec14431a7f6781221e83ef`, `on.py` `644a6c0857fbcc72562032b58d57aa113fee0641`.
- Python 3.12.10; git version 2.46.0.windows.1.

## Checks

Not yet run for this build.

No second build of this corpus has been compared yet.

## Decisions made by hand

- Every version is law.go.kr's own point-in-time text: one per 시행일자 (in-force date) in the eflaw search, dated by that day, not by promulgation (legalize-kr dates by promulgation).
- Where several laws take effect for one act on one day, the day's text is law.go.kr's version for the last of them by promulgation date and number.
- A changed provision is credited to a law of that day only on the source's own evidence: the law is the act's 제정 or 전부개정; or the law's 개정문 (its amending text, in law.go.kr's version record) names the provision; or law.go.kr's amendment note on the provision (<개정 ...>, [전문개정 ...], [본조신설 ...]) names the law's promulgation day; or the provision is that law's own 부칙. Everything else is committed by the publisher as unexplained, including the transcription differences between law.go.kr's historical versions (for example 표견대리/표현대리 in 민법 제129조). For 타법개정 the law is the other law whose 부칙 made the change; its title comes from the version's 개정문.
- A version promulgated before a law already in force (because it takes effect later) was composed by law.go.kr from the text as it stood at its promulgation, so it lacks that later law's changes. Only its own changes (its text against law.go.kr's version before it by promulgation) are applied to the text in force the day before; each such version says so in its note.
- Provisions whose text differs from the day before only in spacing (law.go.kr re-spaced old texts, 띄어쓰기) are committed by the publisher as unexplained, never credited to a law.
- Editorial notes law.go.kr adds to the consolidated text are removed: <개정 ...>, <신설 ...>, the dates after 삭제, and bracketed notes such as [전문개정 ...], [본조신설 ...], [제목개정 ...], [종전 ...] and Constitutional Court notes ([단순위헌 ...], [헌법불합치 ...]). 조문참고자료 is not part of the text.
- Constitutional Court (헌법재판소) decisions that void provisions without a statutory amendment are not commits: law.go.kr keeps the words and adds only a note.
- Headings (편/장/절/관) form one file per act, structure.md; each 부칙 is its own file, keyed by its law's promulgation date and number.
- Annexes (별표, 서식) are not included.
- 민법 art-0052-02 on 2002-01-14: law.go.kr's text already has wording from the law(s) promulgated 2001-12-29, which take effect for this act later; the provision is left out until that law takes effect.
- 민법 art-0060-02 on 2002-01-14: law.go.kr's text already has wording from the law(s) promulgated 2001-12-29, which take effect for this act later; the provision is left out until that law takes effect.
- 민법 제318조 on 2002-01-14: law.go.kr's text already has wording from the law(s) promulgated 2001-12-29, which take effect for this act later; the text in force the day before is kept.
- 민법 제354조 on 2002-01-14: law.go.kr's text already has wording from the law(s) promulgated 2001-12-29, which take effect for this act later; the text in force the day before is kept.
- 민법 제1037조 on 2002-01-14: law.go.kr's text already has wording from the law(s) promulgated 2001-12-29, which take effect for this act later; the text in force the day before is kept.
- 민법 제812조 on 2007-12-21: law.go.kr's text already has wording from the law(s) promulgated 2007-05-17, which take effect for this act later; the text in force the day before is kept.
- 민법 제814조 on 2007-12-21: law.go.kr's text already has wording from the law(s) promulgated 2007-05-17, which take effect for this act later; the text in force the day before is kept.
- 민법 제836조 on 2007-12-21: law.go.kr's text already has wording from the law(s) promulgated 2007-05-17, which take effect for this act later; the text in force the day before is kept.
- 민법 제859조 on 2007-12-21: law.go.kr's text already has wording from the law(s) promulgated 2007-05-17, which take effect for this act later; the text in force the day before is kept.
- 민법 제878조 on 2007-12-21: law.go.kr's text already has wording from the law(s) promulgated 2007-05-17, which take effect for this act later; the text in force the day before is kept.
- 형법 제151조 on 2005-07-29: law.go.kr's text already has wording from the law(s) promulgated 2005-03-31, which take effect for this act later; the text in force the day before is kept.
- 형법 제155조 on 2005-07-29: law.go.kr's text already has wording from the law(s) promulgated 2005-03-31, which take effect for this act later; the text in force the day before is kept.
- 형법 제328조 on 2005-07-29: law.go.kr's text already has wording from the law(s) promulgated 2005-03-31, which take effect for this act later; the text in force the day before is kept.
- law.go.kr lists law-10465 in force for gaeinjeongbo-bohobeop on 2012-03-30, but the text equals the day before's after removing editorial notes; no commit.

## What AI did and did not do

The scripts that read the sources and build this repository were written by Claude Code running Claude Opus 5.5 (`claude-opus-5-5`) under Lexifina's direction.

No model wrote, translated or corrected legal text. No model runs at build time. Every word of law in this repository comes from the official sources above.

The commit messages are written by `build.py` from the source data.

Model use at data-build time:
- Claude Code (claude-opus-5-5) wrote Lexifina's code. No model wrote, summarised or transcribed any legal text; every word comes from the law.go.kr API responses.
