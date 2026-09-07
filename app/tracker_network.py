"""Receive-only multi-station geometry from the paired sat-tracker engine."""
import math
import numpy as np
WGS84_A=6378137.0;WGS84_F=1/298.257223563;WGS84_E2=WGS84_F*(2-WGS84_F)

def geodetic_to_ecef(lat_deg:float,lon_deg:float,alt_m:float)->np.ndarray:
    lat,lon=math.radians(lat_deg),math.radians(lon_deg);N=WGS84_A/math.sqrt(1-WGS84_E2*math.sin(lat)**2);x=(N+alt_m)*math.cos(lat)*math.cos(lon);y=(N+alt_m)*math.cos(lat)*math.sin(lon);z=(N*(1-WGS84_E2)+alt_m)*math.sin(lat);return np.array([x,y,z])/1000.0

def enu_to_ecef_direction(az_deg:float,el_deg:float,lat_deg:float,lon_deg:float)->np.ndarray:
    az,el=math.radians(az_deg),math.radians(el_deg);e=math.sin(az)*math.cos(el);n=math.cos(az)*math.cos(el);u=math.sin(el);lat,lon=math.radians(lat_deg),math.radians(lon_deg);R=np.array([[-math.sin(lon),-math.sin(lat)*math.cos(lon),math.cos(lat)*math.cos(lon)],[math.cos(lon),-math.sin(lat)*math.sin(lon),math.cos(lat)*math.sin(lon)],[0,math.cos(lat),math.sin(lat)]]);d=R@np.array([e,n,u]);return d/np.linalg.norm(d)

def triangulate_observations(observations:list)->dict:
    if len(observations)<2:raise ValueError('Need at least 2 station observations')
    rays=[]
    for o in observations:
        p=geodetic_to_ecef(float(o['lat']),float(o['lon']),float(o.get('elevation_m',0)));d=enu_to_ecef_direction(float(o['azimuth_deg']),float(o['elevation_deg']),float(o['lat']),float(o['lon']));rays.append((p,d))
    A=np.zeros((3,3));b=np.zeros(3)
    for p,d in rays:
        col=d.reshape(3,1);proj=np.eye(3)-col@col.T;A+=proj;b+=proj@p
    sol,*_=np.linalg.lstsq(A,b,rcond=None);res=[]
    for p,d in rays:
        v=sol-p;perp=v-np.dot(v,d)*d;res.append(np.linalg.norm(perp))
    return {'point_ecef_km':[round(float(x),3) for x in sol],'residual_km':round(float(np.mean(res)),2),'stations':len(observations),'quality_note':'Estimate only; accuracy depends strongly on simultaneous pointing precision.'}
