"""Receive-only telemetry helpers imported from the paired sat-tracker design.
No frame-building or transmit functions are exposed here.
"""
import struct
from fastapi import APIRouter, Body, Depends, HTTPException
from .security import require_role

router = APIRouter(prefix='/v1/tracker/telemetry', tags=['sat-tracker-telemetry'])
FEND, FESC, TFEND, TFESC = 0xC0, 0xDB, 0xDC, 0xDD
STRUCT_TYPES={'uint8':'B','int8':'b','uint16':'H','int16':'h','uint32':'I','int32':'i','float32':'f'}

def kiss_unescape(data:bytes)->bytes:
 out=bytearray();i=0
 while i<len(data):
  b=data[i]
  if b==FESC and i+1<len(data):
   n=data[i+1]
   if n==TFEND:out.append(FEND);i+=2;continue
   if n==TFESC:out.append(FESC);i+=2;continue
  out.append(b);i+=1
 return bytes(out)

def _addr(field:bytes)->dict:
 if len(field)<7:return {'callsign':'','ssid':0,'is_last':True}
 return {'callsign':''.join(chr(b>>1) for b in field[:6]).strip(),'ssid':(field[6]>>1)&0x0F,'is_last':bool(field[6]&1)}

def decode_ax25_frame(kiss_payload:bytes)->dict:
 if len(kiss_payload)<15:return {'error':'frame too short','raw_hex':kiss_payload.hex()}
 body=kiss_payload[1:];dest=_addr(body[:7]);source=_addr(body[7:14]);offset=14;repeaters=[]
 if not source['is_last']:
  while offset+7<=len(body):
   r=_addr(body[offset:offset+7]);repeaters.append(r);offset+=7
   if r['is_last']:break
 if offset+2>len(body):return {'error':'frame truncated after addressing','raw_hex':kiss_payload.hex()}
 info=body[offset+2:]
 return {'destination':f"{dest['callsign']}-{dest['ssid']}",'source':f"{source['callsign']}-{source['ssid']}",'repeaters':[f"{r['callsign']}-{r['ssid']}" for r in repeaters],'control':body[offset],'pid':hex(body[offset+1]),'info_hex':info.hex(),'info_len':len(info)}

def decode_fields(payload:bytes,schema:list)->dict:
 decoded={}
 for field in schema:
  name=field.get('name','unnamed')
  try:
   fmt={'big':'>','little':'<'}.get(field.get('byteorder','big'),'>')+STRUCT_TYPES[field['type']]
   raw=struct.unpack_from(fmt,payload,int(field['offset']))[0]
   value=raw*field.get('scale',1.0)+field.get('add',0.0)
   decoded[name]=round(value,6) if isinstance(value,float) else value
  except Exception:decoded[name]=None
 return decoded

@router.post('/ax25/decode')
def ax25_decode(frame_hex:str=Body(...,embed=True),user=Depends(require_role('observer'))):
 try:return {'decoded':decode_ax25_frame(kiss_unescape(bytes.fromhex(frame_hex))),'receive_only':True}
 except ValueError as e:raise HTTPException(400,str(e))

@router.post('/fields/decode')
def fields_decode(payload_hex:str=Body(...),schema:list=Body(...),user=Depends(require_role('observer'))):
 try:return {'fields':decode_fields(bytes.fromhex(payload_hex),schema),'receive_only':True}
 except ValueError as e:raise HTTPException(400,str(e))
