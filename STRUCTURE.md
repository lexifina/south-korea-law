# 구조 (Structure)

이 저장소는 국가법령정보센터(www.law.go.kr)의 현행 법령과 그 연혁(시행일별 판)을 담습니다.
This repository holds every law in force on the National Law Information Center (www.law.go.kr) with its dated
versions (시행일).

## 폴더 (Folders)

| 폴더 | 내용 |
| --- | --- |
| `헌법/` | 대한민국헌법 (Constitution) |
| `법률/<연도>/<법령명>/` | 법률 (Acts); 연도 = 제정 공포연도 (year the act was first promulgated) |
| `대통령령/<연도>/<법령명>/` | 대통령령 (Presidential decrees: 시행령 etc.) |
| `부령/<연도>/<법령명>/` | 총리령 and every 부령 (Prime Minister's and ministerial ordinances: 시행규칙 etc.) |
| `대법원규칙/`, `국회규칙/`, `헌법재판소규칙/`, `중앙선거관리위원회규칙/`, `감사원규칙/` ... `/<연도>/<법령명>/` | Rules of the constitutional bodies, under the kind's own name |

The folder name is the act's current official name (법령명). An act keeps its folder when it is renamed; the name it
had in each version is in the `Act:` trailer of that version's commit.

## 파일 (Files, in each act folder)

| 파일 | 내용 |
| --- | --- |
| `art-NNNN.md`, `art-NNNN-MM.md` | 제N조, 제N조의M: one file per article (조), its 항·호·목 on separate lines |
| `buchik-YYYYMMDD-NNNNN.md` | 부칙 of the instrument promulgated on that day with that number |
| `structure.md` | 편·장·절·관 headings in order |
| `README.md` | the act's versions: 시행일, 공포 (instrument), 제정·개정구분, link to the original |
| `text.md` | only for an act whose text has no numbered articles |

Publisher notes in brackets after an article ([전문개정 ...], <개정 ...>) are left out of article files; they are kept
in 부칙 files as printed.

## 커밋 (Commits)

One commit per entry of the act's 연혁 (history) list on law.go.kr that is in force by the day of the build, dated
12:00 KST on its 시행일. Git cannot store dates before 1970: those commits are dated 1970-01-01 and carry the real day
at the start of the subject and in the `In-force` trailer. Author = the instrument (e.g. `법률 제21454호`).
Trailers: `Law`, `Kind`, `Change` (제정/일부개정/전부개정/타법개정 ...), `Published` (공포일), `In-force` (시행일),
`In-force-basis` (the law.go.kr 연혁 entry), `Source`, `Act`, `Act-id` (law.go.kr 법령ID).

Versions not yet in force (시행 예정) are held until their day.
