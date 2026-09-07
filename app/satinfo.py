"""Satellite catalog metadata and TLE freshness checks adapted from the paired sat-tracker engine."""
from datetime import datetime, timedelta, timezone
STALE_AFTER_DAYS=5.0

def _tle_epoch_datetime(line1:str)->datetime:
    epoch_str=line1[18:32].strip();yy=int(epoch_str[:2]);year=2000+yy if yy<57 else 1900+yy;day=float(epoch_str[2:]);return datetime(year,1,1,tzinfo=timezone.utc)+timedelta(days=day-1)

def _intl_designator(line1:str)->dict:
    raw=line1[9:17].strip()
    if len(raw)<5:return {'raw':raw,'launch_year':None,'launch_number':None,'piece':None}
    yy=int(raw[:2]);year=2000+yy if yy<57 else 1900+yy
    try:number=int(raw[2:5])
    except ValueError:number=None
    return {'raw':raw,'launch_year':year,'launch_number':number,'piece':raw[5:]}

def satellite_info(name:str,line1:str,line2:str)->dict:
    norad_id=line2[2:7].strip();inclination=float(line2[8:16]);raan=float(line2[17:25]);ecc=float('0.'+line2[26:33].strip());argp=float(line2[34:42]);ma=float(line2[43:51]);mm=float(line2[52:63]);period=1440.0/mm if mm else None;epoch=_tle_epoch_datetime(line1);age=(datetime.now(timezone.utc)-epoch).total_seconds()/86400.0
    return {'name':name,'norad_id':norad_id,'international_designator':_intl_designator(line1),'inclination_deg':round(inclination,3),'eccentricity':round(ecc,7),'raan_deg':round(raan,3),'arg_perigee_deg':round(argp,3),'mean_anomaly_deg':round(ma,3),'mean_motion_rev_per_day':round(mm,8),'orbital_period_min':round(period,2) if period else None,'tle_epoch_utc':epoch.isoformat(),'tle_age_days':round(age,2),'tle_stale':age>STALE_AFTER_DAYS,'source_quality':'public_gp_tle'}
