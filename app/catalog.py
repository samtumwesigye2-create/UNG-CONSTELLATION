import requests

BASE='https://celestrak.org/NORAD/elements/gp.php'

def fetch_by_catnr(norad_id:str):
    r=requests.get(BASE,params={'CATNR':str(norad_id),'FORMAT':'TLE'},timeout=15)
    r.raise_for_status()
    lines=[x.strip() for x in r.text.splitlines() if x.strip()]
    if len(lines)<3: raise ValueError('No TLE returned')
    name,line1,line2=lines[0],lines[1],lines[2]
    if not line1.startswith('1 ') or not line2.startswith('2 '): raise ValueError('Invalid TLE response')
    return {'norad_id':str(norad_id),'name':name,'line1':line1,'line2':line2,'source':'CelesTrak'}

def search_name(name:str,limit:int=25):
    r=requests.get(BASE,params={'NAME':name,'FORMAT':'TLE'},timeout=15)
    r.raise_for_status()
    lines=[x.strip() for x in r.text.splitlines() if x.strip()]
    out=[]
    for i in range(0,len(lines)-2,3):
        n,l1,l2=lines[i:i+3]
        if not l1.startswith('1 ') or not l2.startswith('2 '): continue
        norad=l1[2:7].strip()
        out.append({'norad_id':norad,'name':n,'line1':l1,'line2':l2,'source':'CelesTrak'})
        if len(out)>=limit: break
    return out
