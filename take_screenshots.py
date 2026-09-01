"""
Capture high-resolution 4K screenshots of Gmail Zenith Pro tabs.
"""

import os
from pathlib import Path
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

def capture():
    artifact_dir = Path(r"C:\Users\chkam\.gemini\antigravity-ide\brain\046e9156-e9ae-49cb-b7d5-18d90517e5b6")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=chrome_options)
    driver.get("http://127.0.0.1:8765")
    time.sleep(2)

    # 1. Overview Tab
    p1 = str(artifact_dir / "gmail_zenith_overview.png")
    driver.save_screenshot(p1)
    print(f"Saved: {p1}")

    # 2. Cleaners Tab
    btn_cleaners = driver.find_element(By.CSS_SELECTOR, "button[data-tab='cleaners']")
    btn_cleaners.click()
    time.sleep(1)
    p2 = str(artifact_dir / "gmail_zenith_cleaners.png")
    driver.save_screenshot(p2)
    print(f"Saved: {p2}")

    # 3. GitHub Triage Tab
    btn_gh = driver.find_element(By.CSS_SELECTOR, "button[data-tab='github']")
    btn_gh.click()
    time.sleep(1)
    p3 = str(artifact_dir / "gmail_zenith_github.png")
    driver.save_screenshot(p3)
    print(f"Saved: {p3}")

    # 4. Connection & Setup Tab
    btn_setup = driver.find_element(By.CSS_SELECTOR, "button[data-tab='setup']")
    btn_setup.click()
    time.sleep(1)
    p4 = str(artifact_dir / "gmail_zenith_setup.png")
    driver.save_screenshot(p4)
    print(f"Saved: {p4}")

    driver.quit()
    print("All screenshots captured successfully!")

if __name__ == "__main__":
    capture()
