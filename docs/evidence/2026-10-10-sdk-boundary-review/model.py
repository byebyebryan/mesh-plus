"""Design-only projection feasibility; production helpers remain unchanged."""
import asyncio
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path('/home/bryan/code/mesh-plus')
sys.path.insert(0,str(ROOT/'tests'))
from test_reader import CachedClient
from mesh_plus.observer import ObserverCodec
from mesh_plus.reader import Endpoint, Reader
from mesh_plus.view import current_sessions, reconstructed, validate_response

class Projection:
    def __init__(self, domain, host):
        self.domain,self.host=domain,host
        self.codec=ObserverCodec(domain,host,'default')
    def unpack(self, frame):
        self.codec.native(frame)
        snapshot=frame['snapshot']
        return {
            'owner': {'protocol':'tmux-observer.observation.v1' if self.domain=='tmux' else 'agent-observer.snapshot',
                      'version':1 if self.domain=='tmux' else 4,
                      'metadata':None if snapshot is None else {k:copy.deepcopy(v) for k,v in snapshot.items() if k!='sessions'},
                      'service':{k:copy.deepcopy(v) for k,v in frame.items() if k!='snapshot'}},
            'records':[] if snapshot is None else copy.deepcopy(snapshot['sessions']),
            'receipts':copy.deepcopy(self.codec.receipts(frame)),
            'publisher':self.codec.epoch(frame),
            'clock':self.codec.clock(frame),
            'emitted':self.codec.emitted(frame)}
    def record_receipts(self, record, state):
        key='default' if self.domain=='tmux' else record['identity']['provider']+':'+record['identity']['namespace']
        required=frozenset((r['sourceId'],r['component']) for r in state['receipts'] if r['sourceId']==key and r['health'] in {'current','partial'})
        return required or None
    def record_eligible(self, record, state):
        if self.domain=='agent' and not record['hasSavedHistory']:
            return record['runtime']['health']=='current' and any(component=='runtime' for source,component in self.record_receipts(record,state) or ())
        return True
    def restore(self, state):
        metadata=state['owner']['metadata']
        return {**state['owner']['service'],'snapshot':None if metadata is None else {**metadata,'sessions':state['records']}}

async def main():
    cases=[]
    for domain in ('tmux','agent'):
        local=CachedClient(domain,'local');remote=CachedClient(domain,'remote')
        async def connect_local():return local
        async def connect_remote():return remote
        selected=[Endpoint('local',True,None,connect_local),Endpoint('remote',False,'sha256:'+'a'*64,connect_remote)]
        reader=Reader(domain,selected,local_host='local',catalog_revision='sha256:'+'b'*64)
        view=await reader.snapshot();validate_response(view)
        expiry=max(r['expiresAtMs'] for h in view['mesh']['hosts'] for r in h['receipts'] if r['expiresAtMs'] is not None)
        for now in (view['mesh']['reader']['encodedAtMs'],expiry+1):
            effective=[]
            for h in view['mesh']['hosts']:
                profile=Projection(domain,h['hostId']);state=profile.unpack(reconstructed(view,h))
                current=frozenset((r['sourceId'],r['component']) for r in h['receipts'] if r['health'] in {'current','partial'} and r['expiresAtMs'] is not None and r['expiresAtMs']>now)
                if h['delivery']['status']!='ready' or h['viewState']!='current':continue
                for row in state['records']:
                    required=profile.record_receipts(row,state)
                    if required and required<=current and profile.record_eligible(row,state):effective.append(row)
            assert effective==current_sessions(view,now,view['mesh']['reader']['clock'])
        for host in view['mesh']['hosts']:
            frame=reconstructed(view,host)
            projected=Projection(domain,host['hostId']).unpack(frame)
            restored=Projection(domain,host['hostId']).restore(projected)
            assert restored==frame
            assert projected['owner']==host['owner']
            expected=[r for r in view['sessions'] if (r['hostId'] if domain=='tmux' else r['identity']['hostScope'])==host['hostId']]
            assert projected['records']==expected
            for r in host['receipts']:
                native=next(n for n in projected['receipts'] if (n['sourceId'],n['component'])==(r['sourceId'],r['component']))
                assert r['accepted']==native['accepted']
            cases.append({'domain':domain,'local':host['local'],'losslessOwnerAndRecords':True,'originalReceiptsPreserved':True})
    return {'state':'passed','scope':'projection feasibility against current validated local/fleet fixtures; no new SDK implementation or acceptance',
            'cases':cases,'caseCount':len(cases),'effectiveSelectionComparisons':4,'outputWireChanged':False,'sourceFilesChanged':False,'limits':['Pure shape/receipt roundtrip only; full future injected Reader and ReadGuard not implemented','Existing native semantics supplied by current reviewed validators']}

if __name__=='__main__':
    result=asyncio.run(main());result['modelSha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
