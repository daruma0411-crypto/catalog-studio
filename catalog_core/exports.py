import csv
import io
import json
import zipfile
from html import escape

from .operations import now
from .rendering import PAGE_CSS,page_html


def csv_bytes(rows):
    stream=io.StringIO(newline='')
    writer=csv.writer(stream)
    for row in rows:
        values=[]
        for v in row:
            value=str(v if v is not None else '')
            if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')): value="'"+value
            values.append(value)
        writer.writerow(values)
    return stream.getvalue().encode('utf-8-sig')


def search_csv(result):
    rows=[['型番・検索語','掲載ページ','掲載順','要素ID','原文周辺','元Story','版']]
    rows.extend([result['query'],r['page_label'],r['order'],r['element_id'],r['context'],r['source'].get('story_id',''),result['revision']] for r in result['results'])
    return csv_bytes(rows)


def instruction_package(service,cid,actor):
    if actor.role!='editor': raise PermissionError('制作指示の出力は販促担当が行います。')
    state=service.get_catalog(cid,actor)
    original=service.original_document(cid,actor)
    manifest={'catalog_id':cid,'title':state['title'],'revision':state['version'],'created':now(),'source_hash':state['document']['source_hash'],'unresolved_threads':sum(t['status']=='open' for t in state['threads']),'layout_notice':'HTMLは編集用の配置案。InDesignの最終組版とは異なります。','import_warnings':state['document'].get('warnings',[])}
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        z.writestr('instructions.json',json.dumps({**manifest,'changes':state['changes'],'threads':state['threads'],'submissions':state['submissions']},ensure_ascii=False,indent=2))
        rows=[['番号','操作','ページ','要素','変更前','変更後','理由','状態','日時']]
        for i,c in enumerate(state['changes'],1):
            def summary(v):
                if isinstance(v,dict): return v.get('text') or json.dumps(v,ensure_ascii=False)
                return str(v or '')
            rows.append([i,c['type'],c.get('page_label',''),c.get('element_id',''),summary(c.get('before')),summary(c.get('after')),c.get('reason',''),c['status'],c['created']])
        z.writestr('instructions.csv',csv_bytes(rows))
        body=f'<h1>制作への指示原稿</h1><p>{escape(state["title"])} · 版 {state["version"]}</p><p>未解決の確認事項：{manifest["unresolved_threads"]}件。保留事項と確定指示を分けて確認してください。</p>'
        body+='<h2>紙面</h2><ul>'
        for i,p in enumerate(state['document']['pages'],1):
            z.writestr(f'pages/edited-{i}.html',page_html(p,reference=True))
            z.writestr(f'pages/structured-{i}.html',page_html(p,reference=False))
            body+=f'<li>掲載順{i} · {escape(p["title"])}：<a href="pages/edited-{i}.html">原版＋変更指示</a> / <a href="pages/structured-{i}.html">編集用HTML</a></li>'
        for i,p in enumerate(original['pages'],1):
            z.writestr(f'pages/original-{i}.html',page_html(p,reference=True))
        body+='</ul><h2>変更一覧</h2><table><thead><tr>'+''.join(f'<th>{escape(h)}</th>' for h in ['番号','操作','変更前','変更後','理由'])+'</tr></thead><tbody>'
        for row in rows[1:]:
            body+='<tr>'+''.join(f'<td>{escape(str(row[i]))}</td>' for i in [0,1,4,5,6])+'</tr>'
        body+='</tbody></table><h2>コメント・確認事項</h2>'
        for t in state['threads']:
            body+=f'<h3>{escape(t["destination"])} · {escape(t["status"])} · {escape(t.get("element_id") or "全体")}</h3>'
            for m in t['messages']:body+=f'<p><strong>{escape(m["author"])}</strong>：{escape(m["text"])}</p>'
        body+='<h2>添付原稿・素材</h2><ul>'
        assets={**original['assets'],**state['document']['assets']}
        for a in state['attachments']:
            assets[a['id']]=a
            body+=f'<li><a href="assets/{escape(a["id"],quote=True)}">{escape(a["name"])}</a></li>'
        body+='</ul>'
        for aid in assets:
            path=service.assets_dir/aid
            if not path.is_file():raise ValueError('必要な素材が見つかりません。再アップロードしてください：'+assets[aid].get('name',aid))
            z.write(path,'assets/'+aid)
            if assets[aid].get('kind')=='source-image':
                for name in assets[aid].get('link_names',[assets[aid]['name']]):z.write(path,'source/Links/'+name)
        source=service.sources_dir/(cid+'.idml')
        if not source.is_file():raise ValueError('元IDMLが見つかりません。元パッケージを再取り込みしてください。')
        z.write(source,'source/original.idml')
        z.writestr('instructions.html',f'<!doctype html><html lang="ja"><meta charset="utf-8"><title>制作指示原稿</title><style>{PAGE_CSS}</style><main class="instructions">{body}</main></html>')
        z.writestr('README.txt','instructions.htmlをブラウザで開いてください。印刷またはPDF保存もできます。\n原版IDMLはsource/original.idmlです。自動修正したIDMLではありません。\n')
    return out.getvalue()


def released_package(service,cid,actor):
    state=service.get_catalog(cid,actor)
    # This export is always scoped to the reader's published snapshot.
    from .service import Actor
    state=service.get_catalog(cid,Actor(actor.id,actor.name,'reader'))
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for i,p in enumerate(state['document']['pages'],1):z.writestr(f'pages/page-{i}.html',page_html(p))
        for aid in state['document']['assets']:
            path=service.asset_path(cid,Actor(actor.id,actor.name,'reader'),aid)
            z.write(path,'assets/'+aid)
        z.writestr('catalog.json',json.dumps(state,ensure_ascii=False,indent=2))
    return out.getvalue()
