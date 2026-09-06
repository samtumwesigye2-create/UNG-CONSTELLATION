from datetime import datetime, timedelta, timezone
from skyfield.api import EarthSatellite, wgs84, load

_TS = load.timescale()

def _sat(name:str, line1:str, line2:str):
    return EarthSatellite(line1.strip(), line2.strip(), name or 'SATELLITE', _TS)

def position(name:str, line1:str, line2:str, lat:float, lon:float, elevation_m:float=0.0, at:str|None=None):
    sat=_sat(name,line1,line2)
    observer=wgs84.latlon(latitude_degrees=lat, longitude_degrees=lon, elevation_m=elevation_m)
    if at:
        dt=datetime.fromisoformat(at.replace('Z','+00:00'))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    else:
        dt=datetime.now(timezone.utc)
    t=_TS.from_datetime(dt)
    difference=sat-observer
    topocentric=difference.at(t)
    alt,az,distance=topocentric.altaz()
    geocentric=sat.at(t)
    sub=wgs84.subpoint(geocentric)
    return {
        'time':dt.isoformat(),
        'azimuth_deg':az.degrees,
        'elevation_deg':alt.degrees,
        'range_km':distance.km,
        'subpoint_lat':sub.latitude.degrees,
        'subpoint_lon':sub.longitude.degrees,
        'altitude_km':sub.elevation.km,
    }

def passes(name:str, line1:str, line2:str, lat:float, lon:float, elevation_m:float=0.0, hours:int=24, min_elevation_deg:float=10.0):
    sat=_sat(name,line1,line2)
    observer=wgs84.latlon(latitude_degrees=lat, longitude_degrees=lon, elevation_m=elevation_m)
    start=datetime.now(timezone.utc)
    end=start+timedelta(hours=max(1,min(hours,168)))
    t0=_TS.from_datetime(start); t1=_TS.from_datetime(end)
    times,events=sat.find_events(observer,t0,t1,altitude_degrees=min_elevation_deg)
    result=[]; current=None
    for t,event in zip(times,events):
        when=t.utc_datetime().replace(tzinfo=timezone.utc)
        alt,az,distance=(sat-observer).at(t).altaz()
        point={'time':when.isoformat(),'azimuth_deg':az.degrees,'elevation_deg':alt.degrees,'range_km':distance.km}
        if event==0:
            current={'rise':point,'culmination':None,'set':None}
        elif event==1 and current is not None:
            current['culmination']=point
        elif event==2 and current is not None:
            current['set']=point
            current['duration_s']=(when-datetime.fromisoformat(current['rise']['time'])).total_seconds()
            current['max_elevation_deg']=(current.get('culmination') or {}).get('elevation_deg')
            result.append(current); current=None
    return result
