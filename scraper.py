# scraper.py

import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
# IMPORTANT: Update these paths and URLs
BRAVE_PATH = "/usr/bin/brave-browser"  # Path to Brave browser executable
DRIVER_PATH = "./chromedriver-linux64/chromedriver" # Path to the chromedriver we downloaded
LOGIN_URL = "https://selftest.mededtech.ru/login.jsp" # <--- I NEED THIS URL FROM YOU

# Configure Selenium to use Brave browser
chrome_options = Options()
chrome_options.binary_location = BRAVE_PATH

# Set up the WebDriver Service
service = Service(executable_path=DRIVER_PATH)

# Initialize the driver
print("🚀 Starting the scraper...")
driver = webdriver.Chrome(service=service, options=chrome_options)

# Open the login page
print(f"Navigating to login page: {LOGIN_URL}")
driver.get(LOGIN_URL)

# Keep the browser open for a bit so we can see it worked
time.sleep(10) 

# Clean up
print("✅ Scraper finished.")
driver.quit()