import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from test_importer import fixture
from catalog_core.service import Service,Actor


class MCPTests(unittest.TestCase):
    def test_real_stdio_handshake_and_published_only_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=Service(Path(tmp));actor=Actor('promo','販促担当','editor')
            state=service.import_catalog(fixture(),'sample.idml',actor);cid=state['id']
            state=service.apply_operation(cid,actor,state['version'],{'type':'publish'})
            eid=state['document']['pages'][0]['elements'][0]['id']
            state=service.apply_operation(cid,actor,state['version'],{'type':'edit_text','element_id':eid,'text':'PRIVATE-DRAFT'})
            messages=[
                {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'test','version':'1'}}},
                {'jsonrpc':'2.0','method':'notifications/initialized'},
                {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'catalog.find_occurrences','arguments':{'catalog_id':cid,'query':'ERD9717WA'}}},
                {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'catalog.find_occurrences','arguments':{'catalog_id':cid,'query':'PRIVATE-DRAFT'}}},
            ]
            script=Path(__file__).resolve().parents[1]/'mcp_server.py'
            proc=subprocess.run([sys.executable,str(script),'--data',tmp],input='\n'.join(json.dumps(m) for m in messages)+'\n',encoding='utf-8',capture_output=True,timeout=20)
            self.assertEqual(proc.returncode,0,proc.stderr)
            responses=[json.loads(line) for line in proc.stdout.splitlines()]
            self.assertEqual(len(responses),4)
            self.assertEqual(responses[0]['result']['protocolVersion'],'2025-11-25')
            self.assertEqual(len(responses[1]['result']['tools']),3)
            self.assertEqual(responses[2]['result']['structuredContent']['occurrence_count'],1)
            self.assertEqual(responses[3]['result']['structuredContent']['occurrence_count'],0)


if __name__=='__main__':unittest.main()
