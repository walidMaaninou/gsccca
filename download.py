import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from auth import login_to_gsccca
import json
from pathlib import Path
import os
import base64
from pathlib import Path
from PIL import Image
from fpdf import FPDF
from io import BytesIO
import pandas as pd
import streamlit as st

import base64
from pathlib import Path

import base64
from pathlib import Path
from selenium.webdriver.common.by import By
from PIL import Image
from io import BytesIO
from ocr import extract_addresses_from_pdf


def get_base64_images_as_pdf_bytes(driver) -> BytesIO:
    images = driver.find_elements(By.CSS_SELECTOR, 'img[src^="data:image/png;base64,"]')
    pil_images = []

    for img in images:
        src = img.get_attribute("src")
        if src.startswith("data:image/png;base64,"):
            b64_data = src.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_data)
            image = Image.open(BytesIO(img_bytes)).convert("RGB")
            pil_images.append(image)

    if not pil_images:
        raise ValueError("No images found.")

    # Save to in-memory PDF
    pdf_buffer = BytesIO()
    pil_images[0].save(pdf_buffer, format="PDF", save_all=True, append_images=pil_images[1:])
    pdf_buffer.seek(0)
    return pdf_buffer


def use_session_in_headless_chrome_batch(session: requests.Session, results_docs, results, table_placeholder):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import json
    import time
    import re
    from pathlib import Path

    def wait_for_download(download_path: Path, timeout=30):
        end_time = time.time() + timeout
        while time.time() < end_time:
            pdfs = list(download_path.glob("*.pdf"))
            if pdfs:
                time.sleep(1)  # ensure it's fully written
                return pdfs[0]
            time.sleep(0.5)
        raise TimeoutError("Download did not complete in time.")

    def get_doc_id(url):
        match = re.search(r"id=(\d+)", url)
        return match.group(1) if match else str(int(time.time()))

    cookies = session.cookies.get_dict()
    download_dir = Path("./downloads")
    download_dir.mkdir(parents=True, exist_ok=True)

    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--kiosk-printing')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')

    prefs = {
        "printing.print_preview_sticky_settings.appState": json.dumps({
            "recentDestinations": [{
                "id": "Save as PDF",
                "origin": "local",
                "account": "",
            }],
            "selectedDestinationId": "Save as PDF",
            "version": 2
        }),
        "savefile.default_directory": str(download_dir.resolve())
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)
    driver.get("https://www.gsccca.org")
    time.sleep(2)
    for name, value in cookies.items():
        driver.add_cookie({'name': name, 'value': value, 'domain': '.gsccca.org'})

    wait = WebDriverWait(driver, 30)
    for url in results_docs:
        doc_id = get_doc_id(url["doc_id"])
        print(f"[INFO] Processing {url["doc_id"]}")
        driver.get(url["doc_id"])

        # Wait for thumbnails (used to detect page count)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'span[id^="lvThumbnails_lblThumbHeader_"]')))
        thumbnail_elements = driver.find_elements(By.CSS_SELECTOR, 'span[id^="lvThumbnails_lblThumbHeader_"]')
        num_pages = len(thumbnail_elements)
        print(f"[INFO] Found {num_pages} pages.")

        # Start the print process
        print_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'img[title="Print"]')))
        print_button.click()

        page_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input.vtm_exportDialogNumPagesInput')))
        time.sleep(1)
        page_input.clear()
        page_input.send_keys(str(num_pages))
        existing_files = set(download_dir.glob("*.pdf"))

        ok_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'span.vtmBtn')))
        ok_button.click()
        time.sleep(2)  # Wait for images to render
        max_wait = 20
        for _ in range(max_wait * 2):  # every 0.5s
            base64_imgs = driver.find_elements(By.CSS_SELECTOR, 'img[src^="data:image/png;base64,"]')
            if len(base64_imgs) >= num_pages:
                break
            time.sleep(0.5)
        else:
            print(f"[WARN] Only found {len(base64_imgs)} base64 images, expected {num_pages}.")

        pdf_bytes_io = get_base64_images_as_pdf_bytes(driver)
        openai_key = st.secrets["OPENAI_API_KEY"]
        addresses = extract_addresses_from_pdf(pdf_bytes_io, openai_key)
        print(f"[ADDRESS] Extracted for {doc_id}: {addresses[0]}")
        results.append({
                # "Document ID": doc_id,
                "First name": url["grantee"].split(",")[0],
                "Last name": ",".join(url["grantee"].split(",")[1:]),
                "Property Address": addresses[0],
                "Property City": addresses[1],
                "Property State": addresses[2],
                "Property Zip": addresses[3]
            })

            # Convert to DataFrame and update table
        df = pd.DataFrame(results)
        table_placeholder.dataframe(df, hide_index=True)
    driver.quit()
