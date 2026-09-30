"""Loopback-only Catalog Studio HTTP application."""
import argparse
import base64
import binascii
import json
import mimetypes
import sys
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,unquote,quote

from catalog_core.service import Service,ConflictError,Actor
from catalog_core.exports import instruction_package,released_package,search_csv

ROOT=Path(__file__).resolve().parent
MAX_BODY=90*1024*1024


class Handler(BaseHTTPRequestHandler):
    server_version='CatalogStudio/0.1'

    def log_message(self,fmt,*args):
        # Do not log source text, filenames, session cookies or credentials.
        sys.stderr.write(f'{self.log_date_time_string()} {self.command} {self.path.split("?")[0]}\n')

    def send(self,content,status=200,content_type='application/json; charset=utf-8',filename=None,cookie=None):
        if isinstance(content,(dict,list)):
            content=json.dumps(content,ensure_ascii=False,allow_nan=False).encode('utf-8')
        elif isinstance(content,str):content=content.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','same-origin')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
        if filename:self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(filename))
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(content)

    def token(self):
        try:
            jar=SimpleCookie();jar.load(self.headers.get('Cookie',''))
            return jar['catalog_session'].value if 'catalog_session' in jar else ''
        except Exception:return ''

    def body(self):
        try:length=int(self.headers.get('Content-Length','0'))
        except ValueError:raise ValueError('リクエストの長さが不正です。')
        if length<=0 or length>MAX_BODY:raise ValueError('ファイルが大きすぎるか、リクエストが空です。')
        if not self.headers.get('Content-Type','').startswith('application/json'):raise ValueError('JSON形式で送信してください。')
        try:
            value=json.loads(self.rfile.read(length),parse_constant=lambda _: (_ for _ in ()).throw(ValueError('非有限の数値です。')))
        except (json.JSONDecodeError,UnicodeDecodeError):raise ValueError('リクエストを読み取れません。')
        if not isinstance(value,dict):raise ValueError('リクエストはオブジェクトにしてください。')
        return value

    def check_origin(self):
        hosts={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        if self.headers.get('Host','') not in hosts:raise PermissionError('ローカルホスト経由でアクセスしてください。')
        origin=self.headers.get('Origin')
        if origin and origin not in {'http://'+h for h in hosts}:raise PermissionError('別サイトからの操作は受け付けません。')

    def do_GET(self):self.dispatch(False)
    def do_POST(self):self.dispatch(True)

    def dispatch(self,mutation):
        try:
            data=self.body() if mutation else {}
            self.check_origin()
            path=urlsplit(self.path)
            parts=[unquote(p) for p in path.path.split('/') if p]
            query=parse_qs(path.query)
            service=self.server.service
            if not mutation and parts==['health']:
                return self.send({'status':'ok','app':'catalog-studio'})
            if not parts or parts[0]!='api':
                if mutation:return self.send({'error':'Not found'},404)
                relative='index.html' if not parts else '/'.join(parts)
                file=(ROOT/'static'/relative).resolve()
                if not file.is_relative_to((ROOT/'static').resolve()) or not file.is_file():return self.send({'error':'Not found'},404)
                content_type=mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
                if file.suffix=='.js':content_type='text/javascript'
                return self.send(file.read_bytes(),content_type=content_type+'; charset=utf-8')
            if parts==['api','login'] and mutation:
                session=service.login(data.get('username'),data.get('password'))
                return self.send({'actor':session['actor'],'csrf':session['csrf']},cookie=f'catalog_session={session["token"]}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200')
            actor,csrf=service.session(self.token())
            if mutation and self.headers.get('X-CSRF-Token')!=csrf:raise PermissionError('セッションを更新してから操作してください。')
            if parts==['api','session'] and not mutation:return self.send({'actor':actor.__dict__,'csrf':csrf})
            if parts==['api','logout'] and mutation:
                service.logout(self.token())
                return self.send({'ok':True},cookie='catalog_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if parts==['api','library'] and not mutation:return self.send(service.library(actor))
            if parts in (['api','library-search'],['api','campaigns']):
                return self.send({'error':'冊子間の連携機能は提供していません。画面を再読み込みしてください。'},410)
            if parts==['api','catalogs']:
                if not mutation:return self.send(service.list_catalogs(actor))
                raw=decode_upload(data)
                return self.send(service.import_catalog(raw,data.get('filename','catalog.idml'),actor))
            if len(parts)>=3 and parts[:2]==['api','catalogs']:
                cid=parts[2]
                if len(parts)==3 and not mutation:return self.send(service.get_catalog(cid,actor))
                if len(parts)==4:
                    action=parts[3]
                    if action=='submission-import-preview' and mutation:
                        return self.send(service.preview_submission_import(cid,actor,data))
                    if action=='operations' and mutation:
                        if not isinstance(data.get('operation'),dict):raise ValueError('操作を指定してください。')
                        return self.send(service.apply_operation(cid,actor,data.get('version'),data['operation']))
                    if action=='attachments' and mutation:
                        return self.send(service.attach(cid,actor,data.get('version'),data.get('filename'),decode_upload(data),data.get('submission_id')))
                    if action in ('inquiry','inquiry.csv') and not mutation:
                        result=service.inquire(cid,actor,query.get('q',[''])[0])
                        if action=='inquiry':return self.send(result)
                        from catalog_core.inquiry import inquiry_csv
                        return self.send(inquiry_csv(result),content_type='text/csv; charset=utf-8',filename='catalog-answer.csv')
                    if action=='products' and not mutation:return self.send(service.products(cid,actor))
                    if action=='products.csv' and not mutation:
                        from catalog_core.products import product_csv
                        return self.send(product_csv(service.products(cid,actor)),content_type='text/csv; charset=utf-8',filename='catalog-product-candidates.csv')
                    if action=='search' and not mutation:return self.send(service.search(cid,actor,query.get('q',[''])[0]))
                    if action=='search.csv' and not mutation:
                        result=service.search(cid,actor,query.get('q',[''])[0])
                        return self.send(search_csv(result),content_type='text/csv; charset=utf-8',filename='catalog-search.csv')
                    if action=='instructions.zip' and not mutation:
                        return self.send(instruction_package(service,cid,actor),content_type='application/zip',filename='catalog-instructions.zip')
                    if action=='released.zip' and not mutation:
                        return self.send(released_package(service,cid,actor),content_type='application/zip',filename='catalog-released.zip')
                if len(parts)==5 and parts[3]=='assets' and not mutation:
                    file=service.asset_path(cid,actor,parts[4]);typ=mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
                    inline=typ in ('image/png','image/jpeg','image/webp')
                    return self.send(file.read_bytes(),content_type=typ,filename=None if inline else file.name)
            return self.send({'error':'Not found'},404)
        except PermissionError as e:self.send({'error':str(e)},403)
        except ConflictError as e:self.send({'error':str(e),'conflict':True},409)
        except (ValueError,KeyError,TypeError,binascii.Error) as e:self.send({'error':str(e) or '入力が不正です。'},400)
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stderr)
            self.send({'error':'処理に失敗しました。入力ファイルを確認し、必要ならサーバーログを参照してください。'},500)


def decode_upload(data):
    content=data.get('content')
    if not isinstance(content,str):raise ValueError('ファイルを選択してください。')
    return base64.b64decode(content,validate=True)


def create_server(directory,port=8765):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.service=Service(directory)
    server.daemon_threads=True
    return server


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8877)
    parser.add_argument('--data',type=Path,default=ROOT/'data')
    parser.add_argument('--import-file',type=Path)
    args=parser.parse_args()
    server=create_server(args.data,args.port)
    if args.import_file and not server.service.list_catalogs(Actor('promo','販促担当','editor')):
        result=server.service.import_catalog(args.import_file.read_bytes(),args.import_file.name,Actor('promo','販促担当','editor'))
        print('Imported catalog:',result['id'],flush=True)
    print(f'Catalog Studio: http://127.0.0.1:{server.server_port}',flush=True)
    print('LOCAL DEMO ONLY. promo / promo-demo; development / development-demo; reader / reader-demo',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
