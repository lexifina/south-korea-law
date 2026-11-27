# South Korea: law history in git

[한국어](README.md) · **English**

<picture>
<source media="(prefers-color-scheme: dark)" srcset="data/effort-dark.svg">
<img alt="South Korean law in this repository: what it holds, changes by the year they took effect, completeness against the official sources, and the correctness of what is held" src="data/effort-light.svg" width="880">
</picture>

The law of South Korea as a git history: one file per article, one commit per version on the day it took effect, and the law that made each change as the commit's author. `git blame` names the law behind every paragraph; `git log` lists every change to an article; picking a date gives the text in force that day.

Part of [lexifina/global-law](https://github.com/lexifina/global-law), one git history for every country's law: this is South Korea's national law, which global-law reads at `south-korea/national/acts/`.

**What is in it now:** the Constitution and, act by act, every Act (법률), presidential decree (대통령령), Prime Minister's and ministerial ordinance (총리령·부령) and rule of the constitutional bodies in force on law.go.kr (5,634 on 27 November 2026), each with every dated version law.go.kr lists from 17 July 1948. The build takes the core codes first (Civil Procedure, Criminal Procedure, Commercial, Labour Standards, General Act on Public Administration ...), then the other Acts, decrees and ordinances; on 2026-11-27 it held 19 acts with their full history (488 versions), and the further acts of the earlier build each in one current text until the build reaches them. [`STRUCTURE.md`](STRUCTURE.md) gives the layout, and each act's folder has a `README.md` listing its versions.

Folders are by kind and year of first promulgation, in Korean: `헌법/` (Constitution), `법률/<연도>/<법령명>/` (Acts; `법률/1958/민법/` is the Civil Act), `대통령령/<연도>/<법령명>/` (presidential decrees, 시행령), `부령/<연도>/<법령명>/` (총리령 and 부령, 시행규칙), and the rules of the courts and other constitutional bodies under their own kind (`대법원규칙/` ...). Each article is one file (`art-0001.md` is 제1조, `art-0007-02.md` 제7조의2), each paragraph one line; each 부칙 (supplementary provisions) is its own file and the headings are in `structure.md`. An act of the earlier build not yet rebuilt is one file, `text.md`.

The text is in Korean, as law.go.kr publishes it, without its editorial notes (`<개정 ...>`, `[전문개정 ...]`). An English translation is not part of this record.

## Questions as git commands

| Question | Command |
| --- | --- |
| Every change to Article 1 of the Constitution | `git log -p --word-diff -- 헌법/art-0001.md` |
| Which law wrote each line of Article 1? | `git blame 헌법/art-0001.md` |
| Every version of the Constitution, with the day each took effect | `git log --grep="^In-force:" --format="%h %(trailers:key=In-force,valueonly,separator=) %an" -- 헌법` |
| Article 1 as in force on 1 January 1960 | `python tools/on.py 1960-01-01 헌법 art-0001` |

**Outside git**, we also host this record publicly, for free:

- **[Ask Claude about South Korean law](https://global-law.lexifina.com/v1/try_claude?country=south-korea)**: opens Claude with a first question ready.
- **[Ask ChatGPT](https://global-law.lexifina.com/v1/try_chatgpt?country=south-korea)**: the same question in ChatGPT.
- **[Search South Korean law on our site](https://lexifina.com/law?country=south-korea&q=%EC%9C%A0%EA%B8%89%ED%9C%B4%EA%B0%80)**: a search for "유급휴가" (paid leave), with each provision's text and its versions, no account needed.
- **[Developer REST API](https://global-law.lexifina.com/v1/search_law?query=%EC%9C%A0%EA%B8%89%ED%9C%B4%EA%B0%80&jurisdiction=south-korea)**: the same search as JSON, with no key. See the [documentation here](https://lexifina.com/api/global-law).

Both assistants read the record through the free Global law connector (MCP, `https://global-law.lexifina.com/mcp`); the first time, the chat gives you the link that adds it. Ask in Korean or in English.

**Host it yourself easily.** All it takes is git and Python, and the tools run on your machine:

```sh
git clone --depth 1 https://github.com/lexifina/global-law && cd global-law
python3 tools/countries.py add south-korea/national/acts
python3 tools/law.py show 2026-01-01 south-korea/national/acts/헌법/art-0001.md
```

Opened in Claude Code, Cursor, VS Code or Codex, the clone also starts a local MCP server with the same tools ([MCP.md](https://github.com/lexifina/global-law/blob/main/MCP.md)).

## Dates

Each commit is dated at noon, Asia/Seoul, on the day the version took effect, and carries it in its `In-force:` trailer:

- for every act, law.go.kr's own 시행일자 (in-force day) for each version, which already applies the law's 부칙 or the Constitution's default rule (a law takes effect 20 days after promulgation unless it provides otherwise, 헌법 제53조 제7항); where several laws take effect for one act on one day, the text is law.go.kr's version for the last of them;
- each version's 시행일 is the one law.go.kr's 연혁 (history) list gives it, quoted in the commit's `In-force-basis:` trailer, with its promulgation day and number in `Published:` and `Law:`; versions not yet in force are held until their day;
- git cannot store dates before 1970, so the earlier commits are dated 1970-01-01, with the real day in `In-force:`. Ask for a date with `tools/on.py`, not `git log --before`.

Each change is credited to the law that made it, as law.go.kr names it (`법률 제19234호`, `헌법 제10호`), at an address that cannot exist (`law-19234@law.go.kr.invalid`), and only where law.go.kr's record shows that law made the change. Changes the record does not explain, including law.go.kr's re-spacing of old texts (띄어쓰기), are credited to the publisher, 법제처 국가법령정보센터 (43 of the 144 commits on the four acts), as is each of the 500 single texts; the committer is always Lexifina.

## How it is checked

- The text in force on 28 October 2026 of the four acts with history was compared with law.go.kr's page for that version, provision by provision, on 30 October 2026: no provision differs.
- `tools/check_repo.py` reads every version back from git on the day it took effect, and on the day before, and compares it with the corpus the history was built from (its sha256 is in `data/corpus.sha256`); it also checks that every commit's trailers parse, that `main` has no merge commits and that no date goes backwards. [`REPRODUCE.md`](REPRODUCE.md) says it has not yet been run on the current build.
- [`data/versions.json`](data/versions.json) gives each version's source address and sha256.
- History is append-only: the 500 further acts were added on top of the earlier history; on 27 November 2026 the flat folders were moved to the Korean layout in one pure-rename commit, and each act's full history is added on top, its oldest version replacing the single text; no published commit is rewritten.
- [vulnerabilities/](vulnerabilities/README.en.md): possible drafting mistakes in this law, found by global-law's detectors and checked by hand. Not run yet.

## What it does not show

- **Acts the build has not reached yet.** Until then an act of the earlier build holds one current text, and the other acts in force are missing.
- **Repealed acts** (not in force on law.go.kr), local ordinances (조례), administrative rules (행정규칙) and case law are not here.
- **Two versions of the Personal Information Protection Act not yet in force** (from 9 March and 1 July 2027): `REPRODUCE.md` and `data/versions.json` count them, but they are not in the history.
- **Annexes and forms (별표, 서식)**, and images in the source texts, are not in the files.
- **Constitutional Court decisions** voiding a provision: law.go.kr keeps the words and only adds a note, which is removed, so they are not commits.

## Sources

| Source | Kind | Past versions | Notes |
| --- | --- | --- | --- |
| [국가법령정보센터](https://www.law.go.kr) (National Law Information Center, 법제처 Ministry of Government Legislation) | Official law database: its Open API (each version by in-force day, for the first four acts) and its public law pages: the list of laws in force (lsSc.do), each act's 연혁 list (lsHstListR.do) and each dated text (lsInfoR.do) | yes: every version law.go.kr lists | Editorial notes and amendment tags removed; for the first four acts spacing and quotation marks normalised, for the others the text as printed |

## Licence

See [`LICENSE`](LICENSE). Statutes are not protected by copyright in Korea (저작권법 제7조); the text is from 법제처 국가법령정보센터, and the Government of Korea does not endorse this repository. Lexifina's history, commit messages and tools are CC0 1.0.

No model wrote, translated or corrected legal text, and no model runs when the history is built; the readers and builders were written with coding assistants (Claude Code and Codex) under Lexifina's direction (see [`REPRODUCE.md`](REPRODUCE.md)).

## Visualisations

- [visualisations/](visualisations/README.en.md): charts drawn from this repository. Not drawn yet.

## More

From [lexifina/global-law](https://github.com/lexifina/global-law):

- [FEATURES.md](https://github.com/lexifina/global-law/blob/main/FEATURES.md): every feature, and what every corpus must support (`git blame`, `law.py`, the MCP tools)
- [FAQ.md](https://github.com/lexifina/global-law/blob/main/FAQ.md): questions and answers · [CONTRIBUTING.md](https://github.com/lexifina/global-law/blob/main/CONTRIBUTING.md): proposing changes · [MCP.md](https://github.com/lexifina/global-law/blob/main/MCP.md): the MCP server · [REPRODUCE.md](https://github.com/lexifina/global-law/blob/main/REPRODUCE.md): how it was built · [CHANGELOG.md](https://github.com/lexifina/global-law/blob/main/CHANGELOG.md)
- [FRESHNESS.md](https://github.com/lexifina/global-law/blob/main/FRESHNESS.md): how current each corpus is · [Monitoring](https://github.com/lexifina/global-law/tree/main/monitoring): whether updates are running · [WATCHING.md](https://github.com/lexifina/global-law/blob/main/WATCHING.md): how each official source is watched for changes
- [performance/](https://github.com/lexifina/global-law/tree/main/performance): how fast the tools are, measured
- [visualisations/](https://github.com/lexifina/global-law/tree/main/visualisations): charts and bridges across the world's law
- [Vulnerabilities](https://github.com/lexifina/global-law/tree/main/vulnerabilities): mistakes in legislation as published
