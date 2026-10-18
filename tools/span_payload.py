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
print('SPAN %s  own %s -> %s   ext -> %s' % (sid, hms(sp['own_start']),
                                             hms(sp['own_end']), hms(sp['ext_end'])))
print('%d shots. own_end is at shot index %s.' % (
    len(sp['shots']),
    next((str(s['i']) for s in sp['shots'] if s['start'] >= sp['own_end'] - 1e-6),
         'end of list')))
print('')
print('idx  start            end              dur    frames')
for s in sp['shots']:
    print('%3d  %s  %s  %5.1f  %s' % (s['i'], hms(s['start']), hms(s['end']),
                                      s['dur'], ', '.join(fr.get(s['i'], ['-']))))
