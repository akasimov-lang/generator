"""Project-list XLSX export. Only explicitly selected, accessible projects are included."""
import base64
from datetime import datetime, timezone
from io import BytesIO
import re
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from app import models

STATUS_LABELS = {
    'test': 'Тестовый', 'working': 'Рабочий', 'mass_actions': 'Массовые действия',
    'vitalina': 'Vitalina', 'hands_only': 'hands only', 'geo_ru': 'GEO RU',
    'geo_kz': 'GEO KZ', 'inactive': 'Неактивные', 'not_in_focus': 'Не в фокусе', 'duplicate': 'Дубликат',
}
HEADERS = ['№', 'Name WebDev', 'Бренд', 'Title главной', 'Main', 'GEO', 'Язык', 'Статус', 'Domains', 'Drops', 'NewReg', 'Поддоменов', 'Name Fibery']
MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

class ProjectTableExport(BaseModel):
    site_ids: list[str] = Field(min_length=1, max_length=10000)


def workbook(sites) -> bytes:
    rows = [HEADERS]
    for index, site in enumerate(sites, 1):
        counts = site.network_domain_counts or {}
        rows.append([index, site.name, site.brand or 'Общие ключи', site.homepage_title,
                     site.cache_canon or re.sub(r'^https?://', '', site.base_url or '').rstrip('/'),
                     site.cache_geo, site.cache_language, STATUS_LABELS.get(site.project_status, site.project_status),
                     site.domains_count, counts.get('drop'), counts.get('newreg'), counts.get('subdomains'), site.fibery_name])
    def cell(value, column, row):
        ref = f'{chr(65 + column)}{row}'
        style = '1' if row == 1 else '0'
        if value is None:
            return f'<c r="{ref}" s="{style}"/>'
        if isinstance(value, int) and not isinstance(value, bool):
            return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
        # Inline strings keep =, +, -, @ as literal text, never spreadsheet formulas.
        text = ''.join(c for c in str(value) if c in '\t\n\r' or 0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF)
        text = re.sub(r'_x[0-9a-fA-F]{4}_', lambda m: '_x005F_' + m.group()[1:], text[:32767])
        return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'
    data = ''.join(f'<row r="{r}">' + ''.join(cell(v, c, r) for c, v in enumerate(values)) + '</row>' for r, values in enumerate(rows, 1))
    cols = ''.join(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>' for i, width in enumerate([6, 32, 22, 65, 34, 12, 12, 25, 12, 12, 12, 15, 42], 1))
    sheet = f'<worksheet xmlns="{NS}"><dimension ref="A1:M{len(rows)}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{cols}</cols><sheetData>{data}</sheetData><autoFilter ref="A1:M{len(rows)}"/></worksheet>'
    styles = f'''<styleSheet xmlns="{NS}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF287657"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''
    files = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        '_rels/.rels': f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets><sheet name="Проекты" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="{REL}/styles" Target="styles.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': sheet,
        'xl/styles.xml': styles,
    }
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name, xml in files.items():
            archive.writestr(name, ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + xml).encode('utf-8'))
    return output.getvalue()


def export_table(db, user, payload):
    ids = list(dict.fromkeys(payload.site_ids))
    allowed = user.get('allowed_site_ids')
    if allowed is not None and not set(ids).issubset(set(allowed)):
        raise HTTPException(404, 'Проект недоступен для выгрузки.')
    sites = db.scalars(select(models.Site).where(models.Site.id.in_(ids), models.Site.hidden_from_projects.is_(False))).all()
    by_id = {site.id: site for site in sites}
    if len(by_id) != len(ids):
        raise HTTPException(404, 'Некоторые проекты больше недоступны. Обновите список перед выгрузкой.')
    ordered = [by_id[site_id] for site_id in ids]
    return {'filename': 'projects-' + datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S') + '.xlsx',
            'content_type': MIME, 'count': len(ordered), 'base64': base64.b64encode(workbook(ordered)).decode('ascii')}
