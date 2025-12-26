import requests
from bs4 import BeautifulSoup
import time
import re
import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import json
import os
import random
from pathlib import Path
from urllib.parse import urljoin, urlparse

class HomeAdvisorScraper:
    def __init__(self, google_sheet_id, credentials_file=None, headless=True):
        self.base_url = "https://www.homeadvisor.com/c.Air-Conditioning.Elizabeth.NJ.-12002.html"
        self.headless = headless
        
        # Rotate Chrome User-Agents to appear more human-like
        # All user-agents are Chrome-based to match the browser being used
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        })
        
        # Setup Selenium with Chrome browser (Chrome must be installed)
        # ChromeDriver will be automatically downloaded by webdriver-manager
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument('--headless=new')  # New headless mode is less detectable
        
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
        # Note: Google Chrome must be installed on your system
        # ChromeDriver will be automatically downloaded and managed
        try:
            # Get ChromeDriver path - ChromeDriverManager sometimes returns wrong file
            manager_path = ChromeDriverManager().install()
            print(f"ChromeDriverManager returned: {manager_path}")
            
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
        return f"{self.base_url}?page={page_num}"
    
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
    
    def scrape_listings_from_page(self, page_num):
        """Scrape all business listings from a single page"""
        url = self.get_page_url(page_num)
        print(f"Scraping page {page_num}: {url}")
        
        try:
            # Use Selenium for JavaScript rendering
            self.driver.get(url)
            
            # Random delay to appear more human-like (3-7 seconds)
            time.sleep(random.uniform(3, 7))
            
            # Check for CAPTCHA
            if self.check_for_captcha():
                print(f"⚠️  CAPTCHA detected on page {page_num}!")
                if self.headless:
                    print("   Running in headless mode. Switch to non-headless mode to solve CAPTCHA manually.")
                    print("   Edit scraper.py and set headless=False in HomeAdvisorScraper()")
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
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'lxml')
            
            # Debug: Save HTML for inspection (only on first page)
            if page_num == 1:
                try:
                    with open('debug_page1.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    print("Debug: Saved page HTML to debug_page1.html")
                except:
                    pass
            
            listings = []
            
            # Multiple strategies to find listings
            listing_containers = []
            
            # Strategy 1: Look for links to /pro/ pages (HomeAdvisor business profile links)
            # But filter out promotional/ad links
            pro_links = soup.find_all('a', href=re.compile(r'/pro/', re.I))
            for link in pro_links:
                link_text = link.get_text(strip=True).lower()
                href = link.get('href', '').lower()
                
                # Filter out ads and promotional content
                skip_keywords = [
                    'join as a pro',
                    'sign up',
                    'become a pro',
                    'signup',
                    'register',
                    'advertisement',
                    'ad',
                    'sponsored'
                ]
                
                if any(keyword in link_text for keyword in skip_keywords):
                    continue
                
                if any(keyword in href for keyword in ['signup', 'register', 'join']):
                    continue
                
                # Find parent container
                parent = link.find_parent(['div', 'article', 'section', 'li', 'h2', 'h3'])
                if parent:
                    # Make sure it's not nested in another listing
                    is_nested = False
                    for existing in listing_containers:
                        if parent in existing.descendants or parent == existing:
                            is_nested = True
                            break
                    if not is_nested:
                        listing_containers.append(parent)
            
            # Strategy 2: Look for common HomeAdvisor class patterns
            if not listing_containers:
                patterns = [
                    r'[Ss]rpResult',
                    r'[Ll]isting',
                    r'[Pp]ro[Cc]ard',
                    r'[Bb]usiness[Cc]ard',
                    r'[Rr]esult[Cc]ard'
                ]
                for pattern in patterns:
                    containers = soup.find_all(['div', 'article'], class_=re.compile(pattern))
                    if containers:
                        listing_containers.extend(containers)
                        break
            
            # Strategy 3: Look for data attributes
            if not listing_containers:
                listing_containers = soup.find_all(['div', 'article'], attrs={'data-testid': re.compile(r'.*', re.I)})
            
            # Strategy 4: Look for any div/article with business-related text
            if not listing_containers:
                all_divs = soup.find_all(['div', 'article', 'section'])
                for div in all_divs:
                    text = div.get_text()
                    if any(keyword in text.lower() for keyword in ['reviews', 'rating', 'star', 'phone', 'address']):
                        if len(text) > 50 and len(text) < 2000:  # Reasonable size for a listing
                            listing_containers.append(div)
            
            # Remove duplicates and nested containers
            unique_containers = []
            seen_texts = set()
            for container in listing_containers:
                text = container.get_text(strip=True)[:100]  # First 100 chars as signature
                if text and text not in seen_texts:
                    seen_texts.add(text)
                    unique_containers.append(container)
            
            print(f"Found {len(unique_containers)} potential listings on page {page_num}")
            
            for container in unique_containers:
                try:
                    business_data = self.extract_business_info(container)
                    business_name = business_data.get('business_name', '').lower()
                    
                    # Filter out ads and promotional content
                    skip_keywords = [
                        'join as a pro',
                        'sign up',
                        'become a pro',
                        'signup',
                        'register',
                        'advertisement',
                        'ad',
                        'sponsored',
                        'get started',
                        'learn more'
                    ]
                    
                    if business_name and any(keyword in business_name for keyword in skip_keywords):
                        continue
                    
                    # Must have a business name and at least some other data
                    if business_data and business_name and len(business_name) > 2:
                        # Prefer listings with more data (rating, reviews, address)
                        if (business_data.get('star_rating') or 
                            business_data.get('num_reviews') or 
                            business_data.get('address')):
                            listings.append(business_data)
                        elif business_name:  # Still add if it has a name
                            listings.append(business_data)
                except Exception as e:
                    print(f"Error extracting listing: {e}")
                    continue
            
            return listings
            
        except Exception as e:
            print(f"Error scraping page {page_num}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
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
        
        # Extract business name - multiple strategies
        # Strategy 1: Look for /pro/ links (most reliable)
        pro_link = container.find('a', href=re.compile(r'/pro/', re.I))
        if pro_link:
            name_text = pro_link.get_text(strip=True)
            # Filter out promotional text
            if name_text and not any(skip in name_text.lower() for skip in ['join', 'sign up', 'become', 'register']):
                data['business_name'] = name_text
        
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
            response = self.session.get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            text = soup.get_text()
            
            # Common phone number patterns
            phone_patterns = [
                r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (123) 456-7890
                r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',        # 123-456-7890
                r'\+?1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # +1 (123) 456-7890
            ]
            
            for pattern in phone_patterns:
                matches = re.findall(pattern, text)
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
        """Search for email address on a business website"""
        if not url or not url.startswith('http'):
            return None
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            text = soup.get_text()
            
            # Email pattern
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            matches = re.findall(email_pattern, text)
            
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
            google_url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
            
            print(f"  Searching Google for phone: {query}")
            
            self.driver.get(google_url)
            # Random delay to appear more human-like
            time.sleep(random.uniform(2, 4))
            
            # Check for CAPTCHA on Google
            if self.check_for_captcha():
                print("  ⚠️  CAPTCHA detected on Google search, skipping...")
                return None
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'lxml')
            text = soup.get_text()
            
            # Look for phone numbers in the results
            phone_patterns = [
                r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
            ]
            
            for pattern in phone_patterns:
                matches = re.findall(pattern, text)
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
    
    def get_website_from_profile(self, business_name):
        """Get website URL from HomeAdvisor business profile page"""
        try:
            # Search for the business on HomeAdvisor
            search_url = f"https://www.homeadvisor.com/search.html?query={requests.utils.quote(business_name)}"
            self.driver.get(search_url)
            time.sleep(3)
            
            # Look for the first /pro/ link
            pro_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/pro/"]')
            if pro_links:
                profile_url = pro_links[0].get_attribute('href')
                if profile_url:
                    # Visit the profile page
                    self.driver.get(profile_url)
                    time.sleep(3)
                    
                    # Look for website link
                    website_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href^="http"]')
                    for link in website_links:
                        href = link.get_attribute('href')
                        if href and not any(skip in href.lower() for skip in ['homeadvisor.com', 'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com']):
                            return href
            
            return None
        except Exception as e:
            print(f"  Error getting website from profile: {e}")
            return None
    
    def enrich_business_data(self, business_data):
        """Enrich business data with phone and email"""
        website = business_data.get('website', '')
        
        # If no website found, try to get it from HomeAdvisor profile
        if not website:
            business_name = business_data.get('business_name', '')
            if business_name:
                print(f"  No website in listing, trying to get from profile...")
                website = self.get_website_from_profile(business_name)
                if website:
                    business_data['website'] = website
        
        # Find phone on website
        if website:
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
            
            # Find email on website (only if phone was found or we have website)
            email = self.find_email_on_website(website)
            if email:
                business_data['email'] = email
        
        return business_data
    
    def write_to_sheet(self, businesses):
        """Write business data to Google Sheet"""
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
        
        # Append to sheet
        if rows:
            self.sheet.append_rows(rows)
            print(f"Wrote {len(rows)} businesses to sheet")
    
    def scrape_all_pages(self, total_pages=105, start_page=1):
        """Scrape all pages and collect data"""
        all_businesses = []
        
        for page_num in range(start_page, total_pages + 1):
            print(f"\n{'='*50}")
            print(f"Processing page {page_num} of {total_pages}")
            print(f"{'='*50}")
            
            listings = self.scrape_listings_from_page(page_num)
            
            if not listings:
                print(f"No listings found on page {page_num}, stopping...")
                break
            
            # Enrich each business with phone and email
            for i, business in enumerate(listings, 1):
                print(f"\nProcessing business {i}/{len(listings)}: {business.get('business_name', 'Unknown')}")
                enriched = self.enrich_business_data(business)
                all_businesses.append(enriched)
                
                # Write to sheet periodically (every 10 businesses)
                if len(all_businesses) % 10 == 0:
                    self.write_to_sheet(all_businesses[-10:])
                
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
            self.write_to_sheet(all_businesses)
        
        return all_businesses
    
    def close(self):
        """Close the Selenium driver"""
        if self.driver:
            self.driver.quit()


def main():
    # Configuration
    GOOGLE_SHEET_ID = "1mt2pi6hxnDpKiCu8sHlBQHz07ptujXEOPJxq5T-Zfxw"
    CREDENTIALS_FILE = "homeadvisorelizabethscraping-613984138d99.json"  # Google Service Account credentials
    TOTAL_PAGES = 105
    START_PAGE = 1  # Change this to resume from a specific page
    HEADLESS_MODE = True  # Set to False if you want to see the browser (useful for solving CAPTCHAs)
    
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: {CREDENTIALS_FILE} not found!")
        print("Please create a Google Service Account and download the credentials JSON file.")
        print("See README.md for instructions.")
        return
    
    scraper = HomeAdvisorScraper(GOOGLE_SHEET_ID, CREDENTIALS_FILE, headless=HEADLESS_MODE)
    
    try:
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
        print("You can resume by changing START_PAGE in scraper.py")
    except Exception as e:
        print(f"Error in main: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()

