"""Resolve Webdev's stale per-domain 'pending' using independent HTTPS evidence."""
from datetime import datetime, timezone
import hashlib
import html
import re
import httpx
from app import project_network as network, project_pages as pages
from app.reference_context import readable


def normalized(value):
    return ' '.join(html.unescape(value or '').split())


def content_samples(project, home):
    from app.page_word_count import page_visible_text
    definitions = {}
    for item in project.get('shortcodes') or []:
        if not isinstance(item, dict): continue
        value = item.get('data')
        if isinstance(value, dict): value = value.get('html') or value.get('code') or value.get('text')
        if isinstance(value, str): definitions[str(item.get('name') or '').removesuffix('.hbs')] = value
    samples = []
    for block in (home.get('content') or {}).get('blocks', []):
        if not isinstance(block, dict): continue
        if block.get('type') in {'paragraph', 'raw', 'code'}:
            samples.append(normalized(page_visible_text({'content': {'blocks': [block]}})))
        elif block.get('type') == 'shortcode':
            data = block.get('data') or {}
            name = data.get('shortcode') if isinstance(data, dict) else data
            markup = definitions.get(str(name or '').removesuffix('.hbs'), '')
            # Only paragraphs from a shortcode actually included in this page.
            # Unused definitions, navigation, headings and unresolved variables
            # cannot establish that the expected article was deployed.
            samples.extend(normalized(readable(match)) for match in
                           re.findall(r'<p\b[^>]*>([\s\S]*?)</p\s*>', markup, re.I))
    return [sample[:160] for sample in samples if len(sample) >= 40
            and '{{' not in sample and '}}' not in sample][:3]


def observe(db, site, operation, job):
    if operation.action not in {'create_domains', 'create_subdomains', 'delete_domain'}:return False
    result=job.get('result') or {}
    expected={d['domain'] if isinstance(d,dict) else d for d in operation.request_payload.get('domains',[])}
    if (not expected or job.get('state')!='completed' or job.get('error')
            or result.get('errorCount')!=0 or result.get('successCount')!=len(expected)):return False
    for owner in (job,result):
        domains=owner.get('domains')
        if (not isinstance(domains,list) or {d.get('domain') for d in domains}!=expected
                or any(d.get('status') not in {'pending','success','completed','deleted'}
                       or d.get('failedStage') or d.get('errorMessage') for d in domains)):return False
    try:
        with network.Remote(db,site) as remote:project=remote.project()
        state=network.observe(db,site,project)
        if not network.operation_matches(operation,state):return False
        if operation.action == 'delete_domain':
            # Webdev leaves per-domain status pending even after its successful
            # deletion job. Fresh absence plus the exact terminal job is proof;
            # HTTPS is irrelevant because this domain is about to be imported.
            operation.request_payload={**operation.request_payload,'readiness_observed':{
                'at':datetime.now(timezone.utc).isoformat(),'job_id':operation.request_payload['job_id'],
                'removal_confirmed':True,'domains':sorted(expected)}}
            operation.status='confirmed';db.commit()
            return True
        homes=[p for p in pages.pages(project) if pages.is_home(p)]
        if len(homes)!=1:return False
        home=homes[0];title=normalized(home.get('title'))
        # A matching title and a substantive excerpt reject parking/error pages.
        # TLS is validated; redirects do not count as this domain being ready.
        samples=content_samples(project,home)
        if not title or not samples:return False
        evidence=[]
        with httpx.Client(timeout=10.0,follow_redirects=False) as client:
            for domain in sorted(expected):
                response=client.get('https://'+domain+'/',headers={'Cache-Control':'no-cache'})
                if response.status_code!=200:return False
                raw=response.text
                match=re.search(r'<title\b[^>]*>([\s\S]*?)</title>',raw,re.I)
                visible=normalized(readable(raw))
                if not match or normalized(match[1])!=title or not all(s in visible for s in samples):return False
                evidence.append({'domain':domain,'status':200,'tls_verified':True,'content_matches':True,
                                 'html_sha256':hashlib.sha256(raw.encode()).hexdigest()})
    except (httpx.HTTPError,ValueError):return False
    operation.request_payload={**operation.request_payload,'readiness_observed':{
        'at':datetime.now(timezone.utc).isoformat(),'job_id':operation.request_payload['job_id'],
        'membership_confirmed':True,'domains':evidence}}
    operation.status='confirmed';db.commit()
    return True
