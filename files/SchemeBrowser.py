import pandas as pd
import requests
import os
import time

class SchemeBrowser:
    def __init__(self):
        self.base_url = "https://api.mfapi.in"
        self.data_dir = "data/raw"
        os.makedirs(self.data_dir, exist_ok=True)
        self.schemes_df = None
    
    def fetchAllSchemes(self):
        cache_file = f"{self.data_dir}/Schemes-List.csv"
        
        if os.path.exists(cache_file):
            print(f"Loading schemes from cache: {cache_file}")
            self.schemes_df = pd.read_csv(cache_file)
            print(f"Loaded {len(self.schemes_df)} schemes.")
            return True
        
        print("Fetching all schemes from MFAPI.")
        try:
            response = requests.get(f"{self.base_url}/mf")
            response.raise_for_status()
            schemes = response.json()
            
            self.schemes_df = pd.DataFrame(schemes)
            self.schemes_df.to_csv(cache_file, index=False)
            
            print(f"Fetched {len(schemes)} schemes.")
            print(f"Cached to {cache_file}")
            return True
            
        except Exception as e:
            print(f"Error: {e}")
            return False
    
    def search(self, keyword, case_sensitive=False):
        if self.schemes_df is None:
            if not self.fetchAllSchemes():
                return None
        
        if not case_sensitive:
            mask = self.schemes_df['schemeName'].str.contains(keyword, case=False, na=False)
        else:
            mask = self.schemes_df['schemeName'].str.contains(keyword, na=False)
        
        results = self.schemes_df[mask].copy()
        results['match_position'] = results['schemeName'].str.lower().str.find(keyword.lower())
        results = results.sort_values('match_position')
        
        return results[['schemeCode', 'schemeName']]
    
    def interactive_search(self):
        if not self.fetchAllSchemes():
            return
        
        while True:
            print("\n" + "="*70)
            print("MUTUAL FUND SCHEME SEARCH")
            print("="*70)
            print("1. Search by keyword")
            print("2. Exit")
            
            choice = input("\nSelect option (1-2): ").strip()
            
            if choice == '1':
                keyword = input("\nEnter search keyword: ").strip()
                if keyword:
                    results = self.search(keyword)
                    if results is not None and len(results) > 0:
                        print(f"\nFound {len(results)} matching schemes:\n")
                        print(results.head(20).to_string(index=False))
                        if len(results) > 20:
                            print(f"\n... and {len(results) - 20} more results")
                    else:
                        print("No schemes found")

            elif choice == '2':
                print("\nGoodbye!")
                break
            
            else:
                print("Invalid choice. Please try again.")

    def load_or_fetch_schemes(self):
        schemes_file = f"{self.data_dir}/all_schemes.csv"
        
        if os.path.exists(schemes_file):
            print(f"Loading schemes from {schemes_file}")
            self.schemes_df = pd.read_csv(schemes_file)
        else:
            print("Fetching all schemes from API...")
            response = requests.get(f"{self.base_url}/mf")
            if response.status_code == 200:
                schemes = response.json()
                self.schemes_df = pd.DataFrame(schemes)
                self.schemes_df.to_csv(schemes_file, index=False)
                print(f"Fetched and saved {len(schemes)} schemes.")
            else:
                print("Failed to fetch schemes.")
                return False
        
        return True
    
    def get_scheme_with_retry(self, scheme_code, max_retries=3):
        for attempt in range(max_retries):
            try:
                response = requests.get(f"{self.base_url}/mf/{scheme_code}", timeout=30)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  
                else:
                    print(f"✗ Failed to fetch scheme {scheme_code} after {max_retries} attempts")
                    return None
