#!/bin/bash

# This script automates the setup of the scraper on a fresh Ubuntu VM.

# Exit immediately if a command exits with a non-zero status.
# This is crucial for debugging.
set -e

echo "--- 1. UPDATING SYSTEM ---"
sudo apt-get update
sudo apt-get upgrade -y

echo "--- 2. INSTALLING SYSTEM DEPENDENCIES (Python, Pip, Curl, Unzip) ---"
sudo apt-get install -y python3 python3-pip python3-venv curl unzip

echo "--- 3. INSTALLING BRAVE BROWSER ---"
# Add Brave's key and repository
sudo curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/brave-browser-archive-keyring.gpg] https://brave-browser-apt-release.s3.brave.com/ stable main" | sudo tee /etc/apt/sources.list.d/brave-browser-release.list
# Update sources and install
sudo apt-get update
sudo apt-get install -y brave-browser

echo "--- 4. DOWNLOADING AND CONFIGURING THE CORRECT CHROMEDRIVER ---"
# Get the installed Brave version (e.g., 124.0.6367.201)
BRAVE_VERSION=$(brave-browser --version | cut -d ' ' -f 3)
echo "Detected Brave version: $BRAVE_VERSION"

# Construct the download URL for the matching chromedriver
DRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${BRAVE_VERSION}/linux64/chromedriver-linux64.zip"
echo "Downloading ChromeDriver from: $DRIVER_URL"

# Download, unzip, make executable, and clean up
wget -N $DRIVER_URL
unzip chromedriver-linux64.zip
chmod +x ./chromedriver-linux64/chromedriver
rm chromedriver-linux64.zip

echo "--- 5. SETTING UP PYTHON VIRTUAL ENVIRONMENT & INSTALLING LIBRARIES ---"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

echo "--- SETUP COMPLETE ---"
echo "The environment is ready. Next steps:"
echo "1. Create your .env file with credentials: nano .env"
echo "2. Activate the environment: source venv/bin/activate"
echo "3. Start the script using screen: screen -S scraper"