# -*- coding: utf-8 -*-
"""In payload cho subagent cua mot span: danh sach shot + frame.

Dung:
    python tools/span_payload.py <project> <span>

Cac ham o day cung la nguon DUY NHAT cho payload cua duong API
(tools/tag_batch.py): mot span gui len API phai nhan dung chu ma mot subagent
nhan, neu khong thi hai duong tag la hai thi nghiem khac nhau va khong so sanh
duoc.
"""
import io, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def hms(s):
    return '%02d:%02d:%06.3f' % (int(s)//3600, (int(s) % 3600)//60, s % 60)


def load_cast(pdir):
    # Danh sach dien vien di KEM payload. Neu tagger khong co no thi `chars` se
    # toan mo ta ("the American student"), va moi speech claim sau nay thanh
    # khong kiem duoc vi binding_audit doi subject phai la mot nhan vat co ten.
    # Tren tokyodrift2006 dieu do lam hong 31/33 claim, va khong chua duoc neu
    # khong tag lai ca phim.
    try:
        _nj = json.load(io.open(os.path.join(str(pdir), 'names.json'),
                                encoding='utf-8-sig'))
        return [str(e.get('character', '')) for e in (_nj.get('names') or [])
                if e.get('character')]
    except Exception:
        return []


def cast_lines(cast):
    if cast:
        return ['CAST (use these exact spellings in `chars` when you can identify '
                'someone): ' + ', '.join(cast),
                'If you cannot tell who a person is, use a short stable description '
                'instead - never guess a name off the list.']
    return ['!! NO names.json - `chars` will hold descriptions only, and every '
            'later speech claim will be unauditable. Build names.json from the '
            'film\'s Wikipedia cast list BEFORE tagging.']


def frames_by_shot(sp):
    fr = {}
    for f in sp.get('frames', []):
        fr.setdefault(f['shot_i'], []).append(f['file'])
    return fr


def header_line(sp):
    return 'SPAN %s  own %s -> %s   ext -> %s' % (
        sp['id'], hms(sp['own_start']), hms(sp['own_end']), hms(sp['ext_end']))


def shot_lines(sp):
    fr = frames_by_shot(sp)
    out = ['%d shots. own_end is at shot index %s.' % (
        len(sp['shots']),
        next((str(s['i']) for s in sp['shots']
              if s['start'] >= sp['own_end'] - 1e-6), 'end of list')),
        '',
        'idx  start            end              dur    frames']
    for s in sp['shots']:
        out.append('%3d  %s  %s  %5.1f  %s' % (
            s['i'], hms(s['start']), hms(s['end']), s['dur'],
            ', '.join(fr.get(s['i'], ['-']))))
    return out


def payload_lines(sp, cast):
    return [header_line(sp)] + cast_lines(cast) + shot_lines(sp)


def main():
    proj, sid = sys.argv[1], sys.argv[2]
    # config.project_dir thay cho duong dan cung 'D:\Recap Vid\projects\...':
    # tren may chu hai cai la mot, va duong API + test can chay ca o noi khac.
    d = config.project_dir(proj)
    meta = json.load(io.open(d / 'spans.json', encoding='utf-8'))
    sp = [s for s in meta['spans'] if s['id'] == sid][0]
    print('\n'.join(payload_lines(sp, load_cast(d))))


if __name__ == '__main__':
    main()
