"""
CAPTCHA Solver using 2Captcha API
Supports Cloudflare Turnstile and reCAPTCHA v2/v3
"""
import time
import requests
import json


class CaptchaSolver:
    """Solve CAPTCHAs using 2Captcha API"""
    
    def __init__(self, api_key=None):
        """
        Initialize the CAPTCHA solver
        
        Args:
            api_key: Your 2Captcha API key (get it from https://2captcha.com/)
                    If None, automatic solving will be disabled
        """
        self.api_key = api_key
        self.api_url = "http://2captcha.com"
        self.enabled = api_key is not None
        
        if self.enabled:
            print(f"✓ CAPTCHA solver enabled (2Captcha API)")
        else:
            print("⚠️  CAPTCHA solver disabled (no API key provided)")
            print("   To enable automatic CAPTCHA solving:")
            print("   1. Sign up at https://2captcha.com/")
            print("   2. Get your API key from the dashboard")
            print("   3. Set CAPTCHA_API_KEY environment variable or pass it to the scraper")
    
    def solve_cloudflare_turnstile(self, site_key, page_url):
        """
        Solve Cloudflare Turnstile CAPTCHA
        
        Args:
            site_key: The site key from the Turnstile widget
            page_url: The URL of the page with the CAPTCHA
            
        Returns:
            str: The solution token, or None if failed
        """
        if not self.enabled:
            return None
        
        try:
            print(f"  🔐 Solving Cloudflare Turnstile CAPTCHA...")
            
            # Submit CAPTCHA to 2Captcha
            submit_url = f"{self.api_url}/in.php"
            submit_data = {
                'key': self.api_key,
                'method': 'turnstile',
                'sitekey': site_key,
                'pageurl': page_url,
                'json': 1
            }
            
            response = requests.post(submit_url, data=submit_data, timeout=30)
            result = response.json()
            
            if result['status'] != 1:
                print(f"  ❌ Failed to submit CAPTCHA: {result.get('request', 'Unknown error')}")
                return None
            
            captcha_id = result['request']
            print(f"  ⏳ CAPTCHA submitted, ID: {captcha_id}, waiting for solution...")
            
            # Poll for solution (max 2 minutes)
            get_url = f"{self.api_url}/res.php"
            max_wait = 120
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                time.sleep(5)  # Wait 5 seconds between checks
                
                get_params = {
                    'key': self.api_key,
                    'action': 'get',
                    'id': captcha_id,
                    'json': 1
                }
                
                response = requests.get(get_url, params=get_params, timeout=30)
                result = response.json()
                
                if result['status'] == 1:
                    token = result['request']
                    print(f"  ✓ CAPTCHA solved! Token received.")
                    return token
                elif result['request'] == 'CAPCHA_NOT_READY':
                    # Still processing, continue waiting
                    elapsed = int(time.time() - start_time)
                    print(f"  ⏳ Still solving... ({elapsed}s elapsed)")
                    continue
                else:
                    print(f"  ❌ CAPTCHA solving failed: {result.get('request', 'Unknown error')}")
                    return None
            
            print(f"  ❌ CAPTCHA solving timeout after {max_wait} seconds")
            return None
            
        except Exception as e:
            print(f"  ❌ Error solving CAPTCHA: {e}")
            return None
    
    def solve_recaptcha_v2(self, site_key, page_url):
        """
        Solve reCAPTCHA v2
        
        Args:
            site_key: The site key from the reCAPTCHA widget
            page_url: The URL of the page with the CAPTCHA
            
        Returns:
            str: The solution token, or None if failed
        """
        if not self.enabled:
            return None
        
        try:
            print(f"  🔐 Solving reCAPTCHA v2...")
            
            # Submit CAPTCHA to 2Captcha
            submit_url = f"{self.api_url}/in.php"
            submit_data = {
                'key': self.api_key,
                'method': 'userrecaptcha',
                'googlekey': site_key,
                'pageurl': page_url,
                'json': 1
            }
            
            response = requests.post(submit_url, data=submit_data, timeout=30)
            result = response.json()
            
            if result['status'] != 1:
                print(f"  ❌ Failed to submit CAPTCHA: {result.get('request', 'Unknown error')}")
                return None
            
            captcha_id = result['request']
            print(f"  ⏳ CAPTCHA submitted, ID: {captcha_id}, waiting for solution...")
            
            # Poll for solution (max 2 minutes)
            get_url = f"{self.api_url}/res.php"
            max_wait = 120
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                time.sleep(5)  # Wait 5 seconds between checks
                
                get_params = {
                    'key': self.api_key,
                    'action': 'get',
                    'id': captcha_id,
                    'json': 1
                }
                
                response = requests.get(get_url, params=get_params, timeout=30)
                result = response.json()
                
                if result['status'] == 1:
                    token = result['request']
                    print(f"  ✓ CAPTCHA solved! Token received.")
                    return token
                elif result['request'] == 'CAPCHA_NOT_READY':
                    # Still processing, continue waiting
                    elapsed = int(time.time() - start_time)
                    print(f"  ⏳ Still solving... ({elapsed}s elapsed)")
                    continue
                else:
                    print(f"  ❌ CAPTCHA solving failed: {result.get('request', 'Unknown error')}")
                    return None
            
            print(f"  ❌ CAPTCHA solving timeout after {max_wait} seconds")
            return None
            
        except Exception as e:
            print(f"  ❌ Error solving CAPTCHA: {e}")
            return None
    
    def get_balance(self):
        """Get account balance from 2Captcha"""
        if not self.enabled:
            return None
        
        try:
            url = f"{self.api_url}/res.php"
            params = {
                'key': self.api_key,
                'action': 'getbalance',
                'json': 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            result = response.json()
            
            if result['status'] == 1:
                return float(result['request'])
            return None
        except:
            return None

