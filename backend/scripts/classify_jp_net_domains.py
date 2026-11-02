"""Apply the requested jp.net registration classification to saved local types."""
import argparse
import json
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Site
from app.domain_classification import registrable_root
from app.network_state import domain_name


def corrected_types(site):
    types=dict(site.domain_types or {})
    names=[*(site.cache_domains or []),*types,site.name,site.cache_canon,
           *(site.main_domain_history or []),*(site.alternate_domain_history or []),*(site.x_default_history or [])]
    roots={registrable_root(domain_name(name).removeprefix('www.')) for name in names if name}
    roots={root for root in roots if root and root.endswith('.jp.net')}
    changes=[]
    for root in sorted(roots):
        aliases=[root,'www.'+root]
        if any(types.get(alias)=='amp' for alias in aliases):
            continue
        for alias in aliases:
            if alias==root or alias in types:
                if types.get(alias)!='newreg':
                    changes.append({'domain':alias,'before':types.get(alias),'after':'newreg'})
                    types[alias]='newreg'
    return types,changes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    report=[]
    with SessionLocal() as db:
        query=select(Site).order_by(Site.id)
        if args.apply:query=query.with_for_update()
        for site in db.scalars(query):
            types,changes=corrected_types(site)
            if changes:
                report.append({'site_id':site.id,'project':site.name,'changes':changes})
                if args.apply:site.domain_types=types
        if args.apply:db.commit()
    print(json.dumps({'applied':args.apply,'projects':len(report),'types_updated':sum(len(item['changes']) for item in report),'changes':report},ensure_ascii=False))


if __name__=='__main__':main()
