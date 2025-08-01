import os
import time
from PIL import Image
from fpdf import FPDF
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import ocrmypdf
from PIL import Image, ImageStat

def px_to_mm(px, dpi=96):
    return px * 25.4 / dpi

# === Config ===
BASE_DIR = "/Users/namratasrinivasa/Desktop/comply-work/urltopdf"
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
HTML_DIR = os.path.join(BASE_DIR, "accordion_html")
OUTPUT_PDF = os.path.join(BASE_DIR, "output.pdf")
FINAL_PDF = os.path.join(BASE_DIR, "output_with_text.pdf")
ACCORDION_CLASSES = {"accordion", "accordian", "acc_item", "accordion_item"}

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)

# === Selenium Setup ===
options = Options()
options.headless = True
options.add_argument("--window-size=1920,3000")
driver = webdriver.Chrome(options=options)

# === Crawl all internal links ===
def get_all_internal_links(base_url):
    visited = set()
    to_visit = [base_url]
    domain = urlparse(base_url).netloc

    while to_visit:
        url = to_visit.pop()
        if url in visited:
            continue
        try:
            driver.get(url)
            time.sleep(1)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            visited.add(url)
            for link in soup.find_all("a", href=True):
                abs_url = urljoin(url, link["href"])
                if urlparse(abs_url).netloc == domain and abs_url not in visited:
                    to_visit.append(abs_url)
        except Exception as e:
            print(f"⚠️ Failed to visit {url}: {e}")
    return sorted(visited)

# === Take full screenshot of a page ===
def screenshot_page(url, output_path):
    driver.get(url)
    time.sleep(2)
    height = driver.execute_script("return document.body.scrollHeight")
    driver.set_window_size(1920, height)
    time.sleep(1)
    driver.save_screenshot(output_path)

# === Extract accordion content including collapsed text ===
def extract_accordion_html(url):
    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    found_any = any(
        tag for tag in soup.find_all(class_=lambda x: x and any(c in x for c in ACCORDION_CLASSES))
    )
    if not found_any:
        return None

    matched = []
    for tag in soup.find_all(True):
        if tag.get("class") and any(c in ACCORDION_CLASSES for c in tag.get("class")):
            style = tag.get("style", "")
            if "display:none" in style or "max-height:0" in style:
                tag["style"] = ""
            matched.append(tag)

    html_blocks = [
        f"<div style='margin-bottom:10px;padding:10px;border:1px solid #ccc;font-family:sans-serif;'>{el.decode_contents()}</div>"
        for el in matched
    ]
    full_html = f"""
    <html>
    <head>
        <style>body {{ font-family: sans-serif; padding: 20px; }}</style>
    </head>
    <body>
        <h2>Accordion Content from {url}</h2>
        {''.join(html_blocks)}
    </body>
    </html>
    """
    return full_html

def is_image_blank(img, threshold=5):
    stat = ImageStat.Stat(img.convert("L"))  # grayscale
    return stat.stddev[0] < threshold

# === Step 1: Create image-only PDF ===
def generate_image_pdf(image_paths, output_path):
    pdf = FPDF(unit='mm')
    for path in image_paths:
        img = Image.open(path)
        if is_image_blank(img):
            print(f"⚠️ Skipping blank image: {path}")
            continue
        w_px, h_px = img.size
        w_mm = px_to_mm(w_px)
        h_mm = px_to_mm(h_px)

        # Set custom page size to image size
        pdf.add_page(format=(w_mm, h_mm))
        pdf.image(path, x=0, y=0, w=w_mm, h=h_mm)
    pdf.output(output_path)

# === Step 2: Make searchable PDF ===
def apply_ocr(input_pdf, output_pdf):
    print("🔍 Running OCR...")
    ocrmypdf.ocr(input_pdf, output_pdf, language="eng", deskew=True)

# === Main ===
def main():
    base_url = input("Enter the base URL: ").strip()
    urls = get_all_internal_links(base_url)
    image_paths = []

    for i, url in enumerate(urls):
        print(f"Processing: {url}")

        shot_path = os.path.join(SCREENSHOTS_DIR, f"page_{i}_main.png")
        screenshot_page(url, shot_path)
        image_paths.append(shot_path)

        accordion_html = extract_accordion_html(url)
        if accordion_html:
            html_path = os.path.join(HTML_DIR, f"accordion_{i}.html")
            with open(html_path, "w") as f:
                f.write(accordion_html)

            driver.get("file://" + html_path)
            time.sleep(1)
            shot_acc = os.path.join(SCREENSHOTS_DIR, f"page_{i}_accordion.png")
            height = driver.execute_script("return document.body.scrollHeight")
            driver.set_window_size(1920, height)
            time.sleep(1)
            driver.save_screenshot(shot_acc)
            image_paths.append(shot_acc)
        else:
            print("→ No accordion content found.")

    generate_image_pdf(image_paths, OUTPUT_PDF)
    apply_ocr(OUTPUT_PDF, FINAL_PDF)
    print(f"\n✅ PDF with OCR saved to: {FINAL_PDF}")

if __name__ == "__main__":
    main()
    driver.quit()