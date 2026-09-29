"""Search the authorized document snapshot, keeping distinct placements."""
import re
import unicodedata


def normalize(value):
    return unicodedata.normalize('NFKC',str(value)).upper().replace('−','-').replace('‐','-').replace('－','-')


def find_occurrences(document,query,limit=200):
    query=normalize(query).strip()
    if not query or len(query)>200:
        raise ValueError('検索語は1〜200文字で入力してください。')
    pattern=re.escape(query)
    if re.fullmatch(r'[A-Z0-9-]+',query):
        pattern=r'(?<![A-Z0-9-])'+pattern+r'(?![A-Z0-9-])'
    regex=re.compile(pattern)
    results=[]
    count=0
    pages=set()
    for order,page in enumerate(document['pages']):
        if page.get('deleted'):
            continue
        for element in page['elements']:
            if element.get('deleted') or element['kind']!='text':
                continue
            text=normalize(element.get('text',''))
            for match in regex.finditer(text):
                count+=1
                pages.add(page['id'])
                if len(results)<limit:
                    source=element.get('source',{})
                    results.append({'page_id':page['id'],'page_label':page.get('label',str(order+1)),'source_label':page.get('source_label'),'order':order+1,'element_id':element['id'],'match':match.group(),'offset':match.start(),'context':text[max(0,match.start()-65):match.end()+100],'source':source,'bounds':element['bounds'],'placement_status':'位置は要確認' if source.get('linked') or source.get('placement_estimated') else '要素位置を参照'})
    return {'query':query,'occurrence_count':count,'page_count':len(pages),'results':results,'truncated':count>limit,'scope':'本文の表示対象テキスト。画像内文字・紙面外・未対応要素は含みません。','warnings':document.get('warnings',[])}
