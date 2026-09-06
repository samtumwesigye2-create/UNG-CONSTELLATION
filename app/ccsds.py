from datetime import datetime, timezone

def decode_space_packet(data:bytes):
    if len(data)<6: raise ValueError('CCSDS packet requires at least 6 bytes')
    w0=int.from_bytes(data[0:2],'big'); w1=int.from_bytes(data[2:4],'big'); w2=int.from_bytes(data[4:6],'big')
    n=w2+1; payload=data[6:6+n]
    return {'version':(w0>>13)&7,'type':'telecommand' if ((w0>>12)&1) else 'telemetry','secondary_header':bool((w0>>11)&1),
            'apid':w0&0x7ff,'sequence_flags':(w1>>14)&3,'sequence_count':w1&0x3fff,'data_length':n,
            'payload_hex':payload.hex(),'received_at':datetime.now(timezone.utc).isoformat()}

def encode_space_packet(apid:int,payload:bytes,sequence_count:int=0,telecommand:bool=False):
    if not 0<=apid<=2047: raise ValueError('APID must be 0..2047')
    w0=((1 if telecommand else 0)<<12)|apid; w1=(3<<14)|(sequence_count&0x3fff); w2=max(len(payload)-1,0)
    return w0.to_bytes(2,'big')+w1.to_bytes(2,'big')+w2.to_bytes(2,'big')+payload
