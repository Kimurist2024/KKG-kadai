"""Run from project root: backend/.venv/bin/python scripts/validation/run_validation.py.

External annotations are hand-traced pixel coordinates, never fitted to area labels.
Requires the rendered source PNGs retained in sources/; uses the actual upload API.
"""
import base64
import copy
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app

OUT = ROOT / 'docs' / 'validation'
CLIENT = TestClient(app)
UR = 'https://www.ur-net.go.jp/rd_portal/UR-BIM/jni4dd0000001wmv-att/03_kenchikuzu_S2_ver1.1.pdf'
MINI = 'https://b9f0a121-a2f4-4be4-a8a0-ebf384c417bf.filesusr.com/ugd/0dcb7e_6ad37e587a4b47f7baebde4c7abafb32.pdf'

def rect(x0, y0, x1, y1):
    return [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]

def contour(i, name, points, label=1):
    return dict(id=i, room_name=name, label_id=label, isLine=label!=1,
                color={1:'#3b82f6',2:'#dc2626',3:'#16a34a'}[label],
                vertices=[dict(x=x,y=y) for x,y in points])

def mask(contours, image=None, size=(1786,1263)):
    d=dict(contours=contours,image_width=size[0],image_height=size[1])
    if image:
        d['image_data']=dict(mime_type='image/png',base64=base64.b64encode((OUT/'sources'/image).read_bytes()).decode())
    return d

def upload(data, mpp, **kw):
    settings=dict(scale_px=1,scale_m=mpp,ceiling_height_m=2.4,door_height_m=2.0,tolerance_px=10)
    settings.update(kw)
    r=CLIENT.post('/api/analyze', params=settings, files={'file':('validation.json',json.dumps(data).encode(),'application/json')})
    assert r.status_code==200, r.text
    return r.json()

def save(name, data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

# UR page 3, rasterized at 1.5 px/PDF point. X0 -> X7 is 44,650 mm.
# Trace wall centre lines of dwelling units, including the L-shaped first unit.
ur_points=[[[628,530],[682,530],[682,437],[757,437],[757,624],[628,624]]]
ur_points += [rect(a,437,b,624) for a,b in [(757,845),(845,914),(914,1033),(1033,1101),(1101,1170),(1170,1281),(1281,1442)]]
ur_names=['1LDK-42-EV','1DK-36','1K-28 A','2DK-48','1K-28 B','1K-28 C','1LDK-45','3LDK-66']
ur_refs=[42.59,36.60,28.66,48.95,28.66,28.66,45.86,66.50]
ur_perimeters=[2*(w+8.8) for w in [6.05,4.15,3.25,5.55,3.25,3.25,5.2,7.55]]
ur_mask=mask([contour(i+1,n,p) for i,(n,p) in enumerate(zip(ur_names,ur_points))], 'ur_page3.png')
ur_scale=44.65/(1442-493)

# Mini Homes page 5, rasterized at 2 px/PDF point. Calibrate against
# the external 40 ft length, y=285..1427; do not calibrate to room dimensions.
mini_points=[rect(360,300,666,530),rect(295,1018,535,1144),rect(295,1154,666,1411)]
mini_names=['Bedroom 2 (closet excluded)','Bath','Master (closets included)']
mini_dims=[(8,11),(4,8),(9,13)]
mini_refs=[a*b*0.3048**2 for a,b in mini_dims]
mini_perimeters=[2*(a+b)*0.3048 for a,b in mini_dims]
mini_mask=mask([contour(i+1,n,p) for i,(n,p) in enumerate(zip(mini_names,mini_points))], 'mini_homes5.png',(1224,1584))
mini_scale=40*0.3048/(1427-285)

rows=[]
for name,data,mpp,refs,url,page in [('ur',ur_mask,ur_scale,ur_refs,UR,3),('mini',mini_mask,mini_scale,mini_refs,MINI,5)]:
    save(name+'_mask.json',data)
    result=upload(data,mpp)
    save(name+'_response.json',result)
    perimeters=ur_perimeters if name=='ur' else mini_perimeters
    for room,ref,pref in zip(result['rooms'],refs,perimeters):
        value=room['floor_area_m2']
        rows.append(dict(dataset=name,room=room['name'],reference_m2=ref,actual_m2=value,error_m2=value-ref,error_pct=100*(value/ref-1),perimeter_m=room['perimeter_m'],reference_perimeter_m=pref,perimeter_error_pct=100*(room['perimeter_m']/pref-1),source_url=url,page=page))
    save(name+'_settings.json',dict(scale_px=1,scale_m=mpp,tolerance_px=10,ceiling_height_m=2.4,door_height_m=2))

with (OUT/'area_results.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)

# Conditional wall-area check on the traced external Bedroom 2. Door endpoints
# are read from the drawing, heights are assumptions, not ground truth.
p=mini_points[0]; doorway=[[580,530],[653,530]]
walls=[contour(10+i,None,[a,b],2) for i,(a,b) in enumerate(zip(p,p[1:]+p[:1]))]
door=contour(20,None,doorway,3)
bedroom=mask([contour(1,'Bedroom 2',p)]+walls+[door], 'mini_homes5.png',(1224,1584))
save('bedroom_wall_mask.json',bedroom)
width=(666-360)*mini_scale;depth=(530-300)*mini_scale;dw=73*mini_scale
ref=dict(floor_area_m2=width*depth,perimeter_m=2*(width+depth),wall_area_m2=2*(width+depth)*2.4-dw*2)
baseline=upload(bedroom,mini_scale)
save('bedroom_wall_response.json',baseline)
checks={key:dict(expected=v,actual=baseline['rooms'][0][key],absolute_error=abs(v-baseline['rooms'][0][key])) for key,v in ref.items()}
assert all(c['absolute_error']<1e-9 for c in checks.values())

broken=copy.deepcopy(bedroom)
broken['contours']=[c for c in broken['contours'] if c['id']!=12]
broken['contours'] += [contour(30,None,[[666,530],[653,530]],2),contour(31,None,[[580,530],[360,530]],2)]
save('bedroom_door_gap_mask.json',broken)
gap=upload(broken,mini_scale)
save('bedroom_door_gap_response.json',gap)
gap_wall=gap['rooms'][0]['wall_area_m2']

# Sensitivity experiments: derived/synthetic variants, not extra independent plans.
scale_tests=[]
for e in [-.05,-.01,0,.01,.05]:
    r=upload(bedroom,mini_scale*(1+e))['rooms'][0]
    scale_tests.append(dict(scale_error_pct=e*100,floor_error_pct=100*(r['floor_area_m2']/ref['floor_area_m2']-1),wall_error_pct=100*(r['wall_area_m2']/ref['wall_area_m2']-1)))
offset_tests=[]
for offset in [0,2,5,9,10,11,20]:
    d=copy.deepcopy(bedroom)
    for c in d['contours']:
        if c['isLine']:
            for v in c['vertices']:v['x']+=offset;v['y']+=offset
    r=upload(d,mini_scale)['rooms'][0]
    offset_tests.append(dict(offset_x_y_px=offset,wall_area_m2=r['wall_area_m2'],wall_error_pct=100*(r['wall_area_m2']/ref['wall_area_m2']-1)))

summary=dict(area_rows=rows,arithmetic_checks=checks,
    datasets={n:dict(n=sum(r['dataset']==n for r in rows),mape_pct=statistics.mean(abs(r['error_pct']) for r in rows if r['dataset']==n),max_absolute_pct=max(abs(r['error_pct']) for r in rows if r['dataset']==n)) for n in ['ur','mini']},
    wall_gap=dict(reference_m2=ref['wall_area_m2'],actual_m2=gap_wall,error_pct=100*(gap_wall/ref['wall_area_m2']-1),warnings=gap['warnings']),
    scale_sensitivity=scale_tests,offset_sensitivity=offset_tests)
save('results.json',summary)
print(json.dumps({k:v for k,v in summary.items() if k!='area_rows'},ensure_ascii=False,indent=2))
