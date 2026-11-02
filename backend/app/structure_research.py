"""Expand short menu labels before deriving competitor search queries."""
from datetime import datetime,timezone
import json,re
from sqlalchemy import select
from app import models


def word_count(value):
    return len(re.findall(r"[^\W_]+(?:['’\-][^\W_]+)*",str(value or ''),re.UNICODE))


def short_structure_label(item):
    context=item.generation_context or {}
    return bool((item.section_content_mode=='menu_page' or context.get('current_section')) and 1<=word_count(item.topic)<=3)


def expanded_topic(item,geo,language):
    saved=(item.generation_context or {}).get('article_research_topic') or {}
    if (saved.get('label')==item.topic and str(saved.get('geo')).upper()==str(geo).upper()
            and str(saved.get('language')).replace('_','-').lower()==str(language).replace('_','-').lower()
            and 5<=word_count(saved.get('topic'))<=9):
        return saved['topic']
    return None


def defer_queries(item,geo,language):
    return short_structure_label(item) and not expanded_topic(item,geo,language) and not (item.generation_context or {}).get('competitor_queries_manual')


def query_topic(item,geo,language):
    return expanded_topic(item,geo,language) or item.topic


async def prepare(db,item,task,site):
    if not short_structure_label(item) or expanded_topic(item,task.geo,task.language):
        return
    from app.services import call_gemini,extract_gemini_text,apply_provider_usage,regenerate_competitor_queries
    provider=db.get(models.AiProvider,task.ai_provider_id) if task.ai_provider_id else None
    if not provider or provider.provider_type!='gemini' or not provider.is_active or not provider.api_key:
        provider=db.scalar(select(models.AiProvider).where(models.AiProvider.provider_type=='gemini',models.AiProvider.is_active.is_(True)).order_by(models.AiProvider.updated_at.desc()))
    if not provider or not provider.api_key:
        raise ValueError('Для подготовки темы короткого пункта структуры нужен активный Gemini. Сбор конкурентов не запускался.')
    item.competitor_research_status='preparing_topic';item.competitor_research_progress=1;db.commit()
    context=item.generation_context or {}
    request={'menu_label':item.topic,'section':context.get('current_section'),'geo':task.geo,'language':task.language,'brand':getattr(site,'brand',None),'homepage_title':getattr(site,'homepage_title',None)}
    prompt=('Expand the short menu label into one precise article topic of 5–9 words, inclusive. '
            'Return only JSON {"topic":"..."}. Write in the specified project language. '
            'Preserve the exact search intent and page subject; use the section breadcrumb, GEO and brand as context. '
            'For a general-keyword site do not invent or insert an individual casino brand. '
            'Do not invent bonuses, facts, legal claims, dates, prices or a year. This topic will first be used '
            'to derive search queries for collecting competitor articles, then to write this page. '
            'Do not change the menu label or URL. Context: '+json.dumps(request,ensure_ascii=False))
    correction=''
    for attempt in range(3):
        response=await call_gemini(provider,prompt+correction)
        apply_provider_usage(provider,response.get('usageMetadata',{}));db.commit()
        try:
            text=extract_gemini_text(response).strip();text=re.sub(r'^```(?:json)?\s*|\s*```$','',text)
            parsed=json.loads(text);topic=parsed.get('topic') if isinstance(parsed,dict) else None
            if not isinstance(topic,str):raise ValueError('Нет темы статьи')
            topic=' '.join(topic.split())
            if not 5<=word_count(topic)<=9 or len(topic)>500 or re.search(r'[<>]|https?://',topic):
                raise ValueError('Тема должна содержать от 5 до 9 слов без HTML и URL')
            break
        except (ValueError,TypeError) as error:
            if attempt==2:raise ValueError('Не удалось подготовить тему из 5–9 слов; сбор конкурентов остановлен.') from error
            correction='\nPrevious response is invalid. Return valid JSON with a topic of exactly 5–9 words in the project language.'
    item.generation_context={**context,'article_research_topic':{'label':item.topic,'topic':topic,'geo':task.geo,'language':task.language,'provider_id':provider.id,'prepared_at':datetime.now(timezone.utc).isoformat()}}
    if not context.get('competitor_queries_manual'):
        regenerate_competitor_queries(db,item,task.geo,task.language)
    db.commit()
