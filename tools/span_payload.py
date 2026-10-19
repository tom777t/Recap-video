# -*- coding: utf-8 -*-
"""In payload cho subagent cua mot span: danh sach shot + frame."""
import json, io, sys

proj, sid = sys.argv[1], sys.argv[2]
d = rf'D:\Recap Vid\projects\{proj}'
meta = json.load(io.open(d + r'\spans.json', encoding='utf-8'))
sp = [s for s in meta['spans'] if s['id'] == sid][0]


def hms(s):
    return '%02d:%02d:%06.3f' % (int(s)//3600, (int(s) % 3600)//60, s % 60)


fr = {}
for f in sp.get('frames', []):
    fr.setdefault(f['shot_i'], []).append(f['file'])
# Danh sach dien vien di KEM payload. Neu tagger khong co no thi `chars` se
# toan mo ta ("the American student"), va moi speech claim sau nay thanh
# khong kiem duoc vi binding_audit doi subject phai la mot nhan vat co ten.
# Tren tokyodrift2006 dieu do lam hong 31/33 claim, va khong chua duoc neu
# khong tag lai ca phim.
cast = []
try:
    _nj = json.load(io.open(d + r'\names.json', encoding='utf-8-sig'))
    cast = [str(e.get('character', '')) for e in (_nj.get('names') or [])
            if e.get('character')]
except Exception:
    pass

print('SPAN %s  own %s -> %s   ext -> %s' % (sid, hms(sp['own_start']),
                                             hms(sp['own_end']), hms(sp['ext_end'])))
if cast:
    print('CAST (use these exact spellings in `chars` when you can identify '
          'someone): ' + ', '.join(cast))
    print('If you cannot tell who a person is, use a short stable description '
          'instead - never guess a name off the list.')
else:
    print('!! NO names.json - `chars` will hold descriptions only, and every '
          'later speech claim will be unauditable. Build names.json from the '
          'film\'s Wikipedia cast list BEFORE tagging.')
print('%d shots. own_end is at shot index %s.' % (
    len(sp['shots']),
    next((str(s['i']) for s in sp['shots'] if s['start'] >= sp['own_end'] - 1e-6),
         'end of list')))
print('')
print('idx  start            end              dur    frames')
for s in sp['shots']:
    print('%3d  %s  %s  %5.1f  %s' % (s['i'], hms(s['start']), hms(s['end']),
                                      s['dur'], ', '.join(fr.get(s['i'], ['-']))))
