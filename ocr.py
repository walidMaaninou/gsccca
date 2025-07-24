import os
import ast
import time
import pytesseract
from pdf2image import convert_from_path, convert_from_bytes
from openai import OpenAI
from pathlib import Path
from io import BytesIO
from typing import Union

def extract_addresses_from_pdf(pdf_input: Union[str, Path, BytesIO], openai_api_key: str) -> list[str]:
    client = OpenAI(api_key=openai_api_key)

    t0 = time.time()
    print("[STEP] Starting PDF to image conversion...")

    try:
        if isinstance(pdf_input, (str, Path)):
            images = convert_from_path(pdf_input)
        elif isinstance(pdf_input, BytesIO):
            pdf_bytes = pdf_input.read()
            print(f"[DEBUG] PDF size in memory: {len(pdf_bytes)} bytes")
            images = convert_from_bytes(pdf_bytes, dpi=30)
        else:
            return ["Invalid input type. Must be path or BytesIO."]
    except Exception as e:
        return [f"OCR failed during PDF conversion: {e}"]

    print(f"[STEP] PDF to image conversion done in {time.time() - t0:.2f}s — {len(images)} pages detected.")

    # OCR
    t1 = time.time()
    print("[STEP] Starting OCR on images...")

    full_text = ""
    for i, img in enumerate(images):
        page_t0 = time.time()
        page_text = pytesseract.image_to_string(img)
        full_text += f"--- Page {i + 1} ---\n{page_text.strip()}\n\n"
        print(f"[DEBUG] OCR page {i + 1} took {time.time() - page_t0:.2f}s")

    print(f"[STEP] OCR completed in {time.time() - t1:.2f}s.")

    if not full_text.strip():
        return ["⚠️ No text detected in PDF."]

    # Prompt
    t2 = time.time()
    print("[STEP] Sending prompt to OpenAI...")

    prompt = f"""
From the text below, extract the **single most likely physical mailing address** (property address).
Output only a **Python list containing one string**, with no explanation:

\"\"\"{full_text[:3000]}\"\"\"
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        result = response.choices[0].message.content
        print(f"[STEP] OpenAI call done in {time.time() - t2:.2f}s.")
        return ast.literal_eval(result.strip())
    except Exception as e:
        return [f"OpenAI error: {e}"]
