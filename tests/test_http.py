import base64
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from test_importer import fixture


class HTTPTests(unittest.TestCase):
    def setUp(self):
        from server import create_server
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.server=create_server(Path(self.tmp.name),0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close)
        self.cookie='';self.csrf=''

    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()

    def call(self,method,path,data=None,origin=None,csrf=True):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        headers={'Content-Type':'application/json','Cookie':self.cookie}
        if csrf:headers['X-CSRF-Token']=self.csrf
        if origin:headers['Origin']=origin
        c.request(method,path,body=None if data is None else json.dumps(data),headers=headers)
        r=c.getresponse();body=r.read();status=r.status
        cookie=r.getheader('Set-Cookie')
        if cookie:self.cookie=cookie.split(';')[0]
        c.close()
        return status,json.loads(body) if body else {}

    def login(self,user='promo',password='promo-demo'):
        status,body=self.call('POST','/api/login',{'username':user,'password':password})
        self.assertEqual(status,200);self.csrf=body['csrf']

    def test_session_csrf_origin_and_roles(self):
        self.assertEqual(self.call('GET','/api/catalogs')[0],403)
        self.login()
        body={'filename':'demo.idml','content':base64.b64encode(fixture()).decode()}
        self.assertEqual(self.call('POST','/api/catalogs',body,csrf=False)[0],403)
        self.assertEqual(self.call('POST','/api/catalogs',body,origin='https://evil.example')[0],403)
        status,st=self.call('POST','/api/catalogs',body);self.assertEqual(status,200)
        cid=st['id']
        self.assertEqual(self.call('GET','/api/library')[0],200)
        self.assertEqual(self.call('GET','/api/library-search?q=ERD9717WA&catalog='+cid)[1]['target_count'],1)
        self.assertEqual(self.call('GET','/api/campaigns')[1],[])
        status,products=self.call('GET',f'/api/catalogs/{cid}/products')
        self.assertEqual(status,200);self.assertEqual(products['model_count'],1)
        from urllib.parse import quote
        inquiry=f'/api/catalogs/{cid}/inquiry?q='+quote('全ての型番と価格を一覧にして')
        status,answer=self.call('GET',inquiry)
        self.assertEqual(status,200);self.assertEqual(answer['kind'],'prices');self.assertEqual(answer['occurrence_count'],1)
        self.login('reader','reader-demo')
        for path in ['/api/library','/api/library-search?q=ERD9717WA&catalog='+cid,'/api/campaigns']:
            self.assertEqual(self.call('GET',path)[0],403)
        self.assertEqual(self.call('POST','/api/campaigns',{})[0],403)
        self.assertEqual(self.call('GET',f'/api/catalogs/{cid}/products')[0],403)
        self.assertEqual(self.call('GET',f'/api/catalogs/{cid}/products.csv')[0],403)
        self.server.service.reader_preview=True
        self.assertEqual(self.call('GET',inquiry)[1]['kind'],'restricted')
        self.server.service.reader_preview=False
        self.assertEqual(self.call('GET','/api/catalogs/'+cid)[0],403)
        status,body=self.call('POST',f'/api/catalogs/{cid}/operations',{'version':1,'operation':{'type':'add_page'},'role':'editor'})
        self.assertEqual(status,403)


if __name__=='__main__':unittest.main()
