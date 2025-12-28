import time
import re
import gspread
from google.oauth2.service_account import Credentials

# Always import Selenium components (needed for fallback even when undetected-chromedriver is available)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Try to import undetected-chromedriver (optional, for Cloudflare bypass)
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import json
import os
import random
from pathlib import Path

# Import CAPTCHA solver (optional)
try:
    from captcha_solver import CaptchaSolver
    CAPTCHA_SOLVER_AVAILABLE = True
except ImportError:
    CAPTCHA_SOLVER_AVAILABLE = False
    CaptchaSolver = None
from urllib.parse import urljoin, urlparse

class HomeAdvisorScraper:
    def __init__(self, base_url, google_sheet_id, credentials_file=None, headless=True, captcha_api_key=None):
        # Store the base URL (can be any HomeAdvisor listing URL)
        self.base_url = base_url.split('?')[0]  # Remove any existing query parameters
        self.headless = headless
        self.using_undetected = UC_AVAILABLE  # Track if we're using undetected-chromedriver
        
        # Initialize CAPTCHA solver if API key provided
        self.captcha_solver = None
        if captcha_api_key:
            if CAPTCHA_SOLVER_AVAILABLE:
                self.captcha_solver = CaptchaSolver(api_key=captcha_api_key)
                balance = self.captcha_solver.get_balance()
                if balance is not None:
                    print(f"  2Captcha balance: ${balance:.2f}")
            else:
                print("  ⚠️  CAPTCHA solver module not available. Install requests: pip install requests")
        elif os.getenv('CAPTCHA_API_KEY'):
            # Try to get from environment variable
            if CAPTCHA_SOLVER_AVAILABLE:
                self.captcha_solver = CaptchaSolver(api_key=os.getenv('CAPTCHA_API_KEY'))
                balance = self.captcha_solver.get_balance()
                if balance is not None:
                    print(f"  2Captcha balance: ${balance:.2f}")
            else:
                print("  ⚠️  CAPTCHA solver module not available. Install requests: pip install requests")
        
        # Rotate Chrome User-Agents to appear more human-like
        # All user-agents are Chrome-based to match the browser being used
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        
        # No need for requests session - using Selenium only
        self.user_agent = random.choice(user_agents)
        
        # Setup Selenium with Chrome browser (Chrome must be installed)
        # ChromeDriver will be automatically downloaded by webdriver-manager
        chrome_options = Options()
        
        # if headless:
        #     chrome_options.add_argument('--headless=new')  # New headless mode is less detectable
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument(f'--user-agent={random.choice(user_agents)}')
        
        # Remove automation indicators
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Additional stealth options
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 1
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Initialize Chrome WebDriver
        # Use undetected-chromedriver if available (automatically bypasses Cloudflare)
        # Otherwise fall back to regular Selenium
        try:
            if UC_AVAILABLE:
                print("Using undetected-chromedriver for automatic Cloudflare bypass...")
                # Use undetected-chromedriver which automatically bypasses Cloudflare
                chrome_options_uc = uc.ChromeOptions()
                # Note: Cloudflare bypass works better in non-headless mode
                # If you encounter issues, set headless=False
                if headless:
                    chrome_options_uc.add_argument('--headless=new')
                chrome_options_uc.add_argument('--no-sandbox')
                chrome_options_uc.add_argument('--disable-dev-shm-usage')
                chrome_options_uc.add_argument('--window-size=1920,1080')
                chrome_options_uc.add_argument(f'--user-agent={random.choice(user_agents)}')
                
                # Initialize undetected Chrome (automatically handles Cloudflare Turnstile)
                # undetected-chromedriver automatically patches ChromeDriver to bypass Cloudflare
                self.driver = uc.Chrome(options=chrome_options_uc, version_main=None)
                print("Undetected ChromeDriver initialized (Cloudflare bypass enabled)")
            else:
                # Fall back to regular Selenium
                print("Note: undetected-chromedriver not available.")
                print("For automatic Cloudflare bypass, install it with: pip install undetected-chromedriver")
                print("Using regular Selenium (may require manual CAPTCHA solving)...")
                
                # Get ChromeDriver path - ChromeDriverManager sometimes returns wrong file
                try:
                    manager_path = ChromeDriverManager().install()
                    print(f"ChromeDriverManager returned: {manager_path}")
                except Exception as e:
                    print(f"Error getting ChromeDriver path: {e}")
                    raise
                
                # Determine the directory to search
                if os.path.isfile(manager_path):
                    driver_dir = os.path.dirname(manager_path)
                elif os.path.isdir(manager_path):
                    driver_dir = manager_path
                else:
                    # Path might be malformed, try to extract directory
                    driver_dir = os.path.dirname(manager_path) if os.path.dirname(manager_path) else manager_path
                
                # Normalize path separators (handle / vs \)
                driver_dir = os.path.normpath(driver_dir)
                
                # Search for chromedriver.exe
                driver_path = None
                
                # First, check the directory directly
                if os.path.isdir(driver_dir):
                    for file in os.listdir(driver_dir):
                        if file == 'chromedriver.exe':
                            driver_path = os.path.join(driver_dir, file)
                            print(f"Found ChromeDriver in directory: {driver_path}")
                            break
                
                # If not found, search subdirectories (walk through the tree)
                if not driver_path and os.path.isdir(driver_dir):
                    print(f"Searching for chromedriver.exe in: {driver_dir}")
                    for root, dirs, files in os.walk(driver_dir):
                        for file in files:
                            if file == 'chromedriver.exe':
                                driver_path = os.path.join(root, file)
                                print(f"Found ChromeDriver in subdirectory: {driver_path}")
                                break
                        if driver_path:
                            break
                
                # Also try common variations
                if not driver_path:
                    test_paths = [
                        os.path.join(driver_dir, 'chromedriver.exe'),
                        driver_dir.replace('THIRD_PARTY_NOTICES.chromedriver', 'chromedriver.exe'),
                        os.path.join(os.path.dirname(driver_dir), 'chromedriver.exe'),
                    ]
                    for test_path in test_paths:
                        if os.path.exists(test_path) and test_path.endswith('.exe'):
                            driver_path = test_path
                            print(f"Found ChromeDriver at: {driver_path}")
                            break
                
                if not driver_path or not os.path.exists(driver_path):
                    print("ChromeDriver executable not found, re-downloading...")
                    # Clear cache and try again
                    import shutil
                    from pathlib import Path
                    cache_path = Path.home() / ".wdm"
                    if cache_path.exists():
                        try:
                            shutil.rmtree(cache_path)
                            print("Cache cleared, re-downloading...")
                        except:
                            pass
                    
                    manager_path = ChromeDriverManager().install()
                    print(f"Re-download returned: {manager_path}")
                    
                    # Extract directory from the path
                    if os.path.isfile(manager_path):
                        driver_dir = os.path.dirname(manager_path)
                    elif os.path.isdir(manager_path):
                        driver_dir = manager_path
                    else:
                        # Try to find the directory
                        parts = manager_path.split(os.sep)
                        for i in range(len(parts), 0, -1):
                            test_dir = os.sep.join(parts[:i])
                            if os.path.isdir(test_dir):
                                driver_dir = test_dir
                                break
                        else:
                            driver_dir = os.path.dirname(manager_path)
                    
                    # Search for chromedriver.exe
                    if os.path.isdir(driver_dir):
                        # Search current directory and subdirectories
                        for root, dirs, files in os.walk(driver_dir):
                            for file in files:
                                if file == 'chromedriver.exe':
                                    driver_path = os.path.join(root, file)
                                    break
                            if driver_path:
                                break
                
                if not driver_path or not os.path.exists(driver_path):
                    raise Exception(f"Could not find chromedriver.exe executable.\nSearched in: {driver_dir if 'driver_dir' in locals() else 'unknown'}\nManager returned: {manager_path if 'manager_path' in locals() else 'unknown'}")
                
                if not driver_path.endswith('.exe'):
                    raise Exception(f"Invalid ChromeDriver path (not .exe): {driver_path}")
                
                print(f"Using ChromeDriver at: {driver_path}")
                
                self.driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
                print("✓ Chrome browser initialized successfully")
        except OSError as e:
            if "WinError 193" in str(e) or "not a valid Win32 application" in str(e):
                print(f"✗ Error: ChromeDriver is corrupted or wrong architecture")
                print("\nThis usually means:")
                print("  - ChromeDriver cache is corrupted")
                print("  - Architecture mismatch (32-bit vs 64-bit)")
                print("\nTo fix this, run:")
                print("  python fix_chromedriver.py")
                print("\nOr manually:")
                print("  1. Delete folder: %USERPROFILE%\\.wdm")
                print("  2. Make sure you're using 64-bit Python if you have 64-bit Chrome")
                print("  3. Re-run the script")
            else:
                print(f"✗ Error initializing Chrome browser: {e}")
            raise
        except Exception as e:
            print(f"✗ Error initializing Chrome browser: {e}")
            print("\nTroubleshooting:")
            print("1. Make sure Google Chrome is installed: https://www.google.com/chrome/")
            print("2. Run: python fix_chromedriver.py")
            print("3. Make sure Python and Chrome are both 64-bit (or both 32-bit)")
            raise
        
        # Execute script to remove webdriver property (anti-detection)
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        
        # Setup Google Sheets
        self.sheet_id = google_sheet_id
        if credentials_file and os.path.exists(credentials_file):
            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file(credentials_file, scopes=scope)
            self.gc = gspread.authorize(creds)
        else:
            # Try to use default credentials
            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file('homeadvisorelizabethscraping-613984138d99.json', scopes=scope)
            self.gc = gspread.authorize(creds)
        
        self.sheet = self.gc.open_by_key(self.sheet_id).sheet1
        
    def get_page_url(self, page_num):
        """Generate URL for a specific page"""
        if page_num == 1:
            return self.base_url
        # Check if base_url already has query parameters
        separator = '&' if '?' in self.base_url else '?'
        return f"{self.base_url}{separator}page={page_num}"
    
    def detect_total_pages(self):
        """Detect the total number of pages from the first page"""
        try:
            print("Detecting total number of pages...")
            self.driver.get(self.base_url)
            time.sleep(random.uniform(3, 5))
            
            # Wait for Cloudflare challenge if present
            self.wait_for_cloudflare_challenge()
            
            # Wait for page to load
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(2)
            except:
                pass
            
            # Look for pagination summary text like "Showing 1-10 of 1050"
            try:
                # Try to find pagination summary element
                pagination_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    '.ProList_paginationSummary__dtJGF, '
                    '[class*="pagination"], '
                    '[class*="Pagination"], '
                    'div:contains("Showing")'
                )
                
                for elem in pagination_elements:
                    text = elem.text.strip()
                    # Look for pattern like "Showing 1-10 of 1050" or "1-10 of 1050"
                    match = re.search(r'(?:Showing\s+)?\d+-\d+\s+of\s+(\d+)', text, re.IGNORECASE)
                    if match:
                        total_items = int(match.group(1))
                        # HomeAdvisor typically shows 10 items per page
                        total_pages = (total_items + 9) // 10  # Round up division
                        print(f"  Found pagination: {text}")
                        print(f"  Total items: {total_items}, Calculated pages: {total_pages}")
                        return total_pages
            except:
                pass
            
            # Alternative: Look in page text
            try:
                page_text = self.driver.page_source
                # Look for "Showing X-Y of Z" pattern
                match = re.search(r'(?:Showing\s+)?\d+-\d+\s+of\s+(\d+)', page_text, re.IGNORECASE)
                if match:
                    total_items = int(match.group(1))
                    total_pages = (total_items + 9) // 10
                    print(f"  Found in page source: Total items: {total_items}, Calculated pages: {total_pages}")
                    return total_pages
            except:
                pass
            
            # Fallback: Look for pagination links
            try:
                pagination_links = self.driver.find_elements(By.CSS_SELECTOR, 
                    'a[href*="page="], button[data-page], [class*="page"]'
                )
                max_page = 1
                for link in pagination_links:
                    href = link.get_attribute('href') or ''
                    text = link.text.strip()
                    # Extract page number from href
                    match = re.search(r'page=(\d+)', href)
                    if match:
                        page_num = int(match.group(1))
                        max_page = max(max_page, page_num)
                    # Or from text if it's a number
                    elif text.isdigit():
                        page_num = int(text)
                        max_page = max(max_page, page_num)
                
                if max_page > 1:
                    print(f"  Found pagination links: Max page number: {max_page}")
                    return max_page
            except:
                pass
            
            print("  ⚠️  Could not detect total pages, defaulting to 1 page")
            return 1
            
        except Exception as e:
            print(f"  ⚠️  Error detecting total pages: {e}")
            print("  Defaulting to 1 page")
            return 1
    
    def check_for_captcha(self):
        """Check if CAPTCHA is present on the page"""
        try:
            page_source = self.driver.page_source.lower()
            captcha_indicators = [
                'captcha',
                'recaptcha',
                'challenge',
                'verify you are human',
                'cloudflare',
                'access denied'
            ]
            return any(indicator in page_source for indicator in captcha_indicators)
        except:
            return False
    
    def wait_for_cloudflare_challenge(self, max_wait=60):
        """Wait for Cloudflare challenge (including Turnstile) to complete automatically"""
        try:
            # When using undetected-chromedriver, check for actual content first
            # (it may have already bypassed the challenge)
            if self.using_undetected:
                try:
                    # Quick check for HomeAdvisor content
                    current_url = self.driver.current_url
                    if 'homeadvisor' in current_url.lower():
                        # Look for business listings or profile content
                        has_content = any([
                            self.driver.find_elements(By.CSS_SELECTOR, 'article.ProList_businessProCard__qvaeT'),
                            self.driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="business-info"]'),
                            self.driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="contact-information-component"]'),
                            self.driver.find_elements(By.CSS_SELECTOR, 'h1, h2, h3'),
                            self.driver.find_elements(By.CSS_SELECTOR, 'div.ProList_paginationSummary__dtJGF')
                        ])
                        if has_content:
                            # Content found, challenge likely already bypassed
                            return True
                except:
                    pass
            
            # Check if we're on a Cloudflare challenge page
            page_source = self.driver.page_source.lower()
            current_url = self.driver.current_url
            
            is_cloudflare = any(indicator in page_source for indicator in [
                'just a moment',
                'cloudflare',
                'verify you are human',
                'checking your browser',
                'cf-turnstile',
                'challenges.cloudflare.com'
            ])
            
            if not is_cloudflare:
                return True  # Not a Cloudflare page, proceed
            
            print("  ⏳ Cloudflare challenge detected...")
            
            # When using undetected-chromedriver, reduce wait time and check more frequently
            if self.using_undetected:
                max_wait = min(max_wait, 30)  # Shorter timeout for undetected-chromedriver
                check_interval = 2  # Check every 2 seconds instead of 5
            else:
                check_interval = 5
            
            # Try to solve Turnstile CAPTCHA automatically if solver is available
            if self.captcha_solver and self.captcha_solver.enabled:
                try:
                    # Look for Turnstile widget
                    turnstile_widgets = self.driver.find_elements(By.CSS_SELECTOR, 
                        'div[class*="cf-turnstile"], '
                        'iframe[src*="challenges.cloudflare.com/turnstile"], '
                        '[data-sitekey]'
                    )
                    
                    for widget in turnstile_widgets:
                        # Try to get site key from data-sitekey attribute
                        site_key = widget.get_attribute('data-sitekey')
                        if not site_key:
                            # Try to find it in the iframe src or nearby elements
                            try:
                                iframe = widget.find_element(By.TAG_NAME, 'iframe')
                                iframe_src = iframe.get_attribute('src')
                                # Extract site key from iframe src or page source
                                match = re.search(r'sitekey=([^&]+)', iframe_src or '')
                                if match:
                                    site_key = match.group(1)
                            except:
                                pass
                        
                        # Also try to find site key in page source
                        if not site_key:
                            page_source_full = self.driver.page_source
                            match = re.search(r'data-sitekey=["\']([^"\']+)["\']', page_source_full)
                            if match:
                                site_key = match.group(1)
                        
                        if site_key:
                            print(f"  🔍 Found Turnstile site key: {site_key[:20]}...")
                            token = self.captcha_solver.solve_cloudflare_turnstile(site_key, current_url)
                            
                            if token:
                                # Inject the token into the page
                                try:
                                    # Execute JavaScript to set the token
                                    script = f"""
                                    // Find the Turnstile widget and set the token
                                    var widgets = document.querySelectorAll('[data-sitekey], iframe[src*="turnstile"]');
                                    for (var i = 0; i < widgets.length; i++) {{
                                        var widget = widgets[i];
                                        var input = widget.closest('form') ? 
                                            widget.closest('form').querySelector('input[name="cf-turnstile-response"]') :
                                            document.querySelector('input[name="cf-turnstile-response"]');
                                        if (input) {{
                                            input.value = '{token}';
                                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        }}
                                    }}
                                    
                                    // Also try to call the callback if it exists
                                    if (window.turnstile) {{
                                        var widgets = document.querySelectorAll('[data-sitekey]');
                                        widgets.forEach(function(widget) {{
                                            var sitekey = widget.getAttribute('data-sitekey');
                                            if (sitekey) {{
                                                try {{
                                                    window.turnstile.render(widget, {{
                                                        sitekey: sitekey,
                                                        callback: function(token) {{
                                                            // Token callback
                                                        }}
                                                    }});
                                                }} catch(e) {{
                                                    // Ignore errors
                                                }}
                                            }}
                                        }});
                                    }}
                                    """
                                    self.driver.execute_script(script)
                                    print("  ✓ Token injected, waiting for page to process...")
                                    time.sleep(3)
                                except Exception as e:
                                    print(f"  ⚠️  Could not inject token: {e}")
                            
                            break  # Only solve the first widget found
                except Exception as e:
                    print(f"  ⚠️  Error attempting automatic CAPTCHA solve: {e}")
                    print("  Falling back to waiting for automatic completion...")
            
            print("  ⏳ Waiting for Cloudflare challenge to complete...")
            if self.using_undetected:
                print("  (Using undetected-chromedriver - checking for content...)")
            
            # Wait for the challenge to complete
            start_time = time.time()
            last_status = ""
            
            while time.time() - start_time < max_wait:
                try:
                    current_url = self.driver.current_url
                    page_source = self.driver.page_source.lower()
                    
                    # When using undetected-chromedriver, prioritize checking for content
                    if self.using_undetected:
                        try:
                            if 'homeadvisor' in current_url.lower():
                                has_content = any([
                                    self.driver.find_elements(By.CSS_SELECTOR, 'article.ProList_businessProCard__qvaeT'),
                                    self.driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="business-info"]'),
                                    self.driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="contact-information-component"]'),
                                    self.driver.find_elements(By.CSS_SELECTOR, 'div.ProList_paginationSummary__dtJGF'),
                                    self.driver.find_elements(By.CSS_SELECTOR, 'section#pro-list-container')
                                ])
                                if has_content:
                                    print("  ✓ Cloudflare challenge completed! (Content detected)")
                                    time.sleep(1)
                                    return True
                        except:
                            pass
                    
                    # Check for Turnstile widget completion
                    try:
                        # Check if Turnstile iframe is present
                        turnstile_iframes = self.driver.find_elements(By.CSS_SELECTOR, 
                            'iframe[src*="challenges.cloudflare.com"], '
                            'iframe[id*="cf-chl-widget"], '
                            'iframe[title*="Cloudflare security challenge"]'
                        )
                        
                        # Check if Turnstile response token is present (means challenge completed)
                        turnstile_response = self.driver.find_elements(By.CSS_SELECTOR, 
                            'input[name="cf-turnstile-response"][value], '
                            'input[id*="cf-chl-widget"][id*="_response"][value]'
                        )
                        
                        # If we have a response token, challenge likely completed
                        if turnstile_response:
                            response_value = turnstile_response[0].get_attribute('value')
                            if response_value and len(response_value) > 10:  # Valid token
                                print("  ✓ Turnstile challenge token received, waiting for redirect...")
                                time.sleep(3)  # Wait for redirect
                                # Check if we're past the challenge
                                page_source_after = self.driver.page_source.lower()
                                if not any(indicator in page_source_after for indicator in [
                                    'just a moment',
                                    'verify you are human',
                                    'checking your browser'
                                ]):
                                    print("  ✓ Cloudflare challenge completed!")
                                    time.sleep(2)
                                    return True
                    except:
                        pass
                    
                    # Check if challenge is complete (we're no longer on challenge page)
                    if not any(indicator in page_source for indicator in [
                        'just a moment',
                        'verify you are human',
                        'checking your browser'
                    ]):
                        # Check if we can find HomeAdvisor content
                        try:
                            # Try to find HomeAdvisor-specific elements
                            self.driver.find_element(By.TAG_NAME, 'body')
                            # Check for actual content, not just challenge page
                            if 'homeadvisor' in current_url.lower():
                                # Look for business listings or profile content
                                has_content = any([
                                    self.driver.find_elements(By.CSS_SELECTOR, 'article.ProList_businessProCard__qvaeT'),
                                    self.driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="business-info"]'),
                                    self.driver.find_elements(By.CSS_SELECTOR, 'h1, h2, h3')
                                ])
                                if has_content:
                                    print("  ✓ Cloudflare challenge completed!")
                                    time.sleep(2)  # Give page a moment to fully load
                                    return True
                        except:
                            pass
                    
                    # Show progress every check_interval seconds
                    elapsed = int(time.time() - start_time)
                    if elapsed % check_interval == 0 and elapsed != 0 and elapsed != last_status:
                        print(f"  ⏳ Still waiting... ({elapsed}s/{max_wait}s)")
                        last_status = elapsed
                    
                    time.sleep(check_interval)  # Wait before next check
                    
                except Exception as e:
                    # If we get an error, might mean page changed
                    time.sleep(1)
                    continue
            
            # Final check if challenge passed
            try:
                page_source = self.driver.page_source.lower()
                current_url = self.driver.current_url
                
                # Check if we're past the challenge
                if not any(indicator in page_source for indicator in [
                    'just a moment',
                    'verify you are human',
                    'checking your browser'
                ]):
                    # Verify we have actual content
                    if 'homeadvisor' in current_url.lower():
                        has_content = any([
                            self.driver.find_elements(By.CSS_SELECTOR, 'article.ProList_businessProCard__qvaeT'),
                            self.driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="business-info"]'),
                            self.driver.find_elements(By.CSS_SELECTOR, 'body')
                        ])
                        if has_content:
                            print("  ✓ Cloudflare challenge completed!")
                            return True
                
                print("  ⚠️  Cloudflare challenge did not complete automatically")
                print("  This may require manual intervention or using undetected-chromedriver")
                if not self.headless:
                    print("  Please solve the challenge manually in the browser...")
                    input("  Press Enter after solving the challenge to continue...")
                    return True
                return False
            except:
                return False
                
        except Exception as e:
            print(f"  Error waiting for Cloudflare challenge: {e}")
            return False
    
    def scrape_listings_from_page(self, page_num):
        """Scrape all business listings from a single page"""
        url = self.get_page_url(page_num)
        print(f"Scraping page {page_num}: {url}")
        
        try:
            # Use Selenium for JavaScript rendering
            self.driver.get(url)
            
            # Random delay to appear more human-like (3-7 seconds)
            time.sleep(random.uniform(3, 7))
            
            # Wait for Cloudflare challenge if present
            if not self.wait_for_cloudflare_challenge():
                print(f"⚠️  Cloudflare challenge not resolved on page {page_num}, skipping...")
                return []
            
            # Check for other CAPTCHAs
            if self.check_for_captcha():
                # If it's not Cloudflare, it might be a different CAPTCHA
                page_source = self.driver.page_source.lower()
                if 'cloudflare' not in page_source:
                    print(f"⚠️  CAPTCHA detected on page {page_num}!")
                    if self.headless:
                        print("   Running in headless mode. Switch to non-headless mode to solve CAPTCHA manually.")
                        print("   Edit scraper.py and set headless=False in HomeAdvisorScraper()")
                        return []
                    else:
                        print("   Please solve the CAPTCHA manually in the browser window...")
                        input("   Press Enter after solving the CAPTCHA to continue...")
            
            # Wait for listings to appear - wait for specific HomeAdvisor elements
            try:
                # Wait for business listings to load
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/pro/'], div[class*='result'], div[class*='listing'], article"))
                )
                # Additional wait for dynamic content
                time.sleep(3)
            except:
                print("Warning: Timeout waiting for page elements, proceeding anyway...")
            
            # Scroll to load more content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Debug: Save HTML for inspection (only on first page)
            if page_num == 1:
                try:
                    html = self.driver.page_source
                    with open('debug_page1.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    print("Debug: Saved page HTML to debug_page1.html")
                except:
                    pass
            
            listings = []
            
            # Use Selenium to find business listing cards
            # Strategy: Find all article elements with the business card class name
            try:
                # Find article tags with the specific class name (ProList_businessProCard__qvaeT)
                # The article has class: "ProList_businessProCard__qvaeT  BusinessProfileCard_parentContainer__5_Ak0"
                business_cards = self.driver.find_elements(By.CSS_SELECTOR, 'article.ProList_businessProCard__qvaeT')
                
                # Alternative: If the above doesn't work, try XPath or class name directly
                if not business_cards or len(business_cards) == 0:
                    # Try XPath with article tag and class
                    business_cards = self.driver.find_elements(By.XPATH, '//article[contains(@class, "ProList_businessProCard__qvaeT")]')
                
                if not business_cards or len(business_cards) == 0:
                    # Fallback: try finding by class name (but this might return non-article elements)
                    business_cards = self.driver.find_elements(By.CLASS_NAME, 'ProList_businessProCard__qvaeT')
                    # Filter to only article elements
                    business_cards = [card for card in business_cards if card.tag_name == 'article']
                
                seen_urls = set()
                seen_names = set()
                for card in business_cards:
                    try:
                        # Extract business data from the card
                        business_data = self.extract_business_info_from_card(card)
                        
                        if business_data and business_data.get('business_name'):
                            business_name = business_data.get('business_name')
                            profile_url = business_data.get('profile_url', '')
                            
                            # Use business name as unique identifier if no profile URL
                            unique_id = profile_url if profile_url else business_name
                            
                            # Only add if we haven't seen this business before
                            if unique_id not in seen_urls and business_name not in seen_names:
                                seen_urls.add(unique_id)
                                seen_names.add(business_name)
                                listings.append(business_data)
                            
                    except Exception as e:
                        print(f"  Error processing card: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error finding listings with Selenium: {e}")
            
            print(f"Found {len(listings)} listings on page {page_num}")
            
            # If no listings found, wait a bit longer and check again (might be slow loading)
            if len(listings) == 0:
                print(f"  ⚠️  No listings found, waiting longer for page to load...")
                time.sleep(5)
                # Try one more time with a longer wait
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "article.ProList_businessProCard__qvaeT, body"))
                    )
                    time.sleep(3)
                    # Try finding listings again
                    business_cards = self.driver.find_elements(By.CSS_SELECTOR, 'article.ProList_businessProCard__qvaeT')
                    if business_cards:
                        print(f"  Retrying extraction after longer wait...")
                        seen_urls = set()
                        seen_names = set()
                        for card in business_cards:
                            try:
                                business_data = self.extract_business_info_from_card(card)
                                if business_data and business_data.get('business_name'):
                                    business_name = business_data.get('business_name')
                                    profile_url = business_data.get('profile_url', '')
                                    
                                    # Use business name as unique identifier if no profile URL
                                    unique_id = profile_url if profile_url else business_name
                                    
                                    # Only add if we haven't seen this business before
                                    if unique_id not in seen_urls and business_name not in seen_names:
                                        seen_urls.add(unique_id)
                                        seen_names.add(business_name)
                                        listings.append(business_data)
                            except Exception as e:
                                print(f"  Error processing card: {e}")
                                continue
                        print(f"  Found {len(listings)} listings after retry")
                except:
                    pass
            
            return listings
            
        except Exception as e:
            print(f"Error scraping page {page_num}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def extract_business_info_from_card(self, card_element):
        """Extract business information from a business card element on the listing page"""
        data = {
            'business_name': '',
            'star_rating': '',
            'num_reviews': '',
            'address': '',
            'website': '',
            'phone': '',
            'email': '',
            'profile_url': ''
        }
        
        try:
            # Extract business name - try desktop first, then mobile, then fallbacks
            try:
                name_elem = card_element.find_element(By.CSS_SELECTOR, 'h3[data-testid="business-name-desktop"]')
                data['business_name'] = name_elem.text.strip()
            except:
                try:
                    name_elem = card_element.find_element(By.CSS_SELECTOR, 'h3[data-testid="business-name-mobile"]')
                    data['business_name'] = name_elem.text.strip()
                except:
                    # Fallback: try any h3 with BusinessProfileCard_header class
                    try:
                        name_elem = card_element.find_element(By.CSS_SELECTOR, 'h3.BusinessProfileCard_header__srI3D')
                        data['business_name'] = name_elem.text.strip()
                    except:
                        # Last resort: try aria-label from profile link
                        try:
                            profile_link = card_element.find_element(By.CSS_SELECTOR, 'a[data-testid="profile-link"]')
                            aria_label = profile_link.get_attribute('aria-label')
                            if aria_label:
                                # Extract name from aria-label like "AK Aire, LLC profile (opens in new tab)"
                                import re
                                match = re.search(r'^([^(]+)', aria_label)
                                if match:
                                    data['business_name'] = match.group(1).strip()
                        except:
                            pass
            
            # Extract profile URL - try multiple selectors
            try:
                profile_link = card_element.find_element(By.CSS_SELECTOR, 'a[data-testid="profile-link"]')
                href = profile_link.get_attribute('href')
                if href:
                    data['profile_url'] = href
            except:
                # Fallback: try href attribute with "rated" in it
                try:
                    profile_link = card_element.find_element(By.CSS_SELECTOR, 'a[href*="rated"], a[href*="/pro/"]')
                    href = profile_link.get_attribute('href')
                    if href and ('rated' in href or '/pro/' in href):
                        # Make sure it's a full URL
                        if not href.startswith('http'):
                            if href.startswith('/'):
                                href = 'https://www.homeadvisor.com' + href
                            else:
                                href = 'https://www.homeadvisor.com/' + href
                        data['profile_url'] = href
                except:
                    # Try to find profile URL from JSON-LD structured data
                    try:
                        # Get the page source and look for JSON-LD with this business name
                        page_source = self.driver.page_source
                        import json
                        import re
                        
                        # Find all JSON-LD script tags
                        json_ld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
                        matches = re.findall(json_ld_pattern, page_source, re.DOTALL | re.IGNORECASE)
                        
                        business_name_lower = data['business_name'].lower() if data['business_name'] else ''
                        
                        for json_text in matches:
                            try:
                                json_data = json.loads(json_text)
                                
                                # Look for the business in the JSON structure
                                def find_business_in_json(obj, target_name):
                                    """Recursively search for business data in JSON"""
                                    if isinstance(obj, dict):
                                        # Check if this is a business object with matching name
                                        if '@type' in obj:
                                            obj_type = str(obj.get('@type', ''))
                                            if 'HomeAndConstructionBusiness' in obj_type or 'LocalBusiness' in obj_type:
                                                if 'name' in obj and target_name.lower() in obj['name'].lower():
                                                    if 'url' in obj:
                                                        url = obj['url']
                                                        if url and ('rated' in url or '/pro/' in url):
                                                            return url
                                        # Check itemListElement for businesses
                                        if 'itemListElement' in obj:
                                            for item in obj['itemListElement']:
                                                if 'item' in item:
                                                    result = find_business_in_json(item['item'], target_name)
                                                    if result:
                                                        return result
                                        # Recursively search all values
                                        for value in obj.values():
                                            result = find_business_in_json(value, target_name)
                                            if result:
                                                return result
                                    elif isinstance(obj, list):
                                        for item in obj:
                                            result = find_business_in_json(item, target_name)
                                            if result:
                                                return result
                                    return None
                                
                                if business_name_lower:
                                    profile_url = find_business_in_json(json_data, business_name_lower)
                                    if profile_url:
                                        # Make sure it's a full URL
                                        if not profile_url.startswith('http'):
                                            if profile_url.startswith('/'):
                                                profile_url = 'https://www.homeadvisor.com' + profile_url
                                            else:
                                                profile_url = 'https://www.homeadvisor.com/' + profile_url
                                        data['profile_url'] = profile_url
                                        break
                            except:
                                continue
                    except:
                        pass
            
            # Extract star rating
            try:
                # Try desktop rating first
                try:
                    rating_elem = card_element.find_element(By.CSS_SELECTOR, 'div[data-testid="star-rating-desktop"] span.RatingsLockup_ratingNumber__2CoLI')
                    rating_text = rating_elem.text.strip()
                    if not rating_text:
                        # Try getting textContent or innerText
                        rating_text = rating_elem.get_attribute('textContent') or rating_elem.get_attribute('innerText')
                    if rating_text:
                        data['star_rating'] = rating_text.strip()
                except:
                    # Try mobile rating
                    try:
                        rating_elem = card_element.find_element(By.CSS_SELECTOR, 'div[data-testid="star-rating-mobile"] span.RatingsLockup_ratingNumber__2CoLI')
                        rating_text = rating_elem.text.strip()
                        if not rating_text:
                            rating_text = rating_elem.get_attribute('textContent') or rating_elem.get_attribute('innerText')
                        if rating_text:
                            data['star_rating'] = rating_text.strip()
                    except:
                        # Fallback: try without data-testid
                        try:
                            rating_elem = card_element.find_element(By.CSS_SELECTOR, 'span.RatingsLockup_ratingNumber__2CoLI')
                            rating_text = rating_elem.text.strip()
                            if not rating_text:
                                rating_text = rating_elem.get_attribute('textContent') or rating_elem.get_attribute('innerText')
                            if rating_text:
                                data['star_rating'] = rating_text.strip()
                        except:
                            # Last resort: extract from aria-label
                            try:
                                rating_container = card_element.find_element(By.CSS_SELECTOR, 'div[aria-label*="Rating:"]')
                                aria_label = rating_container.get_attribute('aria-label')
                                if aria_label:
                                    import re
                                    match = re.search(r'Rating:\s*([\d.]+)', aria_label)
                                    if match:
                                        data['star_rating'] = match.group(1)
                            except:
                                pass
            except:
                pass
            
            # Extract number of reviews - handle "No reviews yet" cases
            try:
                # First check if there's "No reviews yet" text
                card_text = card_element.text.lower()
                if 'no reviews yet' in card_text:
                    data['num_reviews'] = '0'
                    # Also set star_rating to empty if not found
                    if not data['star_rating']:
                        data['star_rating'] = ''
                else:
                    # Try desktop reviews first
                    try:
                        reviews_elem = card_element.find_element(By.CSS_SELECTOR, 'div[data-testid="star-rating-desktop"] span.RatingsLockup_reviewCount__u0DTP')
                        # The number is inside a div
                        review_div = reviews_elem.find_element(By.TAG_NAME, 'div')
                        reviews_text = review_div.text.strip()
                        if not reviews_text:
                            reviews_text = review_div.get_attribute('textContent') or review_div.get_attribute('innerText')
                        # Remove parentheses if present
                        if reviews_text:
                            reviews_text = reviews_text.strip('()')
                            # Check if it's a number
                            if reviews_text.isdigit():
                                data['num_reviews'] = reviews_text.strip()
                    except:
                        # Try mobile reviews
                        try:
                            reviews_elem = card_element.find_element(By.CSS_SELECTOR, 'div[data-testid="star-rating-mobile"] span.RatingsLockup_reviewCount__u0DTP')
                            review_div = reviews_elem.find_element(By.TAG_NAME, 'div')
                            reviews_text = review_div.text.strip()
                            if not reviews_text:
                                reviews_text = review_div.get_attribute('textContent') or review_div.get_attribute('innerText')
                            if reviews_text:
                                reviews_text = reviews_text.strip('()')
                                # Check if it's a number
                                if reviews_text.isdigit():
                                    data['num_reviews'] = reviews_text.strip()
                        except:
                            # Fallback: try without data-testid
                            try:
                                reviews_elem = card_element.find_element(By.CSS_SELECTOR, 'span.RatingsLockup_reviewCount__u0DTP')
                                review_div = reviews_elem.find_element(By.TAG_NAME, 'div')
                                reviews_text = review_div.text.strip()
                                if not reviews_text:
                                    reviews_text = review_div.get_attribute('textContent') or review_div.get_attribute('innerText')
                                if reviews_text:
                                    reviews_text = reviews_text.strip('()')
                                    # Check if it's a number
                                    if reviews_text.isdigit():
                                        data['num_reviews'] = reviews_text.strip()
                            except:
                                pass
            except:
                pass
            
            # Try to extract profile URL from JSON-LD structured data if not found yet
            if not data['profile_url']:
                try:
                    # Look for JSON-LD script tag in the page (might be at page level, not card level)
                    # First try to find it in the card's parent or siblings
                    try:
                        # Get the page source and look for JSON-LD with this business name
                        page_source = self.driver.page_source
                        import json
                        import re
                        
                        # Find all JSON-LD script tags
                        json_ld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
                        matches = re.findall(json_ld_pattern, page_source, re.DOTALL | re.IGNORECASE)
                        
                        for json_text in matches:
                            try:
                                json_data = json.loads(json_text)
                                # Check if this JSON contains the business name
                                business_name_lower = data['business_name'].lower() if data['business_name'] else ''
                                
                                # Look for the business in the JSON structure
                                def find_business_in_json(obj, target_name):
                                    """Recursively search for business data in JSON"""
                                    if isinstance(obj, dict):
                                        # Check if this is a business object with matching name
                                        if '@type' in obj and 'HomeAndConstructionBusiness' in str(obj.get('@type', '')):
                                            if 'name' in obj and target_name.lower() in obj['name'].lower():
                                                if 'url' in obj:
                                                    return obj['url']
                                        # Check itemListElement for businesses
                                        if 'itemListElement' in obj:
                                            for item in obj['itemListElement']:
                                                if 'item' in item:
                                                    result = find_business_in_json(item['item'], target_name)
                                                    if result:
                                                        return result
                                        # Recursively search all values
                                        for value in obj.values():
                                            result = find_business_in_json(value, target_name)
                                            if result:
                                                return result
                                    elif isinstance(obj, list):
                                        for item in obj:
                                            result = find_business_in_json(item, target_name)
                                            if result:
                                                return result
                                    return None
                                
                                if business_name_lower:
                                    profile_url = find_business_in_json(json_data, business_name_lower)
                                    if profile_url:
                                        # Make sure it's a full URL
                                        if not profile_url.startswith('http'):
                                            if profile_url.startswith('/'):
                                                profile_url = 'https://www.homeadvisor.com' + profile_url
                                            else:
                                                profile_url = 'https://www.homeadvisor.com/' + profile_url
                                        data['profile_url'] = profile_url
                                        break
                            except:
                                continue
                    except:
                        pass
                except:
                    pass
            
            # Extract address from JSON-LD structured data if available
            try:
                # Look for JSON-LD script tag in the card
                script_tags = card_element.find_elements(By.TAG_NAME, 'script')
                for script in script_tags:
                    script_type = script.get_attribute('type')
                    if script_type == 'application/ld+json':
                        import json
                        json_text = script.get_attribute('innerHTML')
                        if json_text:
                            json_data = json.loads(json_text)
                            # Navigate through the JSON structure to find address
                            if '@type' in json_data and json_data['@type'] == 'SearchResultsPage':
                                if 'mainEntity' in json_data and 'itemListElement' in json_data['mainEntity']:
                                    # This is the page-level JSON, not individual business
                                    pass
            except:
                pass
            
            # Address might not be on listing page - will get from profile page
            
        except Exception as e:
            print(f"  Error extracting info from card: {e}")
        
        return data
    
    def extract_business_info(self, container):
        """Extract business information from a listing container"""
        data = {
            'business_name': '',
            'star_rating': '',
            'num_reviews': '',
            'address': '',
            'website': '',
            'phone': '',
            'email': ''
        }
        
        container_text = container.get_text()
        
        # Extract business name and profile URL - multiple strategies
        # Strategy 1: Look for /pro/ or /rated. links (most reliable)
        pro_link = container.find('a', href=re.compile(r'/pro/|/rated\.', re.I))
        if pro_link:
            name_text = pro_link.get_text(strip=True)
            # Filter out promotional text
            if name_text and not any(skip in name_text.lower() for skip in ['join', 'sign up', 'become', 'register']):
                data['business_name'] = name_text
                
            # Extract profile URL
            href = pro_link.get('href', '')
            if href:
                if href.startswith('/'):
                    data['profile_url'] = urljoin('https://www.homeadvisor.com', href)
                elif href.startswith('http'):
                    data['profile_url'] = href
                else:
                    data['profile_url'] = urljoin('https://www.homeadvisor.com', href)
        
        # Strategy 2: Look for headings
        if not data['business_name']:
            for tag in ['h1', 'h2', 'h3', 'h4']:
                name_elem = container.find(tag)
                if name_elem:
                    name_text = name_elem.get_text(strip=True)
                    if name_text and len(name_text) > 2 and len(name_text) < 100:
                        data['business_name'] = name_text
                        break
        
        # Strategy 3: Look for strong/bold text at the beginning
        if not data['business_name']:
            strong_elem = container.find(['strong', 'b'])
            if strong_elem:
                name_text = strong_elem.get_text(strip=True)
                if name_text and len(name_text) > 2 and len(name_text) < 100:
                    data['business_name'] = name_text
        
        # Extract star rating - look for patterns like "4.5 stars" or "★★★★"
        rating_patterns = [
            r'(\d+\.?\d*)\s*[Ss]tar',
            r'(\d+\.?\d*)\s*out\s*of\s*\d+',
            r'Rating[:\s]*(\d+\.?\d*)',
        ]
        for pattern in rating_patterns:
            match = re.search(pattern, container_text)
            if match:
                data['star_rating'] = match.group(1)
                break
        
        # Extract number of reviews
        reviews_patterns = [
            r'(\d+(?:,\d+)*)\s*[Rr]eview',
            r'(\d+(?:,\d+)*)\s*[Rr]ating',
        ]
        for pattern in reviews_patterns:
            match = re.search(pattern, container_text)
            if match:
                data['num_reviews'] = match.group(1).replace(',', '')
                break
        
        # Extract address - look for address patterns
        address_patterns = [
            r'\d+\s+[A-Za-z0-9\s,]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl)[\s,]+[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}',
            r'[A-Za-z0-9\s,]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl)[\s,]+[A-Za-z\s]+,\s*[A-Z]{2}',
        ]
        for pattern in address_patterns:
            match = re.search(pattern, container_text)
            if match:
                data['address'] = match.group(0).strip()
                break
        
        # If no pattern match, try to find address element
        if not data['address']:
            address_elem = container.find(['span', 'div', 'p'], class_=re.compile(r'(address|location|city)', re.I))
            if not address_elem:
                address_elem = container.find('address')
            if address_elem:
                addr_text = address_elem.get_text(strip=True)
                if addr_text and len(addr_text) > 10:
                    data['address'] = addr_text
        
        # Extract website URL - look for external links
        website_links = container.find_all('a', href=re.compile(r'^https?://', re.I))
        for link in website_links:
            href = link.get('href', '')
            # Skip HomeAdvisor links and common social media
            if href and not any(skip in href.lower() for skip in ['homeadvisor.com', 'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com']):
                data['website'] = href
                break
        
        # If no external link found, the website might be on the business profile page
        # We'll need to visit the /pro/ link to get it
        
        return data
    
    def find_phone_on_website(self, url):
        """Search for phone number on a business website"""
        if not url or not url.startswith('http'):
            return None
        
        try:
            print(f"  Searching for phone on: {url}")
            # Random delay before request
            time.sleep(random.uniform(1, 3))
            
            # Use Selenium to visit the website
            self.driver.get(url)
            time.sleep(random.uniform(2, 4))
            
            # Check for CAPTCHA
            if self.check_for_captcha():
                print("  ⚠️  CAPTCHA detected on website, skipping...")
                return None
            
            # Get page text using Selenium
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            # Common phone number patterns
            phone_patterns = [
                r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (123) 456-7890
                r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',        # 123-456-7890
                r'\+?1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # +1 (123) 456-7890
            ]
            
            for pattern in phone_patterns:
                matches = re.findall(pattern, page_text)
                if matches:
                    # Clean up the phone number
                    phone = re.sub(r'[^\d]', '', matches[0])
                    if len(phone) == 10 or (len(phone) == 11 and phone[0] == '1'):
                        if len(phone) == 11:
                            phone = phone[1:]
                        return f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
            
            return None
            
        except Exception as e:
            print(f"  Error searching website {url}: {e}")
            return None
    
    def find_email_on_website(self, url):
        """Search for email address on a business website using Selenium"""
        if not url or not url.startswith('http'):
            return None
        
        try:
            # Use Selenium to visit the website (if not already there)
            current_url = self.driver.current_url
            if current_url != url:
                self.driver.get(url)
                time.sleep(random.uniform(2, 4))
            
            # Get page text using Selenium
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            # Email pattern
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            matches = re.findall(email_pattern, page_text)
            
            # Filter out common non-business emails
            filtered = [e for e in matches if not any(x in e.lower() for x in ['example.com', 'test.com', 'placeholder'])]
            
            if filtered:
                return filtered[0]
            
            return None
            
        except Exception as e:
            print(f"  Error finding email on {url}: {e}")
            return None
    
    def search_google_for_phone(self, business_name, address):
        """Search Google for business phone number"""
        try:
            query = f"{business_name} {address} phone number"
            from urllib.parse import quote
            google_url = f"https://www.google.com/search?q={quote(query)}"
            
            print(f"  Searching Google for phone: {query}")
            
            self.driver.get(google_url)
            # Random delay to appear more human-like
            time.sleep(random.uniform(2, 4))
            
            # Check for CAPTCHA on Google
            if self.check_for_captcha():
                print("  ⚠️  CAPTCHA detected on Google search, skipping...")
                return None
            
            # Get page text using Selenium
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            # Look for phone numbers in the results
            phone_patterns = [
                r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
            ]
            
            for pattern in phone_patterns:
                matches = re.findall(pattern, page_text)
                if matches:
                    phone = re.sub(r'[^\d]', '', matches[0])
                    if len(phone) == 10 or (len(phone) == 11 and phone[0] == '1'):
                        if len(phone) == 11:
                            phone = phone[1:]
                        return f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
            
            return None
            
        except Exception as e:
            print(f"  Error searching Google: {e}")
            return None
    
    def get_data_from_profile_page(self, profile_url):
        """Extract all data from a business profile page using specific selectors"""
        data = {
            'website': '',
            'phone': '',
            'address': '',
            'star_rating': '',
            'num_reviews': ''
        }
        
        try:
            print(f"  Visiting profile page: {profile_url}")
            self.driver.get(profile_url)
            time.sleep(random.uniform(3, 5))
            
            # Wait for Cloudflare challenge if present
            if not self.wait_for_cloudflare_challenge():
                print("  ⚠️  Cloudflare challenge not resolved, skipping...")
                return data
            
            # Check for other CAPTCHAs
            if self.check_for_captcha():
                # If it's not Cloudflare, it might be a different CAPTCHA
                page_source = self.driver.page_source.lower()
                if 'cloudflare' not in page_source:
                    print("  ⚠️  CAPTCHA detected on profile page, skipping...")
                    if not self.headless:
                        print("  Please solve the CAPTCHA manually...")
                        input("  Press Enter after solving to continue...")
                    else:
                        return data
            
            # Don't extract rating and reviews from profile page - already have them from listing page
            # This prevents duplication
            # Rating and reviews are already extracted from the listing card
            
            # Extract address - from contact information section
            try:
                # Look for address in h3 with class SubComponents_subHeader__JUXIF within contact information
                address_elem = self.driver.find_element(By.CSS_SELECTOR, 
                    'div[data-testid="contact-information-component"] h3.SubComponents_subHeader__JUXIF'
                )
                address_text = address_elem.text.strip()
                if address_text and len(address_text) > 10:
                    data['address'] = address_text
            except:
                # Fallback: try without data-testid
                try:
                    address_elem = self.driver.find_element(By.CSS_SELECTOR, 'h3.SubComponents_subHeader__JUXIF')
                    address_text = address_elem.text.strip()
                    if address_text and len(address_text) > 10:
                        data['address'] = address_text
                except:
                    pass
            
            # Extract website - from contact information section
            try:
                # Look for website link in a tag with class SubComponents_link__Gpwoa within contact information
                website_link = self.driver.find_element(By.CSS_SELECTOR, 
                    'div[data-testid="contact-information-component"] a.SubComponents_link__Gpwoa'
                )
                href = website_link.get_attribute('href')
                if href and href.startswith('http') and not any(skip in href.lower() for skip in [
                    'homeadvisor.com', 'facebook.com', 'twitter.com', 
                    'linkedin.com', 'instagram.com', 'youtube.com', 'pinterest.com'
                ]):
                    data['website'] = href
            except:
                # Fallback: try without data-testid
                try:
                    website_link = self.driver.find_element(By.CSS_SELECTOR, 'a.SubComponents_link__Gpwoa')
                    href = website_link.get_attribute('href')
                    if href and href.startswith('http') and not any(skip in href.lower() for skip in [
                        'homeadvisor.com', 'facebook.com', 'twitter.com', 
                        'linkedin.com', 'instagram.com', 'youtube.com', 'pinterest.com'
                    ]):
                        data['website'] = href
                except:
                    pass
            
            # Extract phone number - click the button with id="view-phone-number"
            # Try multiple selectors and wait for button to appear
            phone_button = None
            try:
                # Wait for button to appear with multiple selector strategies
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                
                wait = WebDriverWait(self.driver, 10)
                
                # Try multiple selectors
                selectors = [
                    (By.ID, "view-phone-number"),
                    (By.CSS_SELECTOR, "button#view-phone-number"),
                    (By.CSS_SELECTOR, "[id='view-phone-number']"),
                    (By.XPATH, "//button[@id='view-phone-number']"),
                    (By.XPATH, "//button[contains(@aria-label, 'phone') or contains(@aria-label, 'Phone')]"),
                    (By.XPATH, "//button[contains(text(), 'Phone') or contains(text(), 'phone')]"),
                    (By.CSS_SELECTOR, "button[data-testid*='phone']"),
                    (By.CSS_SELECTOR, "a[href*='phone']"),
                ]
                
                for selector_type, selector_value in selectors:
                    try:
                        phone_button = wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                        if phone_button:
                            print(f"  Found phone button using {selector_type}: {selector_value}")
                            break
                    except:
                        continue
                
                if phone_button:
                    print("  Clicking 'Phone number' button...")
                    # Scroll to button first
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", phone_button)
                    time.sleep(1)
                    # Click using JavaScript to avoid interception
                    self.driver.execute_script("arguments[0].click();", phone_button)
                    time.sleep(2)  # Wait for phone number to appear
                    
                    # Now extract the phone number from the button that appears after clicking
                    try:
                        # Look for the phone button with data-testid="angi_button" and class containing BusinessProfileHero_phoneNumber
                        phone_button_after = self.driver.find_element(By.CSS_SELECTOR, 
                            'button[data-testid="angi_button"][class*="BusinessProfileHero_phoneNumber"], '
                            'button[class*="BusinessProfileHero_phoneNumber"]'
                        )
                        
                        # Try to get phone from name attribute first (most reliable)
                        phone_name = phone_button_after.get_attribute('name')
                        if phone_name:
                            # Extract phone number from name attribute (format: "(732) 416-7719")
                            phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', phone_name)
                            if phone_match:
                                phone = re.sub(r'[^\d]', '', phone_match.group(0))
                                if len(phone) == 10 or (len(phone) == 11 and phone[0] == '1'):
                                    if len(phone) == 11:
                                        phone = phone[1:]
                                    data['phone'] = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
                        
                        # If not found in name, try button text
                        if not data['phone']:
                            button_text = phone_button_after.text
                            phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', button_text)
                            if phone_match:
                                phone = re.sub(r'[^\d]', '', phone_match.group(0))
                                if len(phone) == 10 or (len(phone) == 11 and phone[0] == '1'):
                                    if len(phone) == 11:
                                        phone = phone[1:]
                                    data['phone'] = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
                    except:
                        pass
                    
                    # Also search the entire page text for phone patterns
                    if not data['phone']:
                        page_text = self.driver.find_element(By.TAG_NAME, "body").text
                        phone_patterns = [
                            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
                        ]
                        for pattern in phone_patterns:
                            matches = re.findall(pattern, page_text)
                            if matches:
                                # Filter out common false positives
                                for match in matches:
                                    phone = re.sub(r'[^\d]', '', match)
                                    if len(phone) == 10 or (len(phone) == 11 and phone[0] == '1'):
                                        if len(phone) == 11:
                                            phone = phone[1:]
                                        # Check if it's a valid phone number (not a date, etc.)
                                        if phone[0] in ['2', '3', '4', '5', '6', '7', '8', '9']:
                                            data['phone'] = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
                                            break
                                if data['phone']:
                                    break
            except Exception as e:
                print(f"  Could not find or click phone button: {e}")
                # Try to extract phone from page source directly (might be visible without clicking)
                try:
                    page_source = self.driver.page_source
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    
                    # Look for phone patterns in the page
                    phone_patterns = [
                        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                        r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
                    ]
                    for pattern in phone_patterns:
                        matches = re.findall(pattern, page_text)
                        if matches:
                            for match in matches:
                                phone = re.sub(r'[^\d]', '', match)
                                if len(phone) == 10 or (len(phone) == 11 and phone[0] == '1'):
                                    if len(phone) == 11:
                                        phone = phone[1:]
                                    # Check if it's a valid phone number (not a date, etc.)
                                    if phone[0] in ['2', '3', '4', '5', '6', '7', '8', '9']:
                                        data['phone'] = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
                                        print(f"  Found phone number in page text: {data['phone']}")
                                        break
                            if data['phone']:
                                break
                except Exception as e2:
                    print(f"  Could not extract phone from page: {e2}")
                    pass
            
            return data
            
        except Exception as e:
            print(f"  Error extracting data from profile page: {e}")
            import traceback
            traceback.print_exc()
            return data
    
    def search_profile_url(self, business_name):
        """Try to find profile URL by searching HomeAdvisor for the business name"""
        try:
            # Search HomeAdvisor for the business
            search_url = f"https://www.homeadvisor.com/search.html?query={business_name.replace(' ', '+')}"
            print(f"  Searching for profile URL: {search_url}")
            self.driver.get(search_url)
            time.sleep(3)
            
            # Wait for Cloudflare if present
            self.wait_for_cloudflare_challenge()
            
            # Look for profile links in search results
            try:
                profile_links = self.driver.find_elements(By.CSS_SELECTOR, 
                    'a[href*="rated"], a[href*="/pro/"]')
                for link in profile_links[:5]:  # Check first 5 results
                    href = link.get_attribute('href')
                    link_text = link.text.lower()
                    business_name_lower = business_name.lower()
                    
                    # Check if this link seems related to our business
                    if href and ('rated' in href or '/pro/' in href):
                        # Check if the link text or nearby text contains the business name
                        try:
                            parent = link.find_element(By.XPATH, './ancestor::*[contains(@class, "result") or contains(@class, "listing") or contains(@class, "card")][1]')
                            parent_text = parent.text.lower()
                            if business_name_lower in parent_text:
                                # Make sure it's a full URL
                                if not href.startswith('http'):
                                    if href.startswith('/'):
                                        href = 'https://www.homeadvisor.com' + href
                                    else:
                                        href = 'https://www.homeadvisor.com/' + href
                                return href
                        except:
                            # If we can't check parent, just return the first matching href
                            if not href.startswith('http'):
                                if href.startswith('/'):
                                    href = 'https://www.homeadvisor.com' + href
                                else:
                                    href = 'https://www.homeadvisor.com/' + href
                            return href
            except:
                pass
        except Exception as e:
            print(f"  ⚠️  Error searching for profile URL: {e}")
        
        return None
    
    def enrich_business_data(self, business_data):
        """Enrich business data by visiting the profile page"""
        profile_url = business_data.get('profile_url', '')
        
        # If we don't have a profile URL, try to search for it
        if not profile_url:
            business_name = business_data.get('business_name', '')
            if business_name:
                print(f"  No profile URL found, searching HomeAdvisor for '{business_name}'...")
                profile_url = self.search_profile_url(business_name)
                if profile_url:
                    business_data['profile_url'] = profile_url
                    print(f"  ✓ Found profile URL: {profile_url}")
                else:
                    print(f"  ⚠️  Could not find profile URL for '{business_name}'")
                    # Continue without profile URL - we'll still have name, rating, reviews from listing page
                    return business_data
        
        # If we have a profile URL, visit it to get all the data
        if profile_url:
            try:
                profile_data = self.get_data_from_profile_page(profile_url)
                
                # Merge profile data into business data
                if profile_data.get('website'):
                    business_data['website'] = profile_data['website']
                if profile_data.get('phone'):
                    business_data['phone'] = profile_data['phone']
                if profile_data.get('address'):
                    business_data['address'] = profile_data['address']
                # Don't overwrite rating/reviews from listing page unless they're missing
                if not business_data.get('star_rating') and profile_data.get('star_rating'):
                    business_data['star_rating'] = profile_data['star_rating']
                if not business_data.get('num_reviews') and profile_data.get('num_reviews'):
                    business_data['num_reviews'] = profile_data['num_reviews']
            except Exception as e:
                print(f"  ⚠️  Error visiting profile page: {e}")
                # Continue with data we have from listing page
        
        # If we still don't have phone, try to find it on the website
        website = business_data.get('website', '')
        if website and not business_data.get('phone'):
            phone = self.find_phone_on_website(website)
            if phone:
                business_data['phone'] = phone
            else:
                # Search Google if not found on website
                business_name = business_data.get('business_name', '')
                address = business_data.get('address', '')
                if business_name and address:
                    phone = self.search_google_for_phone(business_name, address)
                    if phone:
                        business_data['phone'] = phone
        
        # Find email on website if we have one
        if website:
            email = self.find_email_on_website(website)
            if email:
                business_data['email'] = email
        
        return business_data
    
    def write_to_sheet(self, businesses):
        """Write business data to Google Sheet with retry logic"""
        if not businesses:
            return
        
        # Prepare data for writing
        rows = []
        for business in businesses:
            row = [
                business.get('business_name', ''),
                business.get('star_rating', ''),
                business.get('num_reviews', ''),
                business.get('address', ''),
                business.get('website', ''),
                business.get('phone', ''),
                business.get('email', '')
            ]
            rows.append(row)
        
        # Append to sheet with retry logic
        if rows:
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    self.sheet.append_rows(rows)
                    print(f"Wrote {len(rows)} businesses to sheet")
                    return  # Success, exit function
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"  Error writing to sheet (attempt {attempt + 1}/{max_retries}): {e}")
                        print(f"  Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        print(f"  ✗ Failed to write to sheet after {max_retries} attempts: {e}")
                        print(f"  Data will be retried on next batch write")
                        raise  # Re-raise on final attempt
    
    def scrape_all_pages(self, total_pages=105, start_page=1):
        """Scrape all pages and collect data"""
        all_businesses = []
        empty_pages_count = 0
        last_processed_page = start_page - 1  # Track the last successfully processed page
        
        for page_num in range(start_page, total_pages + 1):
            print(f"\n{'='*50}")
            print(f"Processing page {page_num} of {total_pages}")
            print(f"{'='*50}")
            
            # Retry logic for pages that might fail
            listings = None
            for retry in range(2):  # Try up to 2 times
                try:
                    listings = self.scrape_listings_from_page(page_num)
                    if listings:
                        break  # Success, exit retry loop
                    elif retry == 0:
                        print(f"  No listings found, retrying page {page_num}...")
                        time.sleep(5)  # Wait before retry
                except Exception as e:
                    print(f"  Error scraping page {page_num} (attempt {retry + 1}): {e}")
                    if retry < 1:
                        time.sleep(5)  # Wait before retry
            
            if not listings:
                empty_pages_count += 1
                print(f"⚠️  No listings found on page {page_num} - skipping and continuing...")
                print(f"   Total empty pages so far: {empty_pages_count}")
                print(f"   Continuing to next page...")
                time.sleep(3)  # Brief pause before next page
                continue
            
            # Check if all businesses on this page have no profile URLs
            businesses_without_profile = 0
            for business in listings:
                profile_url = business.get('profile_url', '')
                if not profile_url:
                    businesses_without_profile += 1
            
            # If all businesses have no profile URLs, stop scraping
            if businesses_without_profile == len(listings) and len(listings) > 0:
                last_processed_page = page_num
                print(f"\n{'='*50}")
                print(f"⚠️  STOPPING: All {len(listings)} businesses on page {page_num} have no profile URLs")
                print(f"   Without profile URLs, we cannot get detailed information")
                print(f"   (address, website, phone, email)")
                print(f"   Stopping scraping process...")
                print(f"{'='*50}\n")
                
                # Write any remaining businesses before stopping
                if all_businesses:
                    try:
                        self.write_to_sheet(all_businesses)
                        print(f"✓ Saved {len(all_businesses)} businesses to sheet before stopping")
                    except Exception as e:
                        print(f"⚠️  Warning: Could not write final batch to sheet: {e}")
                
                break  # Exit the loop and stop scraping
            
            # Update last processed page
            last_processed_page = page_num
            
            # Enrich each business with phone and email
            for i, business in enumerate(listings, 1):
                business_name = business.get('business_name', 'Unknown')
                rating = business.get('star_rating', 'N/A')
                reviews = business.get('num_reviews', 'N/A')
                print(f"\nProcessing business {i}/{len(listings)}: {business_name}")
                print(f"  Rating: {rating}, Reviews: {reviews}")
                try:
                    enriched = self.enrich_business_data(business)
                    all_businesses.append(enriched)
                except Exception as e:
                    print(f"  Error enriching business data: {e}")
                    # Still add the business even if enrichment failed
                    all_businesses.append(business)
                
                # Write to sheet periodically (every 10 businesses)
                if len(all_businesses) % 10 == 0:
                    try:
                        self.write_to_sheet(all_businesses[-10:])
                    except Exception as e:
                        print(f"  Warning: Could not write to sheet: {e}")
                        print(f"  Will retry on next batch or at the end")
                
                # Random rate limiting to appear more human-like (2-5 seconds)
                time.sleep(random.uniform(2, 5))
            
            # Write remaining businesses
            if len(all_businesses) % 10 != 0:
                remaining = all_businesses[-(len(all_businesses) % 10):]
                self.write_to_sheet(remaining)
            
            # Random rate limiting between pages (3-8 seconds)
            time.sleep(random.uniform(3, 8))
        
        # Final write of any remaining businesses
        if all_businesses:
            try:
                self.write_to_sheet(all_businesses)
            except Exception as e:
                print(f"\n⚠️  Warning: Could not write final batch to sheet: {e}")
                print(f"  You may need to manually export the data or check your connection")
        
        # Summary
        pages_processed = last_processed_page - start_page + 1
        print(f"\n{'='*50}")
        print(f"Scraping Summary:")
        print(f"  - Pages processed: {pages_processed} (stopped at page {last_processed_page})")
        print(f"  - Empty pages skipped: {empty_pages_count}")
        print(f"  - Total businesses collected: {len(all_businesses)}")
        if last_processed_page < total_pages:
            print(f"  - ⚠️  Stopped early: All businesses on page {last_processed_page} had no profile URLs")
        print(f"{'='*50}")
        
        return all_businesses
    
    def close(self):
        """Close the Selenium driver"""
        if self.driver:
            self.driver.quit()


def main():
    import sys
    
    # Configuration
    GOOGLE_SHEET_ID = "1b8JUs4vGZXY7YTnmPJ9KEUqDzXufmRuRBL2u5i6NPx4"  # Your Google Sheet ID
    CREDENTIALS_FILE = "homeadvisorelizabethscraping-613984138d99.json"  # Google Service Account credentials
    HEADLESS_MODE = True  # Set to False if you want to see the browser (useful for solving CAPTCHAs)
    
    # Get URL from command line argument or prompt
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        print("=" * 60)
        print("HomeAdvisor Scraper")
        print("=" * 60)
        print("\nEnter the HomeAdvisor URL you want to scrape.")
        print("Example: https://www.homeadvisor.com/c.Air-Conditioning.Elizabeth.NJ.-12002.html")
        print("Or any other HomeAdvisor category/location URL")
        print()
        base_url = input("URL: ").strip()
        
        if not base_url:
            print("ERROR: No URL provided!")
            return
        
        if not base_url.startswith('http'):
            base_url = 'https://' + base_url
    
    # Get start page (optional)
    START_PAGE = 1
    if len(sys.argv) > 2:
        try:
            START_PAGE = int(sys.argv[2])
        except:
            pass
    else:
        resume = input(f"\nStart from page (press Enter for page 1): ").strip()
        if resume:
            try:
                START_PAGE = int(resume)
            except:
                print("Invalid page number, starting from page 1")
                START_PAGE = 1
    
    # Get CAPTCHA API key from environment or command line
    captcha_api_key = os.getenv('CAPTCHA_API_KEY')
    if len(sys.argv) > 3:
        captcha_api_key = sys.argv[3] if sys.argv[3] else None
    
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: {CREDENTIALS_FILE} not found!")
        print("Please create a Google Service Account and download the credentials JSON file.")
        print("See README.md for instructions.")
        return
    
    print(f"\n{'='*60}")
    print(f"Starting scraper with:")
    print(f"  URL: {base_url}")
    print(f"  Starting from page: {START_PAGE}")
    print(f"{'='*60}\n")
    
    scraper = HomeAdvisorScraper(base_url, GOOGLE_SHEET_ID, CREDENTIALS_FILE, headless=HEADLESS_MODE, captcha_api_key=captcha_api_key)
    
    try:
        # Detect total pages automatically
        TOTAL_PAGES = scraper.detect_total_pages()
        
        if TOTAL_PAGES == 0:
            print("ERROR: Could not detect any pages. Please check the URL.")
            return
        
        print(f"\n{'='*60}")
        print(f"Will scrape {TOTAL_PAGES} pages (starting from page {START_PAGE})")
        print(f"{'='*60}\n")
        
        # Initialize sheet headers (only on first run)
        if START_PAGE == 1:
            headers = ['business name', 'star rating', '# of reviews', 'address', 'website', 'Phone Number', 'Email']
            scraper.sheet.clear()
            scraper.sheet.append_row(headers)
            print("Sheet initialized with headers")
        else:
            print(f"Resuming from page {START_PAGE}")
        
        # Scrape all pages
        businesses = scraper.scrape_all_pages(total_pages=TOTAL_PAGES, start_page=START_PAGE)
        
        print(f"\n{'='*50}")
        print(f"Scraping complete! Total businesses: {len(businesses)}")
        print(f"{'='*50}")
        
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user. Data has been saved to the sheet.")
        print("You can resume by running:")
        print(f"  python scraper.py \"{base_url}\" {START_PAGE}")
    except Exception as e:
        print(f"Error in main: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()

