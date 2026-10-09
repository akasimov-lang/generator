from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from PIL import Image

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BG, FG, MUTED, BLUE, MINT = '101A2C', 'F4F7FD', 'AAB9D1', '5279FF', '32D1C6'

def box(s,x,y,w,h,color):
    sh=s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb=RGBColor.from_string(color); sh.line.fill.background()
    return sh

def txt(s,text,x,y,w,h,size=20,color=FG,bold=False):
    sh=s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf=sh.text_frame; tf.word_wrap=True
    tf.margin_left=tf.margin_right=0; tf.margin_top=tf.margin_bottom=0
    for i,line in enumerate(text.split('\n')):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.text=line; p.font.name='Arial'; p.font.size=Pt(size); p.font.bold=bold; p.font.color.rgb=RGBColor.from_string(color)
        p.space_after=Pt(8)
    return sh

def slide(n,kicker,title,subtitle,source):
    s=prs.slides.add_slide(prs.slide_layouts[6]); s.background.fill.solid(); s.background.fill.fore_color.rgb=RGBColor.from_string(BG)
    box(s,.45,.42,.09,.24,MINT)
    txt(s,'PAGEPILOT  /  '+kicker,.68,.4,11,.3,11,MUTED,True)
    txt(s,title,.65,.98,12,1,34,FG,True)
    txt(s,subtitle,.68,1.85,12,.58,16,MUTED)
    box(s,.65,7.02,12,.008,'2B3850')
    txt(s,'Возможности системы • 09.10.2026',.68,7.15,6,.2,9,MUTED)
    txt(s,f'{n:02d} / 06',11.85,7.12,.8,.25,11,MINT,True)
    s.notes_slide.notes_text_frame.text=source
    return s

def metric(s,num,label,x,y,w=3.5,size=56):
    txt(s,num,x,y,w,.88,size,MINT,True)
    txt(s,label,x,y+.98,w,.8,18,FG)

def shot(s,path,x,y,w,h,caption,top=True):
    # Use the original screenshot, cropping only its viewport in the slide frame.
    iw,ih=Image.open(path).size; target=w/h; ratio=iw/ih
    pic=s.shapes.add_picture(str(path),Inches(x),Inches(y),width=Inches(w),height=Inches(h))
    if ratio<target:
        cut=1-ratio/target
        pic.crop_top=0 if top else cut/2; pic.crop_bottom=cut if top else cut/2
    else:
        cut=1-target/ratio; pic.crop_left=cut/2; pic.crop_right=cut/2
    txt(s,caption,x,y+h+.1,w,.45,10,MUTED)

s=slide(1,'ОБЗОР','SEO-контент: от задачи до публикации','Генерация, проверка, публикация и управление проектом в одном интерфейсе.',
    'Источники: README.md; frontend/src/UserGuide.tsx (start, generation, publication). 4 — этапы рабочего процесса, а не количество модулей. Скриншот: design/pagepilot/workspace-light.png, сохранённое локальное превью; цифры внутри окна — демонстрационные данные, не метрики эксплуатации.')
metric(s,'4','этапа работы с контентом',.7,2.7)
txt(s,'01  Задать параметры\n02  Сгенерировать текст\n03  Проверить и принять\n04  Опубликовать',.73,4.55,3.7,2,20)
shot(s,ROOT/'design/pagepilot/workspace-light.png',4.5,2.7,8.1,3.95,'Рабочий экран • сохранённое локальное превью')

s=slide(2,'ЛОКАЛИЗАЦИЯ','Контент для разных рынков','ГЕО, язык и бренд задаются при создании шаблона.',
    'Источники: frontend/src/templateLocaleOptions.ts: массив codes содержит 249 уникальных кодов стран и территорий. frontend/src/languageOptions.ts: базовый LANGUAGE_OPTIONS содержит 76 записей; генератор дополняет список языками для ГЕО. Это размеры справочников, не гарантия качества на каждом языке. Скриншот снят с локальной сборки frontend/dist с подменёнными API-ответами без обращения к рабочим данным.')
metric(s,'249','ГЕО: страны и территории',.7,2.6)
metric(s,'76','языков в базовом справочнике',.7,4.55)
shot(s,OUT/'template-window.png',4.5,2.65,8.1,3.95,'Окно создания шаблона • демонстрационный режим')

s=slide(3,'ИССЛЕДОВАНИЕ','Поиск фактов перед генерацией','При включённом сборе конкурентов система исследует источники через DataForSEO.',
    'Источники: README.md, раздел «Редакционный скилл генерации»; backend/app/factual_research.py. До 10 логических SERP-запросов на статью: до 5 конкуренты и до 5 уточнение фактов, без транспортных повторов. До 2 раундов уточнения. Gemini URL Context анализирует до 10 исходных URL конкурентов; это отдельный лимит. Лимиты не являются гарантией полноты или достоверности фактов.')
for x in [.7,4.9,9.1]: box(s,x,2.75,3.55,2.55,'192740')
metric(s,'10','запросов на статью — максимум',.93,2.95,3.05)
metric(s,'5 + 5','конкуренты + уточнение фактов',5.13,2.95,3.05,48)
metric(s,'2','раунда уточнения — максимум',9.33,2.95,3.05)
txt(s,'Запросы → источники → выдержки → журнал проверки',.8,5.78,11.7,.55,23,FG,True)
txt(s,'Неподтверждённые существенные утверждения отмечаются для редактора.',.8,6.36,11.7,.4,15,MUTED)

s=slide(4,'ГЕНЕРАТОР ШАБЛОНОВ','Дизайн с проверкой повторов','HTML-одностраничник, контент, меню и отчёт проверок — в одном архиве.',
    'Источники: README.md «Генератор шаблона»; backend/app/template_design.py; backend/app/site_templates.py. Протокол сравнивает 15 семейств дизайна; до 3 попыток. Chromium проверяет ширины 1440, 390, 320 px. Проверка моделью — эвристика, не гарантия уникальности. Скриншот — форма генератора из локальной сборки с демонстрационными API-ответами. Генерация в рамках создания презентации не запускалась.')
shot(s,OUT/'template-window.png',.7,2.7,7.5,3.5,'Окно генератора • демонстрационный режим')
metric(s,'15','семейств дизайна для сравнения',8.65,2.65,3.8)
metric(s,'3','попытки дизайна — максимум',8.65,4.48,3.8)
txt(s,'3 ширины проверки: 1440 / 390 / 320 px',.78,6.65,10,.25,13,MINT,True)

s=slide(5,'ПУБЛИКАЦИЯ','Сразу или по расписанию','Приёмка материалов, очередь и подтверждение результата.',
    'Источники: frontend/src/UserGuide.tsx, publication. 2 способа запуска: ручная публикация и кампания. 6 разделов вкладки: Кампании, Контент, Процесс, Очередь, Ошибки, Удалённые. «Публикуется» и «Ожидает проверки» не означают завершение. Скриншот: реальное окно встроенной инструкции, локальная сборка с демо-авторизацией.')
metric(s,'2','способа публикации',.7,2.65)
txt(s,'Вручную\nПо расписанию кампании',.75,4.45,3.7,1,20)
txt(s,'6 разделов контроля\nот очереди до ошибок',.75,5.75,3.7,.85,18,MINT,True)
shot(s,OUT/'publication-window.png',4.5,2.7,8.1,3.95,'Окно встроенной инструкции по публикации')

s=slide(6,'УПРАВЛЕНИЕ ПРОЕКТОМ','Домены под контролем','Сетка проекта, смена основного домена и автоматизация переклея.',
    'Источники: frontend/src/UserGuide.tsx; frontend/src/ProjectNetworkPanel.tsx; frontend/src/AutoRegluePanel.tsx; design/pagepilot/README.md. 3 — перечисленные направления работы с доменами: сетка, переклей, автопереклей. 2 темы: светлая/тёмная. Скриншот: сохранённое локальное превью design/pagepilot/workspace-dark.png, не текущая статистика production. Все числа презентации описывают функции/лимиты; показатели трафика, экономии и производительности не измерялись.')
metric(s,'3','направления работы с доменами',.7,2.65)
txt(s,'Сетка и резерв\nРучной переклей\nАвтопереклей',.75,4.5,3.7,1.6,20)
txt(s,'2 темы: светлая и тёмная',.75,6.35,4,.4,15,MINT,True)
shot(s,ROOT/'design/pagepilot/workspace-dark.png',4.5,2.7,8.1,3.95,'Рабочий экран в тёмной теме • локальное превью')

prs.core_properties.title='PagePilot — возможности в цифрах'
prs.core_properties.subject='Краткая презентация системы со скриншотами интерфейса'
prs.core_properties.author='PagePilot'
prs.save(OUT/'PagePilot.pptx')
print('Created',OUT/'PagePilot.pptx')
