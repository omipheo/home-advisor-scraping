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
        
        # Test scraping address, website, and phone for first few listings
        test_count = min(3, len(listings))  # Test first 3 listings
        print(f"\nScraping detailed info (address, website, phone) for first {test_count} listings...")
        
        for i, listing in enumerate(listings[:test_count], 1):
            print(f"\n{i}. {listing.get('business_name', 'N/A')}")
            print(f"   Rating: {listing.get('star_rating', 'N/A')}")
            print(f"   Reviews: {listing.get('num_reviews', 'N/A')}")
            
            # Get profile URL
            profile_url = listing.get('profile_url')
            if profile_url:
                print(f"   Profile URL: {profile_url}")
                print(f"   Fetching address, website, and phone...")
                
                # Visit profile page to get address, website, and phone
                profile_data = scraper.get_data_from_profile_page(profile_url)
                
                # Merge profile data with listing data
                if profile_data.get('address'):
                    listing['address'] = profile_data['address']
                if profile_data.get('website'):
                    listing['website'] = profile_data['website']
                if profile_data.get('phone'):
                    listing['phone'] = profile_data['phone']
                
                print(f"   ✓ Address: {listing.get('address', 'N/A')}")
                print(f"   ✓ Website: {listing.get('website', 'N/A')}")
                print(f"   ✓ Phone: {listing.get('phone', 'N/A')}")
            else:
                print(f"   ⚠️  No profile URL found")
        
        # Show remaining listings without detailed scraping
        if len(listings) > test_count:
            print(f"\n... and {len(listings) - test_count} more listings (detailed info not fetched)")
        
        if listings:
            print(f"\n✓ Scraper is working! Found {len(listings)} listings on page 1.")
            print("\nTesting Google Sheet write...")
            
            # Write first listing to sheet as a test
            if listings:
                test_business = listings[0]
                scraper.write_to_sheet([test_business])
                print(f"✓ Wrote test listing '{test_business.get('business_name', 'Unknown')}' to your Google Sheet")
                print("  Check your sheet to verify it appeared!")
            
            print("\nYou can now run the full scraper with: python scraper.py")
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

