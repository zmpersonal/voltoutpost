#!/usr/bin/env python3
import os, sys, csv, json, math, time, re, argparse
from pathlib import Path
from statistics import mean
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
parser=argparse.ArgumentParser(); parser.add_argument('--build-only',action='store_true'); args=parser.parse_args()

def get_json(url, timeout=45):
    req=Request(url,headers={'User-Agent':'VoltOutpost/1.0 (+https://voltoutpost.com/sources/)'})
    with urlopen(req,timeout=timeout) as r: return json.load(r)

def clamp(x,a=0,b=100): return max(a,min(b,x))
def score(annual, monthly, rate, disasters):
    perkw=annual/10
    solar=clamp((perkw-1000)/8)
    avg=mean(monthly) if monthly else 1
    ratio=min(monthly)/avg if monthly and avg else .4
    seasonal=clamp((ratio-.25)/.0055)
    hazard=clamp(100-disasters*4.2)
    afford=clamp((35-rate)/.23)
    return round(.35*solar+.20*seasonal+.25*hazard+.20*afford), round(solar),round(seasonal),round(hazard),round(afford),round(ratio,3)

def norm_area(s):
    s=(s or '').lower()
    for x in ['(county)',' county',' parish','(parish)',' municipality','(municipality)',' city','(city)']:
        s=s.replace(x,'')
    return re.sub(r'[^a-z0-9]','',s)

def load_existing():
    with open(DATA/'resilience-index.json') as f:return json.load(f)

def eia_rates():
    key=os.getenv('EIA_API_KEY','').strip()
    if not key:return {}
    params=[('api_key',key),('data[]','price'),('facets[sectorid][]','RES'),('frequency','monthly'),('sort[0][column]','period'),('sort[0][direction]','desc'),('length','500')]
    d=get_json('https://api.eia.gov/v2/electricity/retail-sales/data/?'+urlencode(params))
    out={}
    for x in d.get('response',{}).get('data',[]):
        st=x.get('stateid'); p=x.get('price')
        if st and len(st)==2 and st not in out and p not in (None,''):
            out[st]=(float(p),x.get('period'))
    return out

def pvwatts(lat,lon):
    key=os.getenv('NLR_API_KEY','').strip()
    if not key: raise RuntimeError('NLR_API_KEY not configured; retaining previous solar data')
    tilt=min(40,max(10,abs(float(lat))))
    params={'api_key':key,'system_capacity':10,'module_type':0,'losses':14,'array_type':1,'tilt':round(tilt,1),'azimuth':180,'lat':lat,'lon':lon,'dataset':'nsrdb','radius':0,'timeframe':'monthly'}
    d=get_json('https://developer.nlr.gov/api/pvwatts/v8.json?'+urlencode(params))
    if d.get('errors'): raise RuntimeError('; '.join(d['errors']))
    o=d['outputs']; return float(o['ac_annual']),[float(x) for x in o['ac_monthly']],d.get('station_info',{}).get('weather_data_source','NLR PVWatts v8')

def fema_map():
    # Fetch declarations since 2006. OpenFEMA is unauthenticated. If unavailable, caller keeps previous values.
    start="2006-01-01T00:00:00.000Z"
    select='disasterNumber,state,designatedArea,declarationDate'
    skip=0; top=1000; out={}
    while True:
        url='https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?'+urlencode({'$filter':f"declarationDate ge '{start}'",'$select':select,'$top':top,'$skip':skip})
        d=get_json(url,timeout=60)
        items=d.get('DisasterDeclarationsSummaries',[])
        for x in items:
            st=x.get('state'); area=norm_area(x.get('designatedArea')); num=x.get('disasterNumber')
            if st and area and num is not None: out.setdefault((st,area),set()).add(str(num))
        if len(items)<top or skip>50000: break
        skip+=top; time.sleep(.12)
    return out

def rebuild_static(rows):
    import importlib.util
    spec=importlib.util.spec_from_file_location("render_site", ROOT/"scripts"/"render_site.py")
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    payload={"generated_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"method_version":"1.0","cities":rows}
    mod.render(payload)

def main():
    d=load_existing(); rows=d['cities']
    if not args.build_only:
        try: er=eia_rates(); print('EIA states',len(er))
        except Exception as e: print('EIA refresh failed:',e); er={}
        try: fm=fema_map(); print('FEMA county-area keys',len(fm))
        except Exception as e: print('FEMA refresh failed:',e); fm={}
        for i,r in enumerate(rows):
            if r['state_abbr'] in er:
                r['electricity_rate_cents_kwh']=round(er[r['state_abbr']][0],2); r['electricity_source']='EIA '+str(er[r['state_abbr']][1])
            if fm:
                key=(r['state_abbr'],norm_area(r['county']))
                if key in fm:
                    r['fema_disasters_20yr']=len(fm[key]); r['hazard_source']='OpenFEMA declarations since 2006'
            try:
                annual,monthly,src=pvwatts(r['lat'],r['lon'])
                r['annual_solar_kwh_10kw']=round(annual); r['monthly_solar_kwh_10kw']=[round(x) for x in monthly]; r['solar_source']=src
            except Exception as e:
                print('PVWatts failed',r['city'],e)
            s,a,b,c,e,ratio=score(r['annual_solar_kwh_10kw'],r['monthly_solar_kwh_10kw'],r['electricity_rate_cents_kwh'],r['fema_disasters_20yr'])
            r.update(score=s,solar_score=a,seasonal_score=b,hazard_resilience_score=c,affordability_score=e,winter_to_average_ratio=ratio,data_status='refreshed from available public sources')
            time.sleep(.12)
        rows.sort(key=lambda x:x['score'],reverse=True)
        for i,r in enumerate(rows,1):r['rank']=i
        out={'generated_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'method_version':'1.0','cities':rows}
        (DATA/'resilience-index.json').write_text(json.dumps(out,indent=2))
        fields=['rank','city','state','state_abbr','county','score','solar_score','seasonal_score','hazard_resilience_score','affordability_score','annual_solar_kwh_10kw','winter_to_average_ratio','electricity_rate_cents_kwh','fema_disasters_20yr','data_status']
        with open(DATA/'resilience-index.csv','w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();
            for r in rows:w.writerow({k:r[k] for k in fields})
    rebuild_static(rows)

if __name__=='__main__': main()
