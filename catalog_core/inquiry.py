"""Read-only question intents over authorized catalog evidence; no external AI."""
import re
from .products import MODEL,report
from .search import normalize,find_occurrences

EXAMPLES=['全ての型番と価格を一覧にして','RX-359NBの価格を教えて','ERD9717WAは何か所使われていますか']

def understood_words(q,models,words):
    rest=q
    for model in models:rest=rest.replace(model,'')
    tokens=sorted(words.split('|'),key=len,reverse=True)
    rest=re.sub('|'.join(map(re.escape,tokens)),'',rest)
    return not re.sub(r'[\s、。，,.?!？！「」『』:：]','',rest)

COMMON='カタログ|データ|商品|製品|型番|情報|全て|すべて|全部|全|この|現在|お願いします|お願い|ください|下さい|ほしい|欲しい|して|する|した|します|できますか|ですか|です|ます|か|の|と|が|を|は|に|で|も'
PRICE_WORDS=COMMON+'|価格|金額|値段|単価|いくら|一覧化|一覧|リスト|まとめて|まとめ|表|紐づいた|紐付いた|紐付いている|紐づいている|紐づけ|紐付け|ひもづいた|対応した|確認済み|確認済|教えて|教え|知りたい|知り|調べて|調べ|見せて|表示|出して|のみ|だけ'
LOCATION_WORDS=COMMON+'|どこ|何か所|何箇所|何ヶ所|何ケ所|何件|何回|掲載されています|掲載されている|掲載|使われています|使われている|使っている|使って|場所|件数|教えて|知りたい|調べて|ある|あります|いる'

def answer(state,query,allow_products=True):
    if not isinstance(query,str) or not query.strip() or len(query)>200:raise ValueError('質問・検索語は1〜200文字で入力してください。')
    q=normalize(query).strip();models=list(dict.fromkeys(MODEL.findall(q)))
    def unsupported(message='この質問はまだ解釈できません。型番と価格の一覧、特定型番の価格、掲載場所・件数を調べられます。'):
        return {'kind':'unsupported','query':query,'message':message,'examples':EXAMPLES}
    # Do not silently discard filters, comparisons, time periods or write requests.
    if re.search('以上|以下|未満|より高|より安|最安|最高|平均|合計|去年|昨年|来年|昨年度|年度|削除|変更して|書き換|更新して|安い順|高い順|比較',q):
        return unsupported('価格条件・比較・期間指定・データ更新の依頼にはまだ対応していません。条件を外した一覧は表示できます。')
    price_request=bool(re.search('価格|金額|値段|単価|いくら',q))
    list_request=bool(re.search('一覧|リスト|一覧化|まとめ|全て|すべて|全部|表に',q))
    if price_request and (list_request or models or re.search('教え|知り|調べ',q)) or list_request and re.search('型番|商品',q):
        if not understood_words(q,models,PRICE_WORDS):return unsupported('指定された条件を正確に解釈できません。全型番または特定型番の価格一覧、確認済みだけの一覧に対応しています。除外・ページ指定・価格区分などの条件はまだ対応していません。')
        if not allow_products:return {'kind':'restricted','query':query,'message':'未確認の価格候補を含む一覧は、販促・開発部門で確認できます。社内閲覧では型番・キーワードの掲載検索をご利用ください。'}
        product_report=report(state);rows=[]
        confirmed_only='確認済' in q
        for o in product_report['occurrences']:
            if o['status']=='ignored' or (models and o['model'] not in models):continue
            r=o.get('review') or {};confirmed=o['status']=='confirmed' and r.get('price_state')=='confirmed'
            if confirmed_only and not confirmed:continue
            selected={p['id']:p['kind'] for p in r.get('prices',[])} if confirmed else {}
            rows.append({**o,'confirmed':confirmed,'prices':[{**p,'kind':selected.get(p['id'],p['kind'])} for p in o['price_candidates'] if p['id'] in selected] if confirmed else o['price_candidates']})
        return {'kind':'prices','query':query,'message':('確認済みの価格だけを一覧にしました。' if confirmed_only else '型番と価格を掲載箇所ごとに一覧にしました。未確認の対応は候補として分けて表示します。'),'rows':rows,'model_count':len({r['model'] for r in rows}),'occurrence_count':len(rows),'confirmed_only':confirmed_only,'scope':product_report['scope']}
    if models and re.search('どこ|何[か箇ヶケ]所|何件|何回|掲載|使われ|使って|場所',q):
        if not understood_words(q,models,LOCATION_WORDS):return unsupported('掲載場所・件数は型番を1つ指定してください。除外やページなどの追加条件はまだ対応していません。')
        if len(models)!=1:return unsupported('掲載場所・件数は、型番を1つずつ指定してください。')
        return {'kind':'locations','query':query,'search':find_occurrences(state['document'],models[0])}
    if re.search('ください|教えて|ですか|ますか|[?？]|一覧|なぜ|どう|して$',q):return unsupported()
    return {'kind':'keyword','query':query,'search':find_occurrences(state['document'],query)}

def inquiry_csv(result):
    from .exports import csv_bytes,search_csv
    if result['kind'] in ('keyword','locations'):return search_csv({**result['search'],'revision':result['revision']})
    if result['kind']!='prices':raise ValueError('一覧が返る質問で出力してください。')
    rows=[['型番候補','ページ','掲載順','型番の文字枠','対応状態','価格（円）','価格区分','根拠','価格の文字枠','価格の原文','質問','版']]
    labels={'same_frame':'同じ文字枠・未確認','manual_group':'同じ商品ブロック・未確認','nearby':'位置からの候補・未確認'}
    for o in result['rows']:
        for p in o['prices'] or [{}]:
            rows.append([o['model'],o['page_label'],o['order'],o['element_id'],'確認済み' if o['confirmed'] else '再確認' if o['status']=='recheck' else '未確認',p.get('amount',''),{'body':'本体','set':'セット','list':'定価','unspecified':'区分未確認'}.get(p.get('kind'),''),'人が対応を確認' if o['confirmed'] else labels.get(p.get('relation'),'価格未抽出'),p.get('element_id',''),p.get('context',''),result['query'],result['revision']])
    return csv_bytes(rows)
