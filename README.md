# South Korea: law history in git

The law of South Korea (KR) as a git history: one file per provision, one commit per law on the day it took effect, and the law that made the change as the commit author. It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `kr/`.

**First build.** Language: Korean (the official language).

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
| `heonbeop/` | 대한민국헌법 (Constitution) | 10 | From the first Constitution (17 July 1948) through the nine revisions, to the text in force since 25 February 1988 |
| `minbeop/` | 민법 (Civil Act) | 36 | From 1 January 1960 to the text in force on 17 March 2026 |
| `hyeongbeop/` | 형법 (Criminal Act) | 34 | From 3 October 1953 to the text in force on 2 October 2026 |
| `gaeinjeongbo-bohobeop/` | 개인정보 보호법 (Personal Information Protection Act) | 20 | From 30 September 2011 to today; versions already promulgated but not yet in force go on branch `future` |

Each version is law.go.kr's own version in force from a 시행일자 (in-force date), credited to the law law.go.kr names as its amendment. Where law.go.kr changed only spacing (띄어쓰기) in its own database, or composed a text before laws promulgated later but in force earlier, the version note says so and no law is credited for the spacing. Editorial notes are not part of the text.

**How it is checked.** The text in force on 28 October 2026 of all four acts was compared with law.go.kr's current page for that version, provision by provision (30 October 2026): no provision differs. The versions were fetched from the Open API of law.go.kr using its public demonstration id `OC=test`, which law.go.kr no longer accepts.

**Source:** [국가법령정보센터 (National Law Information Center), 법제처](https://www.law.go.kr), official, retrieved 28 October 2026. See `LICENSE` and `REPRODUCE.md`.

Dates are the day the change took effect. This repository is not legal advice; for anything that matters, read the original.
