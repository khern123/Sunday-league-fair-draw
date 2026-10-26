from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'slides'/'qa'; OUT.mkdir(exist_ok=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(); page=browser.new_page(viewport={'width':1280,'height':720})
    page.goto('http://127.0.0.1:8765/slides.html', wait_until='networkidle'); page.wait_for_timeout(1200)
    images=[]
    for i in range(10):
        page.evaluate(f"Reveal.slide({i})"); page.wait_for_timeout(180)
        path=OUT/f'slide-{i+1:02d}.png'; page.screenshot(path=str(path)); images.append(Image.open(path).convert('RGB'))
    browser.close()
thumbs=[]
for index, image in enumerate(images,1):
    image.thumbnail((480,270)); card=Image.new('RGB',(500,310),'white'); card.paste(image,(10,28)); ImageDraw.Draw(card).text((14,8),f'Slide {index}',fill='#0b1e4a'); thumbs.append(card)
sheet=Image.new('RGB',(1000,1550),'#eaf4ff')
for i,thumb in enumerate(thumbs): sheet.paste(thumb,((i%2)*500,(i//2)*310))
sheet.save(OUT/'slides_contact_sheet.png')
print(f'Captured {len(images)} slides to {OUT}; contact sheet: {OUT/"slides_contact_sheet.png"}')
