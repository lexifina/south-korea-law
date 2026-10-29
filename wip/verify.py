"""Check the corpus against law.go.kr's current official text (target=law, 현행), provision by provision.

For each act, the text this corpus has in force on the retrieval day must equal law.go.kr's current version
(lawService.do?target=law&ID=<법령ID>), parsed the same way (editorial notes removed). Writes verification.json.

    python -X utf8 verify.py [--day 2026-10-28]
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch, parse  # noqa: E402


def current_url(law_id):
    return fetch.BASE + f'lawService.do?OC={fetch.OC}&target=law&ID={law_id}&type=XML'


def state_on(act, day):
    units = None
    for v in act['versions']:
        if v['from'] > day:
            break
        if 'units' in v:
            units = dict(v['units'])
        else:
            for k, u in (v.get('changes') or {}).items():
                if u is None:
                    units.pop(k, None)
                else:
                    units[k] = u
    return units


def main():
    day = sys.argv[sys.argv.index('--day') + 1] if '--day' in sys.argv else parse.RETRIEVED
    corpus = json.load(open(os.path.join(HERE, 'corpus.json'), encoding='utf-8'))
    cfg = {a['slug']: a for a in json.load(open(os.path.join(HERE, 'acts.json'), encoding='utf-8'))}
    out = {'day': day, 'acts': {}}
    for act in corpus['acts']:
        raw = fetch.get(current_url(cfg[act['slug']]['id']), check=fetch.ok_xml)
        meta, units, _, _, _ = parse.parse_version(raw)
        ours = state_on(act, day)
        diff = sorted(k for k in set(units) | set(ours) if (units.get(k) or {}).get('text') != (ours.get(k) or {}).get('text'))
        out['acts'][act['slug']] = {'official_in_force': meta['시행일자'], 'official_promulgation': f"{meta['공포일자']}/{meta['공포번호']}",
                                    'units': len(units), 'mismatches': diff, 'ok': not diff}
        print(act['slug'], len(units), 'units', 'OK' if not diff else f'{len(diff)} mismatches {diff[:8]}')
    with open(os.path.join(HERE, 'verification.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write('\n')


if __name__ == '__main__':
    main()
