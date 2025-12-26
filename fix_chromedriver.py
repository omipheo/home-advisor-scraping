"""
Utility script to fix ChromeDriver issues
Run this if you get "[WinError 193] %1 is not a valid Win32 application"
"""
import shutil
from pathlib import Path
import os

def clear_chromedriver_cache():
    """Clear the ChromeDriver cache to force re-download"""
    cache_path = Path.home() / ".wdm"
    
    if cache_path.exists():
        try:
            print(f"Clearing ChromeDriver cache at: {cache_path}")
            shutil.rmtree(cache_path)
            print("✓ Cache cleared successfully!")
            print("ChromeDriver will be re-downloaded on next run.")
            return True
        except Exception as e:
            print(f"✗ Error clearing cache: {e}")
            print("You may need to manually delete: " + str(cache_path))
            return False
    else:
        print("No cache found. Nothing to clear.")
        return True

def check_chrome_installation():
    """Check if Chrome is installed"""
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            print(f"✓ Chrome found at: {path}")
            return True
    
    print("✗ Chrome not found in common locations")
    print("Please install Google Chrome from: https://www.google.com/chrome/")
    return False

if __name__ == "__main__":
    print("=" * 50)
    print("ChromeDriver Fix Utility")
    print("=" * 50)
    print()
    
    print("1. Checking Chrome installation...")
    chrome_ok = check_chrome_installation()
    print()
    
    print("2. Clearing ChromeDriver cache...")
    cache_cleared = clear_chromedriver_cache()
    print()
    
    if chrome_ok and cache_cleared:
        print("=" * 50)
        print("✓ Setup complete! Try running test_scraper.py again.")
        print("=" * 50)
    else:
        print("=" * 50)
        print("⚠ Please fix the issues above and try again.")
        print("=" * 50)

