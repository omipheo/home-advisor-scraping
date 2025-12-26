# HomeAdvisor Scraper

This script scrapes business listings from HomeAdvisor and enriches them with contact information (phone numbers and emails) by visiting their websites and searching Google when necessary.

## Features

- Scrapes all 105 pages of HomeAdvisor listings for Air Conditioning businesses in Elizabeth, NJ
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
5. Share your Google Sheet with the service account email (found in the JSON file):
   - Open your Google Sheet
   - Click "Share" button
   - Paste the service account email and give it "Editor" access

### 3. Google Chrome Browser

**Important:** The script uses **Google Chrome browser** via Selenium. You must have Google Chrome installed on your system.

- Download Chrome from: https://www.google.com/chrome/
- The `webdriver-manager` package will automatically download and manage ChromeDriver
- Make sure Chrome is up to date for best compatibility

## Usage

1. Make sure `homeadvisorelizabethscraping-613984138d99.json` is in the project root directory
2. **Test first** (recommended):
   ```bash
   python test_scraper.py
   ```
   This will test the scraper on just the first page to make sure everything works.

3. Run the full scraper:
   ```bash
   python scraper.py
   ```

The script will:
- Clear the existing sheet and add headers (on first run)
- Scrape all 105 pages from HomeAdvisor
- For each business, visit their website to find phone/email
- If phone not found, search Google
- Write data to Google Sheets in batches (every 10 businesses)

## Configuration

You can modify these variables in `scraper.py`:

- `GOOGLE_SHEET_ID`: Your Google Sheet ID (found in the URL)
- `total_pages`: Number of pages to scrape (default: 105)
- `start_page`: Page to start from (default: 1)

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

### If You Encounter CAPTCHAs:

1. **Switch to non-headless mode** (see browser window):
   - Edit `scraper.py`
   - Change `HEADLESS_MODE = False`
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

