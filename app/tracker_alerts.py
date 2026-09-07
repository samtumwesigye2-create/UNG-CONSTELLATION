"""Telemetry alert evaluation for paired sat-tracker data.
Delivery remains delegated to approved UNG notification services.
"""
from fastapi import APIRouter, Body, Depends
from .security import require_role

router=APIRouter(prefix='/v1/tracker/alerts',tags=['sat-tracker-alerts'])

def evaluate(fields:dict,limits:dict)->list:
 alerts=[]
 for name,value in fields.items():
  if value is None or name not in limits:continue
  rule=limits.get(name) or {}
  try:v=float(value)
  except Exception:continue
  lo=rule.get('min');hi=rule.get('max')
  if lo is not None and v<float(lo):alerts.append({'field':name,'severity':rule.get('severity','warning'),'condition':'below_min','value':v,'threshold':float(lo)})
  if hi is not None and v>float(hi):alerts.append({'field':name,'severity':rule.get('severity','warning'),'condition':'above_max','value':v,'threshold':float(hi)})
 return alerts

@router.post('/evaluate')
def evaluate_alerts(fields:dict=Body(...),limits:dict=Body(...),user=Depends(require_role('operator'))):
 alerts=evaluate(fields,limits)
 return {'count':len(alerts),'alerts':alerts,'delivery':'UNG notification integration','receive_only':True}
