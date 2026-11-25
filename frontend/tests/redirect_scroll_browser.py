"""Remote Linux layout regression check; reads before/after HTML fixtures on stdin."""
import json
import sys

if sys.platform != 'linux':
    raise SystemExit('Run this check in the remote Linux browser container, never on the user Mac.')

from playwright.sync_api import sync_playwright

fixtures = json.load(sys.stdin)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page()
        page.set_viewport_size({'width': 1280, 'height': 1000})
        page.set_content(fixtures['before'])
        baseline = page.evaluate('({viewport:innerWidth,width:document.documentElement.scrollWidth})')
        assert baseline['width'] > baseline['viewport'], baseline
        print(json.dumps({'baseline_overflow_reproduced': baseline}), flush=True)
        for width in (390, 1280, 1920):
            page.set_viewport_size({'width': width, 'height': 1000})
            page.set_content(fixtures['after'])
            overflow = page.evaluate('''() => ({width:document.documentElement.scrollWidth,viewport:innerWidth,elements:[...document.querySelectorAll('main,main *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,12).map(e=>({tag:e.tagName,class:e.className,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right}))})''')
            overflow['containers']=page.locator('.redirectTables, .redirectSupportingBody, .redirectWorkspaceBody, .networkRedirects').evaluate_all('(items)=>items.map(e=>({class:e.className,client:e.clientWidth,scroll:e.scrollWidth,overflow:getComputedStyle(e).overflowX,width:getComputedStyle(e).width,position:getComputedStyle(e).position}))')
            assert overflow['width'] <= width + 1, f'Page overflows: {overflow}'
            sections = page.locator('.redirectCompactSection')
            assert sections.count() == 2
            for index in range(sections.count()):
                section = sections.nth(index)
                tables = section.locator('.redirectTables')
                header = section.locator('.networkRedirectsHeading')
                actions = section.locator('.networkActions')
                before_header = header.bounding_box()
                before_actions = actions.bounding_box()
                assert tables.evaluate('(e) => e.scrollWidth > e.clientWidth'), f'No table overflow at {width}px'
                tables.evaluate('(e) => {e.scrollLeft=e.scrollWidth;}')
                assert tables.evaluate('(e) => e.scrollLeft > 0'), 'Table cannot scroll right'
                assert header.bounding_box()['x'] == before_header['x'], 'Header shifted with table'
                assert actions.bounding_box()['x'] == before_actions['x'], 'Actions shifted with table'
                assert page.evaluate('scrollX === 0'), 'Document scrolled horizontally'
                last = tables.locator('fieldset').last.bounding_box()
                viewport = tables.bounding_box()
                assert last['x'] < viewport['x'] + viewport['width'] and last['x'] + last['width'] <= viewport['x'] + viewport['width'] + 1, 'Right edge of last column is unreachable'
                assert max(section.locator('tbody').evaluate_all('(bodies) => bodies.map(e => e.rows.length)')) <= 15
            print(json.dumps({'viewport': width, 'domain_and_page_tables': 'pass', 'document_horizontal_scroll': 0}), flush=True)
    finally:
        browser.close()
