#!/usr/bin/env python3
"""
Reconnaissance script to analyze the actual page structure
"""

import time
import json
from dotenv import load_dotenv
import os
import re
import html as html_lib
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from sqlite_store import SQLiteStore
from good_turing import GoodTuringEstimator
import hashlib
from datetime import datetime
import threading
import math

# Load environment variables
load_dotenv()

# Configuration
BRAVE_PATH = "/usr/bin/brave-browser"
DRIVER_PATH = "./chromedriver-linux64/chromedriver"
LOGIN_URL = "https://selftest.mededtech.ru/login.jsp"

# Output / persistence toggles via environment
USE_SQLITE = os.getenv("USE_SQLITE", "0") == "1"
SQLITE_PATH = os.getenv("SQLITE_PATH", "mcq.db")
SET_LABEL = os.getenv("SET_LABEL")
ADDITIONAL_SETS = int(os.getenv("ADDITIONAL_SETS", os.getenv("QUIZ_LOOPS", "2")))

def _bool_env(var_name, default=False):
    v = os.getenv(var_name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y"}

def setup_driver():
    """Setup and configure the Chrome driver"""
    chrome_options = Options()
    chrome_options.binary_location = BRAVE_PATH
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    # Enable performance logging for network/XHR reconnaissance
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    service = Service(executable_path=DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def login_and_navigate_to_results(driver):
    """Login and navigate directly to results page"""
    print("🔐 Logging in...")
    driver.get(LOGIN_URL)
    time.sleep(2)
    
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.XPATH, "//input[@type='submit']").click()
    time.sleep(3)
    
    print("✅ Login successful")
    
    # Navigate to testing
    print("🧪 Navigating to testing...")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//div[text()='Тестирование']"))).click()
    time.sleep(2)
    
    # Try to dismiss any popups first
    try:
        popup = driver.find_element(By.XPATH, "//div[contains(@class, 'gwt-PopupPanelGlass')]")
        if popup.is_displayed():
            print("🔄 Dismissing popup...")
            driver.execute_script("arguments[0].style.display = 'none';", popup)
            time.sleep(1)
    except:
        pass
    
    wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Пройти тестирование']"))).click()
    time.sleep(2)
    
    # Click on test
    print("🎯 Clicking on test...")
    test_xpath = "//span[@class='extraSpace' and contains(text(), 'РЭ_Лечебное дело, 2025')]"
    test_element = driver.find_element(By.XPATH, test_xpath)
    test_element.click()
    time.sleep(3)
    
    # Switch to new window
    original_window = driver.current_window_handle
    wait.until(EC.number_of_windows_to_be(2))
    all_windows = driver.window_handles
    new_window = None
    for window_handle in all_windows:
        if window_handle != original_window:
            new_window = window_handle
            break
    
    if new_window:
        driver.switch_to.window(new_window)
        time.sleep(5)
    
    # Click "Go to first question"
    print("🎯 Clicking 'Go to first question'...")
    wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Перейти к первому вопросу')]"))).click()
    time.sleep(3)
    
    # Complete test immediately to get to results
    print("🚪 Completing test to reach results...")
    try:
        complete_button = driver.find_element(By.XPATH, "//span[contains(text(), 'Завершить тестирование')]")
        complete_button.click()
        time.sleep(2)
        
        # Handle confirmation dialog
        try:
            complete_anyway = driver.find_element(By.XPATH, "//*[contains(text(), 'Все равно завершить')]")
            complete_anyway.click()
            time.sleep(5)
        except:
            pass
    except:
        pass
    
    print("✅ Reached results page")
    return driver

def comprehensive_page_analysis(driver):
    """Comprehensive analysis of the current page"""
    print("\n🔍 COMPREHENSIVE PAGE ANALYSIS")
    print("=" * 50)
    
    try:
        # Basic page info
        current_url = driver.current_url
        page_title = driver.title
        page_source_length = len(driver.page_source)
        
        print(f"📍 URL: {current_url}")
        print(f"📄 Title: {page_title}")
        print(f"📄 Page source length: {page_source_length} characters")
        
        # Get all tables
        tables = driver.find_elements(By.TAG_NAME, "table")
        print(f"\n📊 Found {len(tables)} tables")
        
        for i, table in enumerate(tables):
            try:
                table_text = table.text.strip()
                table_class = table.get_attribute('class') or 'No class'
                print(f"  Table {i+1}: {len(table_text)} chars, class: {table_class}")
                if len(table_text) > 0:
                    print(f"    Preview: {table_text[:100]}...")
            except:
                print(f"  Table {i+1}: Error reading table")
        
        # Get all divs with classes
        divs = driver.find_elements(By.XPATH, "//div[@class]")
        print(f"\n📦 Found {len(divs)} divs with classes")
        
        class_counts = {}
        for div in divs:
            try:
                class_name = div.get_attribute('class')
                if class_name:
                    class_counts[class_name] = class_counts.get(class_name, 0) + 1
            except:
                pass
        
        # Show most common classes
        sorted_classes = sorted(class_counts.items(), key=lambda x: x[1], reverse=True)
        print("  Most common classes:")
        for class_name, count in sorted_classes[:10]:
            print(f"    {class_name}: {count}")
        
        # Look for question-related elements
        print(f"\n🧪 Looking for question-related elements...")
        
        # All elements containing "Вопрос"
        question_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Вопрос')]")
        print(f"  Elements containing 'Вопрос': {len(question_elements)}")
        
        for i, elem in enumerate(question_elements[:5]):
            try:
                text = elem.text.strip()
                tag = elem.tag_name
                classes = elem.get_attribute('class') or 'No class'
                print(f"    {i+1}. '{text[:50]}...' (tag: {tag}, class: {classes})")
            except:
                pass
        
        # All clickable elements
        clickable_elements = driver.find_elements(By.XPATH, "//*[@onclick or @href or contains(@class, 'clickable') or contains(@class, 'button')]")
        print(f"\n🖱️  Found {len(clickable_elements)} potentially clickable elements")
        
        for i, elem in enumerate(clickable_elements[:10]):
            try:
                text = elem.text.strip()
                tag = elem.tag_name
                classes = elem.get_attribute('class') or 'No class'
                onclick = elem.get_attribute('onclick') or 'No onclick'
                if text or classes != 'No class':
                    print(f"    {i+1}. '{text[:30]}...' (tag: {tag}, class: {classes}, onclick: {onclick[:30]}...)")
            except:
                pass
        
        # Look for specific patterns
        print(f"\n🔍 Looking for specific patterns...")
        
        patterns = {
            "Question numbers": "//*[contains(text(), '1') or contains(text(), '2') or contains(text(), '3')]",
            "Answer options": "//*[contains(text(), 'А') or contains(text(), 'Б') or contains(text(), 'В') or contains(text(), 'Г')]",
            "Navigation buttons": "//*[contains(text(), 'Далее') or contains(text(), 'Назад') or contains(text(), 'Следующий') or contains(text(), 'Предыдущий')]",
            "List elements": "//ul | //ol",
            "Table rows": "//tr",
            "Table cells": "//td"
        }
        
        for pattern_name, xpath in patterns.items():
            try:
                elements = driver.find_elements(By.XPATH, xpath)
                print(f"  {pattern_name}: {len(elements)} found")
                
                # Show first few examples
                for i, elem in enumerate(elements[:3]):
                    try:
                        text = elem.text.strip()
                        if text and len(text) > 0:
                            print(f"    {i+1}. '{text[:50]}...'")
                    except:
                        pass
            except Exception as e:
                print(f"  {pattern_name}: Error - {e}")
        
        # Save page source for manual inspection
        with open("page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"\n💾 Saved page source to page_source.html")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in comprehensive analysis: {e}")
        return False


def find_question_list_entries(driver):
    """Attempt to locate question list entries and their clickable squares.

    Returns a list of dicts with keys: element, description.
    """
    print("\n🧭 Locating question list entries...")
    candidates = []
    try:
        patterns = [
            # Potential square + text rows
            "//tr[.//td]",
            "//div[contains(@class,'list') or contains(@class,'questions') or contains(@class,'items')]//*[self::div or self::tr or self::li]",
            # Any element with data-index like attributes
            "//*[@data-index or @data-id][not(self::option)]",
            # Any element that looks like a square/checkbox proxy
            "//*[contains(@class,'square') or contains(@class,'box') or contains(@class,'checkbox') or contains(@class,'indicator')]",
            # Links
            "//a[contains(@href,'question') or contains(@onclick,'question')]"
        ]

        for idx, xp in enumerate(patterns, start=1):
            elems = driver.find_elements(By.XPATH, xp)
            print(f"  Pattern {idx}: {len(elems)} nodes")
            for el in elems[:50]:
                try:
                    txt = (el.text or "").strip()
                    cls = el.get_attribute("class") or ""
                    tag = el.tag_name
                    if txt or cls:
                        candidates.append({"element": el, "description": f"<{tag} class='{cls}'> {txt[:80]}"})
                except Exception:
                    pass
        print(f"  Aggregated candidate count: {len(candidates)}")
    except Exception as e:
        print(f"❌ Error locating list entries: {e}")
    return candidates


def open_question_from_list(driver):
    """Try clicking the first question entry/square from the list page."""
    print("\n🖱️  Attempting to open a question from the list...")
    def _is_question_view(d):
        try:
            hdr = d.find_elements(By.XPATH, "//*[contains(text(),'Вопрос ') and contains(text(),' из ')]")
            return bool(hdr)
        except Exception:
            return False

    # Ensure the results list is rendered before searching
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'Список вопросов') or contains(text(),'Результат тестирования')]"))
        )
    except Exception:
        pass

    # Try targeted clicks first (top-most row/question text or checkbox square)
    targeted_xpaths = [
        "(//tr[contains(@class,'xforms-repeat-item')])[1]",
        "(//table//tr[.//td])[1]",
        "(//table//tr[.//td])[2]",
        "(//table//tr[.//td])[1]//td[last()]",
    ]
    for xp in targeted_xpaths:
        try:
            el = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xp)))
            ActionChains(driver).move_to_element(el).pause(0.1).click(el).perform()
            time.sleep(2)
            if _is_question_view(driver):
                print(f"  Opened via targeted selector: {xp}")
                return True
        except Exception:
            continue

    candidates = find_question_list_entries(driver)
    if not candidates:
        print("  No candidates found.")
        return False

    wait = WebDriverWait(driver, 10)
    for cand in candidates:
        el = cand["element"]
        try:
            if el.is_displayed() and el.is_enabled():
                ActionChains(driver).move_to_element(el).pause(0.2).click(el).perform()
                time.sleep(2)
                # Strong check: we must see a question header like "Вопрос X из Y"
                if _is_question_view(driver):
                    print(f"  Opened via: {cand['description']}")
                    return True
        except Exception:
            continue
    print("  Could not open any question.")
    return False


def extract_current_question(driver):
    """Extract question text, options, and determine the correct answer if visually indicated.

    Returns dict with: question_text, options:[{text,is_correct,style}], raw_html
    """
    print("\n📥 Extracting current question...")
    data = {
        "question_text": None,
        "options": [],
        "raw_html": None,
    }
    try:
        container_xps = [
            "//*[contains(@class,'question') and (self::div or self::section)]",
            "//div[contains(@class,'content') and .//*[contains(text(),'Вопрос')]]",
            "//form[.//*[contains(text(),'Вопрос')]]",
        ]
        container = None
        for xp in container_xps:
            elems = driver.find_elements(By.XPATH, xp)
            if elems:
                container = elems[0]
                break
        if not container:
            # Fallback to body
            container = driver.find_element(By.TAG_NAME, "body")

        # Question text: look for prominent headings/labels
        qt_candidates = container.find_elements(By.XPATH, ".//*[self::h1 or self::h2 or self::h3 or contains(@class,'title') or contains(@class,'question')]")
        for el in qt_candidates:
            txt = (el.text or "").strip()
            if len(txt) >= 20:
                data["question_text"] = txt
                break
        if not data["question_text"]:
            # Fallback: the first substantial paragraph
            ps = container.find_elements(By.XPATH, ".//*[self::p or self::div][string-length(normalize-space(text()))>30]")
            if ps:
                data["question_text"] = (ps[0].text or "").strip()

        # Options: look for list items, table rows, inputs with labels
        option_blocks = []
        option_xps = [
            ".//li",
            ".//tr[.//td]",
            ".//*[contains(@class,'option') or contains(@class,'answer') or contains(@class,'choice')]",
            ".//label",
            ".//div[contains(@class,'variant') or contains(@class,'item')]",
        ]
        seen = set()
        for xp in option_xps:
            for el in container.find_elements(By.XPATH, xp):
                try:
                    key = el.id
                except Exception:
                    key = None
                if key and key in seen:
                    continue
                txt = (el.text or "").strip()
                if not txt:
                    continue
                # Heuristic: filter out very long blocks that likely include the whole question
                if len(txt) > 1000:
                    continue
                seen.add(key)
                option_blocks.append(el)

        # Classify options and detect correctness by style (green background)
        options = []
        for el in option_blocks:
            try:
                txt = (el.text or "").strip()
                bg = el.value_of_css_property("background-color") or ""
                cls = el.get_attribute("class") or ""
                style_attr = el.get_attribute("style") or ""
                # Heuristics for correct answer marking
                is_green = any(token in bg for token in ["rgb(0, 128, 0)", "rgba(0, 128, 0)", "rgb(46, 204, 113)", "rgba(46, 204, 113)", "rgb(34, 197, 94)", "rgba(34, 197, 94)"]) or ("background" in style_attr and ("green" in style_attr or "#0f0" in style_attr or "#2ecc71" in style_attr)) or ("correct" in cls.lower())
                options.append({
                    "text": txt,
                    "is_correct": bool(is_green),
                    "style": {"background": bg, "class": cls, "style": style_attr},
                })
            except Exception:
                continue
        data["options"] = options

        # Raw HTML snapshot of container for offline analysis
        try:
            data["raw_html"] = container.get_attribute("innerHTML")
        except Exception:
            data["raw_html"] = None

        # If no obvious options were found, expose a short preview for debugging
        print(f"  Question text len: {len(data['question_text'] or '')}")
        print(f"  Options found: {len(options)} (correct: {sum(1 for o in options if o['is_correct'])})")
        if data["question_text"]:
            print(f"  Q preview: {(data['question_text'][:100] if data['question_text'] else '')}...")
        if options[:3]:
            for i, o in enumerate(options[:3], start=1):
                print(f"  Opt{i}: {(o['text'][:80])} | correct={o['is_correct']}")

        return data
    except Exception as e:
        print(f"❌ Extract failed: {e}")
        return data


def extract_question_dom_precise(driver):
    """Precise DOM extraction based on XForms structure used by the site.

    Returns dict with: question_num, question_text, options[{letter,text,is_correct}], correct_letters
    """
    result = {
        "question_num": None,
        "question_total": None,
        "question_text": None,
        "options": [],
        "correct_letters": [],
    }
    try:
        # Question number from header like: "Вопрос 51 из 80"
        try:
            header_elem = driver.find_element(By.XPATH, "//span[contains(@id,'output-2_12_4_2_') or contains(text(),'Вопрос ') and contains(text(),' из ')]")
            header_text = (header_elem.text or "").strip()
        except Exception:
            # Fallback: any element containing pattern
            header_candidates = driver.find_elements(By.XPATH, "//*[contains(text(),'Вопрос ') and contains(text(),' из ')]")
            header_text = (header_candidates[0].text or "").strip() if header_candidates else None
        if header_text:
            result["question_num"] = None
            import re as _re
            m = _re.search(r"Вопрос\s+(\d+)\s+из\s+(\d+)", header_text)
            if m:
                result["question_num"] = m.group(1)
                result["question_total"] = m.group(2)

        # Question text block: span with class 'testQuestion'
        try:
            qtext_elem = driver.find_element(By.XPATH, "//span[contains(@class,'testQuestion')]//span[contains(@class,'xforms-value')]")
            qtext = (qtext_elem.text or "").strip()
            if qtext:
                result["question_text"] = qtext
        except Exception:
            pass

        # Options table rows
        rows = driver.find_elements(By.XPATH, "//table[contains(@class,'question_options')]//tr[contains(@class,'xforms-repeat-item')]")
        options = []
        correct_letters = []
        for row in rows:
            try:
                letter_td = row.find_element(By.XPATH, ".//td[contains(@class,'testLetter')]")
                text_td = row.find_element(By.XPATH, ".//td[contains(@class,'testAnswer')]")
            except Exception:
                continue
            letter = (letter_td.text or "").strip()
            # The letter might be rendered via nested spans; normalize single letter
            if len(letter) > 2:
                # try to extract a single Russian letter at start
                import re as _re
                m = _re.search(r"[А-ЯA-Z]", letter)
                letter = m.group(0) if m else letter[:1]
            text = (text_td.text or "").strip()
            cls_letter = letter_td.get_attribute("class") or ""
            cls_text = text_td.get_attribute("class") or ""
            is_correct = ("correct_answer" in cls_letter) or ("correct_answer" in cls_text)
            if is_correct and letter:
                correct_letters.append(letter)
            options.append({
                "letter": letter,
                "text": text,
                "is_correct": is_correct,
            })
        if options:
            result["options"] = options
            result["correct_letters"] = correct_letters

        return result
    except Exception as e:
        print(f"⚠️  Precise DOM extract failed: {e}")
        return result


def click_next_question(driver):
    """Click the Next button if present. Returns True if navigation attempted."""
    print("\n➡️  Attempting to click Next...")
    try:
        selectors = [
            "//*[contains(text(),'Далее')]/ancestor::*[self::button or self::a or self::span][1]",
            "//*[contains(text(),'Следующий')]/ancestor::*[self::button or self::a or self::span][1]",
            "//button[contains(@class,'next') or contains(@class,'forward')]",
            "//a[contains(@class,'next') or contains(@class,'forward')]",
        ]
        for xp in selectors:
            btns = driver.find_elements(By.XPATH, xp)
            for btn in btns:
                try:
                    if btn.is_displayed() and btn.is_enabled():
                        ActionChains(driver).move_to_element(btn).pause(0.2).click(btn).perform()
                        time.sleep(2)
                        return True
                except Exception:
                    continue
        print("  Next not found.")
        return False
    except Exception as e:
        print(f"❌ Next navigation error: {e}")
        return False


def enable_cdp_network_logging(driver):
    """Enable CDP Network logging to detect dynamic endpoints during navigation."""
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Page.enable", {})
        print("📡 CDP Network logging enabled")
    except Exception as e:
        print(f"⚠️  Could not enable CDP logging: {e}")


def _start_new_test_in_new_tab(driver):
    """From the base tab (history/testing page), start the same test in a new tab and switch to it.

    Returns True on success, otherwise False.
    """
    try:
        wait = WebDriverWait(driver, 10)
        # Click "Пройти тестирование"
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Пройти тестирование']")))
            btn.click()
            time.sleep(2)
        except Exception:
            pass  # It may already be open

        # Click the specific test item (same XPath used earlier)
        test_xpath = "//span[@class='extraSpace' and contains(text(), 'РЭ_Лечебное дело, 2025')]"
        test_element = wait.until(EC.element_to_be_clickable((By.XPATH, test_xpath)))
        test_element.click()
        time.sleep(2)

        # Switch to the newly opened window
        original = None
        for h in driver.window_handles:
            if h == driver.current_window_handle:
                original = h
                break
        WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
        for h in driver.window_handles:
            if h != original:
                driver.switch_to.window(h)
                break
        time.sleep(3)

        # Click "Перейти к первому вопросу"
        try:
            go_first = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Перейти к первому вопросу')]")))
            go_first.click()
            time.sleep(2)
        except Exception:
            pass

        # Complete and confirm, same as first cycle
        try:
            complete_button = driver.find_element(By.XPATH, "//span[contains(text(), 'Завершить тестирование')]")
            complete_button.click()
            time.sleep(2)
            try:
                complete_anyway = driver.find_element(By.XPATH, "//*[contains(text(), 'Все равно завершить')]")
                complete_anyway.click()
                time.sleep(5)
            except Exception:
                pass
        except Exception:
            pass

        # Give the results page a moment to render
        time.sleep(2)

        return True
    except Exception:
        return False


def drain_performance_logs(driver, limit=200):
    """Fetch recent performance logs for network/XHR reconnaissance."""
    logs = []
    try:
        for entry in driver.get_log("performance")[:limit]:
            try:
                obj = json.loads(entry.get("message", "{}"))
                msg = obj.get("message", {})
                method = msg.get("method")
                params = msg.get("params", {})
                if method and method.startswith("Network."):
                    url = (params.get("request", {}) or {}).get("url") or params.get("response", {}).get("url")
                    request_id = params.get("requestId")
                    if url:
                        logs.append({"method": method, "url": url, "requestId": request_id})
            except Exception:
                continue
    except Exception:
        pass
    if logs:
        print("\n🌐 Recent network events (sample):")
        for item in logs[:10]:
            print(f"  {item['method']}: {item['url'][:120]}")
    return logs


def capture_recent_secured_data_bodies(driver, logs, out_dir="data_payloads"):
    """Capture response bodies for '/spec/qt/secured/data' requests from recent logs via CDP.

    Returns list of file paths written.
    """
    written = []
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        pass
    try:
        for item in logs:
            if not isinstance(item, dict):
                continue
            url = item.get("url", "") or ""
            if "/spec/qt/secured/data" in url and item.get("method") == "Network.responseReceived":
                req_id = item.get("requestId")
                if not req_id:
                    continue
                try:
                    body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": req_id})
                    text = body.get("body", "")
                    base = os.path.join(out_dir, f"payload_{int(time.time()*1000)}.json")
                    with open(base, "w", encoding="utf-8") as f:
                        f.write(text)
                    written.append(base)
                except Exception:
                    continue
    except Exception:
        pass
    if written:
        print(f"📝 Saved {len(written)} secured/data payload(s) to '{out_dir}'")
    return written


def get_question_signature(driver):
    """Return a lightweight signature of the current question area to detect changes between navigations."""
    try:
        container = None
        for xp in [
            "//*[contains(@class,'question') and (self::div or self::section)]",
            "//div[contains(@class,'content') and .//*[contains(text(),'Вопрос')]]",
            "//form[.//*[contains(text(),'Вопрос')]]",
        ]:
            els = driver.find_elements(By.XPATH, xp)
            if els:
                container = els[0]
                break
        if not container:
            container = driver.find_element(By.TAG_NAME, "body")
        html = container.get_attribute("innerHTML") or ""
        return str(len(html)) + ":" + (html[:200] if len(html) > 200 else html)
    except Exception:
        return None


def cleanup_payloads(out_dir="data_payloads", keep_latest_n=50):
    """Keep only latest N payload files; remove older ones. If folder doesn't exist, create it."""
    try:
        os.makedirs(out_dir, exist_ok=True)
        entries = []
        for name in os.listdir(out_dir):
            fp = os.path.join(out_dir, name)
            if os.path.isfile(fp):
                entries.append((fp, os.path.getmtime(fp)))
        entries.sort(key=lambda x: x[1], reverse=True)
        for fp, _ in entries[keep_latest_n:]:
            try:
                os.remove(fp)
            except Exception:
                pass
        print(f"🧹 data_payloads cleaned; kept {min(len(entries), keep_latest_n)} recent file(s)")
    except Exception as e:
        print(f"⚠️  cleanup skipped: {e}")


def _next_question_set_filename(base_dir="."):
    """Return a non-existing filename like question_set_N.jsonl with the next index."""
    try:
        existing = []
        for name in os.listdir(base_dir):
            if name.startswith("question_set_") and name.endswith(".jsonl"):
                try:
                    n = int(name[len("question_set_"):-len(".jsonl")])
                    existing.append(n)
                except Exception:
                    continue
        next_n = (max(existing) + 1) if existing else 1
        return os.path.join(base_dir, f"question_set_{next_n}.jsonl")
    except Exception:
        return os.path.join(base_dir, "question_set_1.jsonl")


def _unescape_js_hex_escapes(text):
    r"""Convert \xNN escapes to characters, keep text robust for XML parsing."""
    try:
        # Replace \\xNN with the corresponding char
        def repl(match):
            return bytes.fromhex(match.group(1)).decode('latin1')
        return re.sub(r"\\x([0-9A-Fa-f]{2})", repl, text)
    except Exception:
        return text


def _extract_schema_xml_from_payload(payload_text):
    """Best-effort extraction of <schema>...</schema> XML from GWT/XForms payload."""
    if not payload_text:
        return None
    s = _unescape_js_hex_escapes(payload_text)
    # Remove control characters that break XML parsing
    s = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", s)
    # Find the <schema> ... </schema> block with DOTALL
    m = re.search(r"<schema>[\s\S]*?</schema>", s)
    if not m:
        return None
    xml = m.group(0)
    return xml


def _strip_html_preserve_spaces(html_text):
    try:
        from lxml import html
        doc = html.fromstring(html_text)
        return doc.text_content().strip()
    except Exception:
        # Fallback plain removal of tags
        return re.sub(r"<[^>]+>", " ", html_text or "").replace("\n", " ").strip()


def parse_schema_xml(schema_xml):
    """Parse the schema XML string to extract question info and options.

    Returns dict: { question_num, question_header, question_html, question_text, options:[{letter,text,is_true,id}], is_last }
    """
    try:
        # Prefer lxml for robust parsing; fallback to ElementTree
        try:
            from lxml import etree as LET
            parser = LET.XMLParser(recover=True)
            root = LET.fromstring(schema_xml.encode('utf-8'), parser=parser)
            find = root.find
            findtext = lambda path: (root.find(path).text if root.find(path) is not None else None)
        except Exception:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(schema_xml)
            find = root.find
            def findtext(path):
                el = root.find(path)
                return el.text if el is not None else None
        desc = find("description")
        result = {
            "question_num": None,
            "question_header": None,
            "question_html": None,
            "question_text": None,
            "options": [],
            "is_last": None,
        }
        if desc is not None:
            q_el = desc.find("question")
            if q_el is not None:
                # question header
                qh = desc.find("questionHeader")
                result["question_header"] = (qh.text or "").strip() if qh is not None else None
                result["question_num"] = q_el.attrib.get("number")
                result["is_last"] = q_el.attrib.get("isLastQuestion") == "1"
                # question element content seems to have escaped HTML like &lt;p&gt;
                q_html_escaped = (q_el.text or "").strip()
                q_html = html_lib.unescape(q_html_escaped)
                result["question_html"] = q_html
                result["question_text"] = _strip_html_preserve_spaces(q_html)
            options_root = desc.find("options")
            if options_root is not None:
                for opt in options_root.findall("option"):
                    letter = opt.findtext("letter") or ""
                    opt_id = opt.findtext("id") or ""
                    is_true = (opt.findtext("isTrue") or "").lower() == "true"
                    opt_html_escaped = opt.findtext("destructorHTML") or ""
                    opt_html = html_lib.unescape(opt_html_escaped)
                    opt_text = _strip_html_preserve_spaces(opt_html)
                    result["options"].append({
                        "letter": letter,
                        "id": opt_id,
                        "is_true": is_true,
                        "text": opt_text,
                        "raw_html": opt_html,
                    })
        return result
    except Exception as e:
        print(f"⚠️  Schema parse error: {e}")
        return None


def iterate_questions(driver, max_questions=80, out_path="questions.jsonl", enable_network_logs=True, clean_payloads_first=True):
    """From the question list page, open first question, then iterate via Next, extracting data.

    Writes JSONL to out_path.
    """
    print("\n🔁 Iterating questions and extracting data...")
    if enable_network_logs:
        enable_cdp_network_logging(driver)

    if clean_payloads_first:
        cleanup_payloads("data_payloads", keep_latest_n=0)

    opened = open_question_from_list(driver)
    if not opened:
        print("❌ Could not open a question from list. Aborting iteration.")
        return 0

    extracted = 0
    # Optional SQLite + GT estimator setup
    store = None
    estimator = None
    run_id = None
    duplicates = 0
    uniques = 0
    # Track question-hash frequencies for pool-size estimation
    qhash_to_count = {}
    if USE_SQLITE:
        try:
            store = SQLiteStore(SQLITE_PATH)
            store.connect()
            estimator = GoodTuringEstimator()
            # Start run row
            started_iso = datetime.utcnow().isoformat() + "Z"
            try:
                run_id = store.run_start(label=SET_LABEL, started_at_iso=started_iso)
            except Exception:
                run_id = None
        except Exception as e:
            print(f"⚠️  SQLite init failed: {e}")
            store = None
            estimator = None
    start_time = time.time()  # Start timer
    with open(out_path, "w", encoding="utf-8") as f:
        for i in range(max_questions):
            recent_logs = drain_performance_logs(driver) if enable_network_logs else []
            parsed_schema = None
            if enable_network_logs and recent_logs:
                files = capture_recent_secured_data_bodies(driver, recent_logs)
                # Try to parse the last captured payload to extract exact data
                for fp in reversed(files or []):
                    try:
                        with open(fp, "r", encoding="utf-8") as pf:
                            payload = pf.read()
                        schema_xml = _extract_schema_xml_from_payload(payload)
                        if schema_xml:
                            parsed_schema = parse_schema_xml(schema_xml)
                            if parsed_schema:
                                break
                    except Exception:
                        continue

            # Prefer DOM-precise extraction; enrich with schema when available
            record = {"index": i + 1}
            dom_precise = extract_question_dom_precise(driver)
            if dom_precise and dom_precise.get("options"):
                record.update({
                    "question_num": dom_precise.get("question_num"),
                    "question_text": dom_precise.get("question_text"),
                    "options": dom_precise.get("options"),
                    "correct_letters": dom_precise.get("correct_letters"),
                })
            else:
                # fallback to heuristic DOM
                dom_data = extract_current_question(driver)
                record.update({
                    "question_text": dom_data.get("question_text"),
                    "options": [{"text": o.get("text"), "is_correct": o.get("is_correct")} for o in dom_data.get("options", [])],
                })

            if parsed_schema:
                # If schema is available, fill missing fields or cross-check
                if not record.get("question_text") and parsed_schema.get("question_text"):
                    record["question_text"] = parsed_schema.get("question_text")
                if not record.get("question_num") and parsed_schema.get("question_num"):
                    record["question_num"] = parsed_schema.get("question_num")
                # If options empty, adopt schema options
                if not record.get("options") and parsed_schema.get("options"):
                    record["options"] = [{"letter": o.get("letter"), "text": o.get("text"), "is_correct": o.get("is_true")} for o in parsed_schema.get("options", [])]
                    record["correct_letters"] = [o["letter"] for o in parsed_schema.get("options", []) if o.get("is_true")]
                # Keep is_last if present
                if parsed_schema.get("is_last") is not None:
                    record["is_last"] = parsed_schema.get("is_last")

            # Persist JSONL as before
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

            # Persist to SQLite if enabled
            try:
                if store is not None:
                    # Build stable question hash over text + sorted options
                    qtext = record.get("question_text") or ""
                    opts_for_hash = []
                    for o in record.get("options", []) or []:
                        opts_for_hash.append((o.get("letter") or "", o.get("text") or ""))
                    opts_for_hash.sort()
                    hasher = hashlib.sha256()
                    hasher.update(qtext.encode("utf-8", errors="ignore"))
                    for lt, tx in opts_for_hash:
                        hasher.update(b"|LT|")
                        hasher.update(lt.encode("utf-8", errors="ignore"))
                        hasher.update(b"|TX|")
                        hasher.update(tx.encode("utf-8", errors="ignore"))
                    qhash = hasher.hexdigest()

                    # Duplicate detection and frequency accounting
                    is_dup = False
                    try:
                        is_dup = store.hash_exists(qhash)
                    except Exception:
                        is_dup = False
                    if is_dup:
                        duplicates += 1
                    else:
                        uniques += 1
                    # Update in-memory counts for Chao1 / GT over hashes
                    prev_c = qhash_to_count.get(qhash, 0)
                    qhash_to_count[qhash] = prev_c + 1

                    options_for_db = []
                    for o in record.get("options", []) or []:
                        # Normalize fields across DOM and schema paths
                        options_for_db.append({
                            "letter": o.get("letter"),
                            "text": o.get("text"),
                            "is_correct": bool(o.get("is_correct") or o.get("is_true")),
                        })
                    store.insert_question_with_options(
                        set_label=SET_LABEL,
                        question_num=(record.get("question_num") if record.get("question_num") is not None else str(record.get("index"))),
                        question_text=record.get("question_text"),
                        options=options_for_db,
                        qhash=qhash,
                    )
                    # Update Good–Turing counts incrementally for correct option texts
                    if estimator is not None:
                        for o in options_for_db:
                            if o.get("is_correct") and o.get("text"):
                                estimator.increment(o["text"], 1)
            except Exception as e:
                print(f"⚠️  SQLite write failed: {e}")

            # Optionally annotate current record with GT probabilities (preview/logging)
            try:
                if estimator is not None and record.get("options"):
                    p0 = estimator.probability_of_unseen()
                    annotated = []
                    for o in record["options"]:
                        text_val = o.get("text")
                        p = estimator.smoothed_probability(text_val) if text_val else None
                        o_copy = dict(o)
                        o_copy["gt_prob"] = p if p is not None else p0
                        annotated.append(o_copy)
                    record["options"] = annotated
            except Exception:
                pass

            # Compute Good–Turing P0 and Chao1 for question hashes
            try:
                total_obs_q = sum(qhash_to_count.values())
                f1 = sum(1 for c in qhash_to_count.values() if c == 1)
                f2 = sum(1 for c in qhash_to_count.values() if c == 2)
                p0_hashes = (float(f1) / float(total_obs_q)) if total_obs_q > 0 else 0.0
                if f2 > 0:
                    chao1 = len(qhash_to_count) + (f1 * f1) / (2.0 * f2)
                else:
                    chao1 = float(len(qhash_to_count))  # fallback
                # periodic terminal stats
                if extracted % 5 == 0 or i == 0:
                    print(f"[stats] step={extracted} total={extracted} unique={uniques} dup={duplicates} P0={p0_hashes:.4f} Chao1≈{chao1:.1f}")
            except Exception:
                pass
            extracted += 1

            # Periodic payload cleanup: purge every 5 questions to control disk usage
            try:
                if extracted % 5 == 0:
                    cleanup_payloads("data_payloads", keep_latest_n=0)
            except Exception:
                pass

            # If current question is the last one per header, stop after saving it
            try:
                if dom_precise and dom_precise.get("question_num") and dom_precise.get("question_total"):
                    if str(dom_precise.get("question_num")) == str(dom_precise.get("question_total")):
                        print("🛑 Reached last question according to header (saved). Stopping.")
                        break
            except Exception:
                pass

            moved = click_next_question(driver)
            if not moved:
                print("⛔ No Next found; stopping iteration.")
                break
            # Wait for content change or at least a short delay for dynamic load
            old_sig = get_question_signature(driver)
            for _ in range(20):
                time.sleep(0.3)
                new_sig = get_question_signature(driver)
                if new_sig and new_sig != old_sig:
                    break
            time.sleep(0.7)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"\n✅ Extracted {extracted} question(s) in {elapsed_time:.2f} seconds ({elapsed_time/extracted:.2f} seconds per question)")
    print(f"💾 Data saved to {out_path}")
    try:
        if store is not None:
            # Close out run stats
            try:
                ended_iso = datetime.utcnow().isoformat() + "Z"
                duration = time.time() - start_time
                if run_id is not None:
                    store.run_finish(
                        run_id=run_id,
                        ended_at_iso=ended_iso,
                        total_questions=extracted,
                        unique_questions=uniques,
                        duplicate_questions=duplicates,
                        duration_seconds=float(duration),
                    )
            except Exception:
                pass
            store.close()
    except Exception:
        pass
    return extracted


def loop_additional_quizzes(driver, num_additional_sets=2, wait_seconds=7):
    """After finishing the first extraction in the active quiz tab, run more quizzes.

    For each additional set:
      - wait `wait_seconds`, close the current quiz tab
      - switch back to the base tab, refresh
      - start a new quiz in a new tab, switch to it
      - extract questions to question_set_{k}.jsonl (1-indexed for additional runs)
    """
    for k in range(1, num_additional_sets + 1):
        try:
            time.sleep(wait_seconds)
            # Close current quiz tab
            try:
                driver.close()
            except Exception:
                pass

            # Switch to the remaining (base) tab
            try:
                remaining = driver.window_handles[0]
                driver.switch_to.window(remaining)
            except Exception:
                # Fallback: pick any available handle
                for h in driver.window_handles:
                    try:
                        driver.switch_to.window(h)
                        break
                    except Exception:
                        continue

            # Refresh the base page to update history
            try:
                driver.refresh()
                time.sleep(3)
            except Exception:
                pass

            # Start new test in a fresh tab and switch
            started = _start_new_test_in_new_tab(driver)
            if not started:
                print("⚠️  Could not start a new test. Stopping loop.")
                break

            # Extract this set to the next available question_set_N.jsonl
            out_path = _next_question_set_filename(".")
            iterate_questions(driver, max_questions=80, out_path=out_path, enable_network_logs=True)
        except Exception as e:
            print(f"⚠️  Error in quiz loop iteration {k}: {e}")
            break


def test_clicking_approaches(driver):
    """Test different clicking approaches"""
    print("\n🧪 TESTING CLICKING APPROACHES")
    print("=" * 40)
    
    try:
        # Approach 1: Look for any clickable elements that might be questions
        print("\n📋 Approach 1: Looking for clickable question elements...")
        
        # Try different selectors for question elements
        question_selectors = [
            "//tr[contains(@class, 'xforms-repeat-item')]",
            "//td[contains(text(), '1') or contains(text(), '2') or contains(text(), '3')]",
            "//*[contains(@class, 'question')]",
            "//*[contains(@class, 'item')]",
            "//*[contains(@class, 'row')]"
        ]
        
        for i, selector in enumerate(question_selectors):
            try:
                elements = driver.find_elements(By.XPATH, selector)
                print(f"  Selector {i+1}: Found {len(elements)} elements")
                
                if elements:
                    # Try clicking on first element
                    first_elem = elements[0]
                    try:
                        text = first_elem.text.strip()
                        print(f"    First element: '{text[:50]}...'")
                        
                        # Check if clickable
                        is_clickable = first_elem.is_enabled() and first_elem.is_displayed()
                        print(f"    Clickable: {is_clickable}")
                        
                        if is_clickable:
                            print(f"    Attempting to click...")
                            first_elem.click()
                            time.sleep(3)
                            
                            # Check what happened
                            new_url = driver.current_url
                            print(f"    New URL: {new_url}")
                            
                            # Look for changes in the page
                            new_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Вопрос')]")
                            print(f"    Question elements after click: {len(new_elements)}")
                            
                            # Go back if possible
                            try:
                                back_button = driver.find_element(By.XPATH, "//*[contains(text(), 'К списку') or contains(text(), 'Назад')]")
                                back_button.click()
                                time.sleep(2)
                                print(f"    Returned to question list")
                            except:
                                print(f"    Could not return to question list")
                                # Refresh page
                                driver.refresh()
                                time.sleep(5)
                            
                    except Exception as e:
                        print(f"    Error clicking: {e}")
                
            except Exception as e:
                print(f"  Selector {i+1}: Error - {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing clicking approaches: {e}")
        return False

def main():
    """Main function"""
    print("🚀 Starting RECONNAISSANCE SCRIPT")
    print("=" * 50)
    
    driver = None
    try:
        driver = setup_driver()
        
        # Login and navigate to results
        driver = login_and_navigate_to_results(driver)
        
        # Comprehensive page analysis
        comprehensive_page_analysis(driver)
        
        # Test clicking approaches
        test_clicking_approaches(driver)

        # Iterate questions and extract data (first set) -> save to next question_set_N.jsonl
        first_out = _next_question_set_filename(".")
        iterate_questions(driver, max_questions=80, out_path=first_out, enable_network_logs=True)

        # Run additional quizzes, saving as question_set_1.jsonl, question_set_2.jsonl, ...
        loop_additional_quizzes(driver, num_additional_sets=2, wait_seconds=7)
        
        print("\n✅ Reconnaissance complete!")
        
    except Exception as e:
        print(f"❌ Reconnaissance failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            print("\n⏳ Keeping browser open for 60 seconds for manual inspection...")
            time.sleep(60)
            driver.quit()
            print("🔚 Driver closed")

if __name__ == "__main__":
    main()

