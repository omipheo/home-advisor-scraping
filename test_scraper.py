"""
Test script to verify the scraper works on a single page
Run this first to make sure everything is set up correctly
"""
from scraper import HomeAdvisorScraper
import os

def test_single_page():
    """Test scraping a single page"""
    GOOGLE_SHEET_ID = "1b8JUs4vGZXY7YTnmPJ9KEUqDzXufmRuRBL2u5i6NPx4"  # Your Google Sheet ID
    CREDENTIALS_FILE = "homeadvisorelizabethscraping-613984138d99.json"
    
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: {CREDENTIALS_FILE} not found!")
        print("Please create a Google Service Account and download the credentials JSON file.")
        return
    
    scraper = HomeAdvisorScraper(GOOGLE_SHEET_ID, CREDENTIALS_FILE)
    
    try:
        print("Testing scraper on page 1...")
        listings = scraper.scrape_listings_from_page(1)
        
        print(f"\nFound {len(listings)} listings:")
        for i, listing in enumerate(listings[:5], 1):  # Show first 5
            print(f"\n{i}. {listing.get('business_name', 'N/A')}")
            print(f"   Rating: {listing.get('star_rating', 'N/A')}")
            print(f"   Reviews: {listing.get('num_reviews', 'N/A')}")
            print(f"   Address: {listing.get('address', 'N/A')}")
            print(f"   Website: {listing.get('website', 'N/A')}")
        
        if listings:
            print(f"\n✓ Scraper is working! Found {len(listings)} listings on page 1.")
            print("You can now run the full scraper with: python scraper.py")
        else:
            print("\n✗ No listings found. The page structure may have changed.")
            print("You may need to update the selectors in scraper.py")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()

if __name__ == "__main__":
    test_single_page()

