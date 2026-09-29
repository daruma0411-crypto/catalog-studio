"""Bounded IDML parsing. No InDesign, archive extraction, or external URLs."""
import base64
import hashlib
import io
import math
import re
import struct
import warnings as pywarnings
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from PIL import Image

MAX_ARCHIVE = 250 * 1024 * 1024
MAX_XML = 32 * 1024 * 1024
IDENTITY = (1, 0, 0, 1, 0, 0)


def checked_zip(data):
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as e:
        raise ValueError('ZIP / IDMLとして読み取れません。') from e
    infos = z.infolist()
    if len(infos) > 8000 or sum(i.file_size for i in infos) > MAX_ARCHIVE:
        z.close()
        raise ValueError('展開後のファイル数または容量が上限を超えています。')
    names = set()
    for item in infos:
        name = item.filename.replace('\\', '/')
        if name.startswith('/') or ':' in name or '..' in PurePosixPath(name).parts or name in names:
            z.close()
            raise ValueError('不正または重複したZIP内パスです。')
        names.add(name)
    return z


def xml(data):
    if len(data) > MAX_XML or re.search(br'<!\s*(?:DOCTYPE|ENTITY)', data, re.I):
        raise ValueError('XMLが大きすぎるか、未対応の宣言が含まれます。')
    try:
        return ET.fromstring(data)
    except ET.ParseError as e:
        raise ValueError('IDML内のXMLを読み取れません。') from e


def number(value, default=0):
    try:
        n = float(value)
        return n if math.isfinite(n) and abs(n) < 1000000 else default
    except (TypeError, ValueError):
        return default


def matrix(value):
    parts = (value or '').split()
    return tuple(number(x) for x in parts) if len(parts) == 6 else IDENTITY


def mul(p, q):
    a,b,c,d,e,f = p
    g,h,i,j,k,l = q
    return (a*g+c*h,b*g+d*h,a*i+c*j,b*i+d*j,a*k+c*l+e,b*k+d*l+f)


def point(m, x, y):
    a,b,c,d,e,f=m
    return a*x+c*y+e,b*x+d*y+f


def box(points):
    xs,ys=zip(*points)
    return [min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)]


def path_box(node, transform):
    pts=[]
    for p in node.findall('./Properties/PathGeometry/GeometryPathType/PathPointArray/PathPointType'):
        parts=p.get('Anchor','').split()
        if len(parts)==2:
            pts.append(point(transform,*[number(v) for v in parts]))
    if pts:
        return box(pts)
    raw=node.get('GeometricBounds','').split()
    if len(raw)==4:
        t,l,b,r=map(number,raw)
        return box([point(transform,l,t),point(transform,r,t),point(transform,r,b),point(transform,l,b)])
    return None


def overlap(a,b):
    return max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))*max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))


def open_image(data):
    """Pillow plus bounded raw RGB16 PSD composite support (Adobe PSD spec)."""
    if len(data)>=40 and data[:4]==b'8BPS' and struct.unpack_from('>H',data,22)[0]==16:
        version=struct.unpack_from('>H',data,4)[0]
        channels,height,width,depth,mode=struct.unpack_from('>HIIHH',data,12)
        if version!=1 or mode!=3 or channels<3 or channels>56 or width<1 or height<1 or width*height>40_000_000:
            raise ValueError('この16bit PSDの形式・画素数には対応していません。')
        offset=26
        for _ in range(3):
            if offset+4>len(data):raise ValueError('PSDのセクションが不完全です。')
            length=struct.unpack_from('>I',data,offset)[0];offset+=4+length
        if offset+2>len(data) or struct.unpack_from('>H',data,offset)[0]!=0:raise ValueError('16bit PSDは非圧縮RGB合成画像に対応しています。PNGへの変換も利用できます。')
        offset+=2;plane=width*height*2
        if len(data)-offset<plane*channels:raise ValueError('PSDの画像データが不完全です。')
        bands=[Image.frombytes('L',(width,height),data[offset+i*plane:offset+(i+1)*plane:2]) for i in range(3)]
        return Image.merge('RGB',bands)
    return Image.open(io.BytesIO(data))


def save_image(data, directory):
    if len(data)>30*1024*1024:
        raise ValueError('画像の容量が大きすぎます。')
    with pywarnings.catch_warnings():
        pywarnings.simplefilter('error', Image.DecompressionBombWarning)
        with open_image(data) as im:
            if im.width*im.height>40_000_000:
                raise ValueError('画像の画素数が大きすぎます。')
            im.load()
            im=im.convert('RGBA')
            im.thumbnail((2400,2400))
            out=io.BytesIO()
            im.save(out,format='PNG')
    content=out.getvalue()
    key=hashlib.sha256(content).hexdigest()[:24]+'.png'
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    dest=directory/key
    if not dest.exists():
        dest.write_bytes(content)
    return key


def read_package(data, filename):
    """Return IDML bytes, filename, related assets and optional matching PDF."""
    with checked_zip(data) as z:
        if 'designmap.xml' in z.namelist():
            return data,Path(filename).name,{},None
        ids=[n for n in z.namelist() if n.lower().endswith('.idml') and not n.startswith('__MACOSX/')]
        if len(ids)!=1:
            raise ValueError('ZIPにはIDMLを1つだけ入れてください。')
        idml=ids[0]
        links={}
        for n in z.namelist():
            if n.lower().endswith(('.png','.jpg','.jpeg','.psd','.tif','.tiff','.webp')):
                base=PurePosixPath(n).name
                if base in links:
                    raise ValueError('同名の画像が複数あります。画像名を一意にしてください。')
                links[base]=z.read(n)
        pdf_name=str(PurePosixPath(idml).with_suffix('.pdf'))
        pdf=z.read(pdf_name) if pdf_name in z.namelist() else None
        return z.read(idml),PurePosixPath(idml).name,links,pdf


def parse_idml(data, assets_dir, linked_files=None):
    linked_files=linked_files or {}
    assets_dir=Path(assets_dir)
    notes=[]
    result={'pages':[],'stories':{},'assets':{},'warnings':notes,'source_hash':hashlib.sha256(data).hexdigest(),'format':'idml','schema_version':1}
    assets_dir.mkdir(parents=True,exist_ok=True)
    for filename,content in linked_files.items():
        filename=Path(filename).name
        suffix=Path(filename).suffix.lower()
        if suffix not in ('.psd','.png','.jpg','.jpeg','.tif','.tiff','.webp'):continue
        aid=hashlib.sha256(content).hexdigest()[:24]+suffix
        (assets_dir/aid).write_bytes(content)
        asset=result['assets'].setdefault(aid,{'id':aid,'name':filename,'kind':'source-image','link_names':[]})
        if filename not in asset['link_names']:asset['link_names'].append(filename)
    colors={'Color/Black':'#202020','Swatch/None':'transparent','Color/Paper':'#ffffff'}
    styles={}
    image_cache={}
    with checked_zip(data) as z:
        if 'designmap.xml' not in z.namelist():
            raise ValueError('IDMLのdesignmap.xmlがありません。')
        design=xml(z.read('designmap.xml'))
        hidden_layers={e.get('Self') for e in design.iter('Layer') if e.get('Visible')=='false'}
        if 'Resources/Graphic.xml' in z.namelist():
            for color in xml(z.read('Resources/Graphic.xml')).iter('Color'):
                vals=[number(v) for v in color.get('ColorValue','').split()]
                if color.get('Space')=='CMYK' and len(vals)==4:
                    c,m,y,k=[v/100 for v in vals]
                    vals=[round(255*(1-c)*(1-k)),round(255*(1-m)*(1-k)),round(255*(1-y)*(1-k))]
                if len(vals)==3:
                    colors[color.get('Self')]= '#'+''.join(f'{int(max(0,min(255,v))):02x}' for v in vals)
        if 'Resources/Styles.xml' in z.namelist():
            for e in xml(z.read('Resources/Styles.xml')).iter():
                if e.tag in ('ParagraphStyle','CharacterStyle'):
                    styles[e.get('Self')]=dict(e.attrib)

        def attrs(node, inherited=None):
            a=dict(inherited or {})
            for field in ('AppliedParagraphStyle','AppliedCharacterStyle'):
                a.update(styles.get(node.get(field),{}))
            a.update(node.attrib)
            return a

        def runs(node, inherited=None):
            a=attrs(node,inherited)
            pieces=[]
            for child in node:
                if child.tag=='Content':
                    pieces.append({'text':child.text or '', 'size':number(a.get('PointSize'),8), 'bold':bool(re.search('bold|heavy',a.get('FontStyle',''),re.I)), 'color':colors.get(a.get('FillColor'),'#202020')})
                elif child.tag in ('Br','ForcedLineBreak'):
                    pieces.append({'text':'\n','size':number(a.get('PointSize'),8)})
                elif child.tag=='Tab':
                    pieces.append({'text':'\t','size':number(a.get('PointSize'),8)})
                elif child.tag=='Table':
                    pieces.append({'text':'\n','size':number(a.get('PointSize'),8)})
                elif child.tag in ('CharacterStyleRange','ParagraphStyleRange','HyperlinkTextSource'):
                    nested=runs(child,a)
                    pieces.extend(nested)
                    if child.tag=='ParagraphStyleRange' and nested and not nested[-1]['text'].endswith('\n'):
                        pieces.append({'text':'\n','size':number(a.get('PointSize'),8)})
            return pieces

        story_nodes={}
        for name in z.namelist():
            if name.startswith('Stories/') and name.endswith('.xml'):
                root=xml(z.read(name))
                st=root.find('Story')
                if st is None:
                    continue
                sid=st.get('Self')
                story_nodes[sid]=st
                result['stories'][sid]={'id':sid,'path':name,'text':' '.join(e.text or '' for e in st.iter('Content'))}
        spread_names=[e.get('src') for e in design if e.tag.split('}')[-1]=='Spread' and e.get('src')]
        if not spread_names:
            spread_names=sorted(n for n in z.namelist() if n.startswith('Spreads/') and n.endswith('.xml'))
        linked_count=0
        dropped=0
        for name in spread_names:
            root=xml(z.read(name))
            spread=root.find('Spread')
            if spread is None:
                continue
            spread_pages=[]
            for node in spread.findall('Page'):
                bounds=path_box(node,matrix(node.get('ItemTransform')))
                if not bounds or bounds[2]<=0 or bounds[3]<=0:
                    continue
                p={'id':node.get('Self'),'source_label':node.get('Name',str(len(result['pages'])+1)),'label':node.get('Name',str(len(result['pages'])+1)),'title':'','width':round(bounds[2],3),'height':round(bounds[3],3),'elements':[],'source_spread':name,'original':True}
                spread_pages.append((p,bounds))
                result['pages'].append(p)

            def add_element(el,bounds):
                nonlocal dropped
                if not spread_pages:
                    return
                p,pb=max(spread_pages,key=lambda pair:overlap(bounds,pair[1]))
                if overlap(bounds,pb)<=0:
                    dropped+=1
                    return
                el['bounds']=[round(bounds[0]-pb[0],3),round(bounds[1]-pb[1],3),round(max(bounds[2],.1),3),round(max(bounds[3],.1),3)]
                el.setdefault('source',{})['spread']=name
                el['source']['page_id']=p['id']
                el['source']['original_bounds']=list(el['bounds'])
                p['elements'].append(el)

            def make_text(node,bounds):
                nonlocal linked_count
                sid=node.get('ParentStory')
                st=story_nodes.get(sid)
                if st is None:
                    return
                fid=node.get('Self')
                previous=node.get('PreviousTextFrame','n')
                nxt=node.get('NextTextFrame','n')
                linked=previous!='n' or nxt!='n'
                if linked:
                    linked_count+=1
                source={'element_id':fid,'story_id':sid,'story_path':result['stories'][sid]['path'],'previous_frame':previous,'next_frame':nxt}
                if previous!='n':
                    add_element({'id':fid,'kind':'flow-placeholder','text':'連結文章の続き（位置の確認が必要）','source':source},bounds)
                    return
                tables=list(st.iter('Table'))
                if tables:
                    offset_y=0
                    for table in tables:
                        rows=table.findall('Row')
                        cols=table.findall('Column')
                        heights=[number(r.get('SingleRowHeight'),number(r.get('MinimumHeight'),12)) for r in rows]
                        widths=[number(c.get('SingleColumnWidth'),bounds[2]/max(1,len(cols))) for c in cols]
                        for cell in table.findall('Cell'):
                            cr=cell.get('Name','').split(':')
                            if len(cr)!=2 or not all(x.isdigit() for x in cr):
                                continue
                            col,row=map(int,cr)
                            if row>=len(rows) or col>=len(cols):
                                continue
                            rs=max(1,min(int(number(cell.get('RowSpan'),1)),len(rows)-row))
                            cs=max(1,min(int(number(cell.get('ColumnSpan'),1)),len(cols)-col))
                            rr=runs(cell)
                            text=''.join(r['text'] for r in rr).rstrip('\n')
                            cb=[bounds[0]+sum(widths[:col]),bounds[1]+offset_y+sum(heights[:row]),sum(widths[col:col+cs]),sum(heights[row:row+rs])]
                            border=number(cell.get('BottomEdgeStrokeWeight'))
                            if text:
                                add_element({'id':fid+':'+cell.get('Self',cell.get('Name')),'kind':'text','text':text,'runs':rr,'font_size':next((r['size'] for r in rr if r['text'].strip()),8),'fill':colors.get(cell.get('FillColor'),'transparent'),'border_bottom':border,'padding':[number(cell.get('TextTopInset')),number(cell.get('TextRightInset')),number(cell.get('TextBottomInset')),number(cell.get('TextLeftInset'))],'source':{**source,'cell_id':cell.get('Self'),'linked':linked}},cb)
                        offset_y+=sum(heights)
                    extra_runs=runs(st)
                    extra_text=''.join(r['text'] for r in extra_runs).strip('\n')
                    if extra_text.strip():
                        add_element({'id':fid+':surrounding','kind':'text','text':extra_text,'runs':extra_runs,'font_size':8,'source':{**source,'placement_estimated':True}},bounds)
                        notes.append(f'表前後の本文（Story {sid}）を保持しました。正確な位置は要確認です。')
                else:
                    rr=runs(st)
                    text=''.join(r['text'] for r in rr).rstrip('\n')
                    if text:
                        add_element({'id':fid,'kind':'text','text':text,'runs':rr,'font_size':next((r['size'] for r in rr if r['text'].strip()),8),'source':{**source,'linked':linked}},bounds)

            def make_image(node,bounds,container):
                link=node.find('Link')
                filename=unquote((link.get('LinkResourceURI','') if link is not None else '').replace('\\','/').split('/')[-1])
                key=filename or node.get('Self')
                if key not in image_cache:
                    data=linked_files.get(filename)
                    if data is None:
                        contents=node.find('./Properties/Contents')
                        if contents is not None and contents.text:
                            try:
                                data=base64.b64decode(contents.text)
                            except ValueError:
                                pass
                    if data:
                        try:
                            asset=save_image(data,assets_dir)
                            result['assets'][asset]={'id':asset,'name':filename or '埋め込み画像','kind':'image'}
                            image_cache[key]=asset
                        except (OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):
                            image_cache[key]=None
                    else:
                        image_cache[key]=None
                asset=image_cache[key]
                add_element({'id':node.get('Self'),'kind':'image','asset_id':asset,'name':filename or '埋め込み画像','source':{'element_id':container.get('Self'),'image_id':node.get('Self'),'link_name':filename}},bounds)

            def walk(node,transform=IDENTITY):
                if node.get('Visible')=='false' or node.get('ItemLayer') in hidden_layers:
                    return
                transform=mul(transform,matrix(node.get('ItemTransform')))
                tag=node.tag.split('}')[-1]
                bounds=path_box(node,transform)
                if tag=='TextFrame' and bounds:
                    make_text(node,bounds)
                    return
                if tag in ('Rectangle','Oval','Polygon','GraphicLine') and bounds:
                    images=node.findall('Image')+node.findall('PDF')+node.findall('EPS')
                    if images:
                        for img in images:
                            make_image(img,bounds,node)
                    else:
                        fill=colors.get(node.get('FillColor'),'transparent')
                        weight=number(node.get('StrokeWeight'))
                        if fill!='transparent' or weight:
                            add_element({'id':node.get('Self'),'kind':'shape','fill':fill,'stroke':colors.get(node.get('StrokeColor'),'#333333'),'stroke_width':weight,'source':{'element_id':node.get('Self')}},bounds)
                    return
                for child in node:
                    if child.tag in ('Group','TextFrame','Rectangle','Oval','Polygon','GraphicLine'):
                        walk(child,transform)
            walk(spread)
        if not result['pages']:
            raise ValueError('IDMLに本文ページが見つかりません。')
        missing=sum(v is None for v in image_cache.values())
        if linked_count:
            notes.append(f'連結フレーム {linked_count}個：文章は先頭枠にまとめて抽出。続きの正確な位置は組版確認が必要です。')
        if missing:
            notes.append(f'画像 {missing}点を表示できません。元画像の添付を確認してください。')
        if dropped:
            notes.append(f'紙面外の要素 {dropped}個は編集画面・検索対象から除外しました。')
        notes.append('編集用HTMLは位置・表・文章を近似表示します。フォント、縦組み、マスター、回転・効果などの完全再現は行いません。')
        for p in result['pages']:
            candidates=[e for e in p['elements'] if e['kind']=='text' and e['bounds'][1]<80 and len(e['text'])>6]
            p['title']=max(candidates,key=lambda e:e.get('font_size',0))['text'][:70] if candidates else 'カタログページ'
            p['title_auto']=True
    return result
