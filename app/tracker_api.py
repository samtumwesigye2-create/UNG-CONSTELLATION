from fastapi import APIRouter, HTTPException, Body, Depends
from . import tracker_engine, tracker_network
from .security import require_role
router=APIRouter(prefix='/v1/tracker',tags=['sat-tracker-engine'])

@router.get('/snapshot')
def snapshot(norad_id:str,lat:float,lon:float,elevation_m:float=0,hours:int=24,min_elevation_deg:float=10):
    try:return tracker_engine.satellite_snapshot(norad_id,lat,lon,elevation_m,max(1,min(hours,72)),min_elevation_deg)
    except Exception as e:raise HTTPException(502,str(e))

@router.get('/passes')
def passes(norad_id:str,lat:float,lon:float,elevation_m:float=0,hours:int=24,min_elevation_deg:float=10):
    try:return tracker_engine.pass_track(norad_id,lat,lon,elevation_m,max(1,min(hours,72)),min_elevation_deg)
    except Exception as e:raise HTTPException(502,str(e))

@router.post('/triangulate')
def triangulate(observations:list=Body(...,embed=True),user=Depends(require_role('observer'))):
    try:
        out=tracker_network.triangulate_observations(observations);out['receive_only']=True;out['actor']=user.get('sub');return out
    except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
