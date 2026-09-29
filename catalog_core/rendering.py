from html import escape


PAGE_CSS='''body{font-family:"Yu Gothic UI",Meiryo,sans-serif;background:#edf0f2;color:#1c3039;margin:24px}h1{font-size:24px}a{color:#07695b}.paper{position:relative;background:white;color:#202020;margin:20px auto;box-shadow:0 3px 16px #0002;overflow:hidden}.element{position:absolute;box-sizing:border-box;overflow:hidden}.text{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.18;font-family:"Yu Gothic",Meiryo,sans-serif}.element img{width:100%;height:100%;object-fit:contain}.reference{position:absolute;inset:0;width:100%;height:100%}.deleted-mark{border:2px dashed #b94242;background:#fff9;color:#9b2525}.instructions{max-width:960px;margin:auto;background:white;padding:28px}table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #ccd6d8;padding:9px;text-align:left;vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere}small{color:#586970}pre{white-space:pre-wrap;overflow-wrap:anywhere}.badge{background:#e5f4ee;padding:3px 8px;border-radius:4px}@media print{body{background:white;margin:0}.paper{box-shadow:none;page-break-after:always}.instructions{padding:0}a{color:inherit}}'''


def element_html(el,asset_prefix='assets/',reference=False):
    if el.get('deleted'):
        return ''
    x,y,w,h=el['bounds']
    style=f'left:{x}px;top:{y}px;width:{w}px;height:{h}px;'
    kind=el['kind']
    body=''
    if kind=='text':
        if reference and not el.get('modified'): return ''
        style+=f'font-size:{el.get("font_size",8)}px;'
        style+='background:'+ ('#ffffff' if el.get('modified') else escape(el.get('fill','transparent'),quote=True))+';'
        if el.get('padding'): style+='padding:'+' '.join(str(v)+'px' for v in el['padding'])+';'
        if el.get('border_bottom'):style+=f'border-bottom:{el["border_bottom"]}px solid #333;'
        if el.get('runs') and not el.get('modified'):
            body=''.join(f'<span style="font-size:{r.get("size",8)}px;color:{escape(r.get("color","#202020"),quote=True)};font-weight:{700 if r.get("bold") else 400}">{escape(r["text"])}</span>' for r in el['runs'])
        else: body=escape(el.get('text',''))
    elif kind=='image':
        if reference and not el.get('modified'): return ''
        aid=el.get('asset_id')
        body=f'<img src="{escape(asset_prefix+aid,quote=True)}" alt="{escape(el.get("name","画像"),quote=True)}">' if aid else '<small>画像未解決</small>'
    elif kind=='shape':
        if reference:return ''
        style+=f'background:{escape(el.get("fill","transparent"),quote=True)};border:{el.get("stroke_width",0)}px solid {escape(el.get("stroke","#333333"),quote=True)};'
    else:
        if reference:return ''
        body='<small>連結先は要確認</small>';style+='border:1px dashed #d69526;font-size:9px;'
    return f'<div class="element {escape(kind)}" data-element-id="{escape(el["id"],quote=True)}" style="{style}">{body}</div>'


def page_html(page,asset_prefix='../assets/',reference=False):
    body=''
    if reference and page.get('reference_asset'):
        body=f'<img class="reference" src="{escape(asset_prefix+page["reference_asset"],quote=True)}" alt="原版PDF">'
    else: reference=False
    def mask(bounds):
        x,y,w,h=bounds
        return f'<div class="element" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:white"></div>'
    if reference:
        for region in page.get('removed_regions',[]):body+=mask(region['bounds'])
    for e in page['elements']:
        source=e.get('source',{})
        if reference and (e.get('modified') or e.get('deleted')) and source.get('page_id')==page['id'] and source.get('original_bounds') and source['original_bounds']!=e['bounds']:
            body+=mask(source['original_bounds'])
        if reference and e.get('deleted'):
            x,y,w,h=e['bounds'];body+=f'<div class="element deleted-mark" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">削除指示</div>'
        else: body+=element_html(e,asset_prefix,reference)
    return f'<!doctype html><html lang="ja"><meta charset="utf-8"><title>{escape(page["title"])}</title><style>{PAGE_CSS}</style><h1>{escape(page["title"])} · p.{escape(str(page["label"]))}</h1><p>編集用の配置案です。最終的な組版は制作側で確認してください。</p><div class="paper" style="width:{page["width"]}px;height:{page["height"]}px">{body}</div></html>'
