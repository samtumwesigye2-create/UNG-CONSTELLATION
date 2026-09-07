"""Adapter that pairs the uploaded sat-tracker model with UNG-CONSTELLATION's existing catalog/orbit stack."""
from . import catalog, orbit, satinfo

def satellite_snapshot(norad_id:str,lat:float,lon:float,elevation_m:float=0,hours:int=24,min_elevation_deg:float=10):
    t=catalog.fetch_by_catnr(norad_id)
    info=satinfo.satellite_info(t['name'],t['line1'],t['line2'])
    pos=orbit.position(t['name'],t['line1'],t['line2'],lat,lon,elevation_m)
    passes=orbit.passes(t['name'],t['line1'],t['line2'],lat,lon,elevation_m,hours,min_elevation_deg)
    ground=orbit.ground_track(t['name'],t['line1'],t['line2'],45,90,60)
    return {'satellite':t['name'],'norad_id':t['norad_id'],'source':t['source'],'metadata':info,'position':pos,'passes':passes,'ground_track':ground}

def pass_track(norad_id:str,lat:float,lon:float,elevation_m:float=0,hours:int=24,min_elevation_deg:float=10):
    t=catalog.fetch_by_catnr(norad_id)
    ps=orbit.passes(t['name'],t['line1'],t['line2'],lat,lon,elevation_m,hours,min_elevation_deg)
    return {'satellite':t['name'],'norad_id':t['norad_id'],'passes':ps}
