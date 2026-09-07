from datetime import datetime, timedelta, timezone
from math import acos, cos, degrees
from skyfield.api import EarthSatellite, wgs84, load

_TS = load.timescale()
_EARTH_KM = 6378.137

def _sat(name:str, line1:str, line2:str):
    return EarthSatellite(line1.strip(), line2.strip(), name or 'SATELLITE', _TS)

def _dt(value=None):
    if value:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)

def position(name:str, line1:str, line2:str, lat:float, lon:float, elevation_m:float=0.0, at:str|None=None):
    sat=_sat(name,line1,line2); observer=wgs84.latlon(latitude_degrees=lat,longitude_degrees=lon,elevation_m=elevation_m)
    dt=_dt(at); t=_TS.from_datetime(dt); topocentric=(sat-observer).at(t); alt,az,distance=topocentric.altaz(); sub=wgs84.subpoint(sat.at(t))
    altitude=max(0.0,sub.elevation.km)
    footprint=degrees(acos(_EARTH_KM/(_EARTH_KM+altitude))) if altitude else 0.0
    return {'time':dt.isoformat(),'azimuth_deg':az.degrees,'elevation_deg':alt.degrees,'range_km':distance.km,'subpoint_lat':sub.latitude.degrees,'subpoint_lon':sub.longitude.degrees,'altitude_km':sub.elevation.km,'visibility_radius_deg':footprint,'visibility_radius_km':_EARTH_KM*footprint*3.141592653589793/180.0}

def ground_track(name:str,line1:str,line2:str,minutes_before:int=45,minutes_after:int=90,step_seconds:int=60):
    sat=_sat(name,line1,line2); now=datetime.now(timezone.utc); out=[]
    start=now-timedelta(minutes=max(0,min(minutes_before,360))); end=now+timedelta(minutes=max(1,min(minutes_after,720))); step=max(15,min(step_seconds,600)); d=start
    while d<=end:
        sub=wgs84.subpoint(sat.at(_TS.from_datetime(d)))
        out.append({'time':d.isoformat(),'lat':sub.latitude.degrees,'lon':sub.longitude.degrees,'altitude_km':sub.elevation.km})
        d+=timedelta(seconds=step)
    return out

def passes(name:str, line1:str, line2:str, lat:float, lon:float, elevation_m:float=0.0, hours:int=24, min_elevation_deg:float=10.0):
    sat=_sat(name,line1,line2); observer=wgs84.latlon(latitude_degrees=lat,longitude_degrees=lon,elevation_m=elevation_m)
    start=datetime.now(timezone.utc); end=start+timedelta(hours=max(1,min(hours,168))); t0=_TS.from_datetime(start); t1=_TS.from_datetime(end)
    times,events=sat.find_events(observer,t0,t1,altitude_degrees=min_elevation_deg); result=[]; current=None
    for t,event in zip(times,events):
        when=t.utc_datetime().replace(tzinfo=timezone.utc); alt,az,distance=(sat-observer).at(t).altaz(); point={'time':when.isoformat(),'azimuth_deg':az.degrees,'elevation_deg':alt.degrees,'range_km':distance.km}
        if event==0: current={'rise':point,'culmination':None,'set':None}
        elif event==1 and current is not None: current['culmination']=point
        elif event==2 and current is not None:
            current['set']=point; current['duration_s']=(when-datetime.fromisoformat(current['rise']['time'])).total_seconds(); current['max_elevation_deg']=(current.get('culmination') or {}).get('elevation_deg'); result.append(current); current=None
    return result
