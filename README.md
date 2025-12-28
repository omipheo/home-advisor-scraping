# HomeAdvisor Scraper

This script scrapes business listings from HomeAdvisor and enriches them with contact information (phone numbers and emails) by visiting their websites and searching Google when necessary.

## Features

- **Flexible URL Support**: Enter any HomeAdvisor category/location URL to scrape
- **Automatic Page Detection**: Automatically detects the total number of pages to scrape
- **Multi-City Support**: Easily scrape different cities by running with different URLs
- Extracts: business name, star rating, number of reviews, address, website
- Visits each business website to find phone numbers and emails
- Falls back to Google search if phone number not found on website
- Automatically writes data to Google Sheets

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Google Sheets API Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Sheets API and Google Drive API
4. Create a Service Account:
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Give it a name and create
   - Click on the service account and go to "Keys" tab
   - Click "Add Key" > "Create new key" > Choose JSON
   - Download the JSON file and save it as `homeadvisorelizabethscraping-613984138d99.json` in the project root
5. Share your Google Sheet with the service account email:
   - Open your Google Sheet: https://docs.google.com/spreadsheets/d/1mt2pi6hxnDpKiCu8sHlBQHz07ptujXEOPJxq5T-Zfxw
   - Click "Share" button (top right)
   - Add this email as an **Editor**: `home-advisor-gh-api@homeadvisorelizabethscraping.iam.gserviceaccount.com`
   - Click "Send" (you can uncheck "Notify people" if you don't want an email)
   - **Important**: The service account must have Editor access to write data

### 3. Google Chrome Browser

**Important:** The script uses **Google Chrome browser** via Selenium. You must have Google Chrome installed on your system.

- Download Chrome from: https://www.google.com/chrome/
- The `webdriver-manager` package will automatically download and manage ChromeDriver
- Make sure Chrome is up to date for best compatibility

## Usage

### Option 1: GUI (Recommended)

The easiest way to use the scraper is with the graphical interface:

```bash
python scraper_gui.py
```

This will open a window where you can:
- Enter any HomeAdvisor URL
- Set the starting page
- Choose headless mode (no browser window)
- See real-time progress in the log
- Stop the scraper if needed

### Option 2: Command Line

1. Make sure `homeadvisorelizabethscraping-613984138d99.json` is in the project root directory

2. **Test Google Sheets connection** (important!):
   ```bash
   python test_google_sheet.py
   ```
   This will:
   - Verify the credentials work
   - Check if the service account has access to your sheet
   - Write a test row to confirm everything works
   - Show you exactly what to do if there are permission issues

3. **Test the scraper** (recommended):
   ```bash
   python test_scraper.py
   ```
   This will test the scraper on just the first page to make sure everything works.

4. Run the full scraper:
   ```bash
   python scraper.py
   ```

## Checking if Data is Being Written

### Method 1: Test Script
Run the test script to verify connection and write a test row:
```bash
python test_google_sheet.py
```
This will write a test row that you can see in your sheet.

### Method 2: Check Your Sheet
1. Open your Google Sheet: https://docs.google.com/spreadsheets/d/1mt2pi6hxnDpKiCu8sHlBQHz07ptujXEOPJxq5T-Zfxw
2. Look for new rows being added (the scraper writes every 10 businesses)
3. The headers should be: business name, star rating, # of reviews, address, website, Phone Number, Email

### Method 3: Watch the Console
The scraper prints messages like:
- `"Wrote 10 businesses to sheet"` - confirms data was written
- `"Sheet initialized with headers"` - confirms connection worked

The script will:
- Prompt you for a HomeAdvisor URL (or accept it as a command-line argument)
- Automatically detect the total number of pages
- Clear the existing sheet and add headers (on first run from page 1)
- Scrape all pages from the provided URL
- For each business, visit their website to find phone/email
- If phone not found, search Google
- Write data to Google Sheets in batches (every 10 businesses)

## Usage

### Basic Usage

Run the scraper and enter a URL when prompted:

```bash
python scraper.py
```

The scraper will:
1. Ask you for a HomeAdvisor URL (any category/location URL)
2. Automatically detect the total number of pages
3. Ask which page to start from (or press Enter for page 1)
4. Scrape all businesses from that URL

### Command Line Usage

You can also provide the URL and start page as command-line arguments:

```bash
# Scrape from page 1
python scraper.py "https://www.homeadvisor.com/c.Air-Conditioning.Elizabeth.NJ.-12002.html"

# Resume from a specific page
python scraper.py "https://www.homeadvisor.com/c.Air-Conditioning.Elizabeth.NJ.-12002.html" 7
```

### Multiple Cities/URLs

You can scrape different cities by running the scraper multiple times with different URLs:

```bash
# Scrape Elizabeth, NJ
python scraper.py "https://www.homeadvisor.com/c.Air-Conditioning.Elizabeth.NJ.-12002.html"

# Then scrape another city
python scraper.py "https://www.homeadvisor.com/c.Air-Conditioning.Newark.NJ.-12002.html"
```

All data will be saved to the same Google Sheet.

## Configuration

You can modify these variables in `scraper.py`:

- `GOOGLE_SHEET_ID`: Your Google Sheet ID (found in the URL)
- `HEADLESS_MODE`: Set to `False` to see the browser (useful for debugging CAPTCHAs)

## Notes

- The script includes rate limiting to be respectful to websites
- It processes businesses in batches and writes to the sheet periodically (every 10 businesses)
- If the script stops, you can modify `START_PAGE` in `scraper.py` to resume from a specific page
- Phone numbers are prioritized over emails
- If phone is not found on website, Google search is used (but email search is skipped)
- The script will save progress as it goes, so you can stop and resume anytime
- Each page takes approximately 2-5 minutes depending on how many businesses need website visits

## CAPTCHA and Blocking

**Yes, HomeAdvisor can block scraping or show CAPTCHAs.** The scraper includes several anti-detection measures:

### Built-in Protections:
- ✅ Random delays between requests (appears more human-like)
- ✅ Rotating User-Agents
- ✅ Stealth Selenium configuration (removes automation indicators)
- ✅ CAPTCHA detection and alerts
- ✅ Realistic browser behavior

### Automatic CAPTCHA Solving (Recommended)

The scraper now supports **automatic CAPTCHA solving** using 2Captcha API:

1. **Sign up for 2Captcha** (paid service):
   - Go to https://2captcha.com/
   - Create an account and add credits ($2.99 per 1000 CAPTCHAs)
   - Get your API key from the dashboard

2. **Enable automatic solving**:
   
   **Option A: GUI**
   - Enter your 2Captcha API key in the "2Captcha API Key" field
   - The key will be hidden for security
   
   **Option B: Command Line**
   ```bash
   # Set environment variable
   set CAPTCHA_API_KEY=your_api_key_here  # Windows
   export CAPTCHA_API_KEY=your_api_key_here  # Linux/Mac
   
   # Or pass as argument
   python scraper.py "URL" 1 "your_api_key_here"
   ```
   
   **Option C: Environment Variable**
   ```bash
   # Windows
   set CAPTCHA_API_KEY=your_api_key_here
   
   # Linux/Mac
   export CAPTCHA_API_KEY=your_api_key_here
   ```

3. **How it works**:
   - When a Cloudflare Turnstile CAPTCHA is detected, the scraper automatically:
     - Extracts the site key
     - Submits it to 2Captcha
     - Waits for the solution (usually 10-30 seconds)
     - Injects the solution token into the page
     - Continues scraping automatically

### Manual CAPTCHA Solving (Fallback)

If you don't use automatic solving:

1. **Switch to non-headless mode** (see browser window):
   - In GUI: Uncheck "Run in headless mode"
   - Or edit `scraper.py` and set `HEADLESS_MODE = False`
   - Run again - you'll see the browser and can solve CAPTCHAs manually
   - The script will pause and wait for you to solve them

2. **Slow down the scraper**:
   - Increase the random delay ranges in the code
   - Add more time between pages

3. **Use a VPN or proxy** (advanced):
   - Change your IP address if you get blocked
   - Consider using residential proxies for large-scale scraping

4. **Take breaks**:
   - Run the scraper in smaller batches
   - Resume from different pages using `START_PAGE`

### Best Practices:
- Run during off-peak hours (late night/early morning)
- Don't run multiple instances simultaneously
- Respect rate limits (the script does this automatically)

## Troubleshooting

### ChromeDriver Error: "[WinError 193] %1 is not a valid Win32 application"

This error means ChromeDriver is corrupted or there's an architecture mismatch. Fix it by:

1. **Run the fix script** (easiest):
   ```bash
   python fix_chromedriver.py
   ```

2. **Or manually clear cache**:
   - Delete the folder: `%USERPROFILE%\.wdm`
   - Re-run the scraper (it will re-download ChromeDriver)

3. **Check architecture**:
   - Make sure you're using 64-bit Python if you have 64-bit Chrome
   - Check Python: `python -c "import platform; print(platform.architecture())"`
   - Check Chrome: Right-click Chrome → Properties → Details tab

### Other Issues

- **ChromeDriver issues**: Make sure Chrome is installed and up to date
- **Google Sheets permission errors**: Verify the service account has access to the sheet
- **No listings found**: HomeAdvisor may have changed their HTML structure - you may need to update the selectors in `extract_business_info()`
- **CAPTCHA detected**: Switch to non-headless mode (`HEADLESS_MODE = False`) to solve manually
- **Getting blocked**: Increase delays, use VPN, or run in smaller batches

