import pandas as pd
from SchemeBrowser import SchemeBrowser

def SchemesList():
    browser = SchemeBrowser()
    browser.fetchAllSchemes()

def CollectSpecificSchemes():
    print("\n" + "="*50)
    print("COLLECTING SPECIFIC SCHEMES")
    print("="*50)
    
    collector = SchemeBrowser()
    
    collector.load_or_fetch_schemes()
    scheme_names_lookup = dict(zip(collector.schemes_df['schemeCode'].astype(str), collector.schemes_df['schemeName']))
    
    specific_schemes_input = input("\nEnter scheme codes to collect (comma-separated): ").strip()
    
    specific_schemes = {}
    for code in specific_schemes_input.split(','):
        code = code.strip()
        if code:
            if code not in scheme_names_lookup:
                print(f"\n✗ Error: Scheme code '{code}' does not exist in the database.")
                return None
            scheme_name = scheme_names_lookup[code]
            specific_schemes[code] = scheme_name
    
    print("\nCollecting these specific schemes:")
    for code, name in specific_schemes.items():
        print(f"  {code}: {name}")
    
    proceed = input("\nProceed? (y/n): ").strip().lower()
    
    if proceed == 'y':
        collected = []
        
        for code, name in specific_schemes.items():
            print(f"\nFetching {name}...")
            data = collector.get_scheme_with_retry(code)
            
            if data and 'data' in data:
                nav_df = pd.DataFrame(data['data'])
                meta = data.get('meta', {})
                
                nav_df['scheme_code'] = code
                nav_df['scheme_name'] = name
                nav_df['fund_house'] = meta.get('fund_house', 'Unknown')
                
                filename = f"{collector.data_dir}/scheme_{code}.csv"
                nav_df.to_csv(filename, index=False)
                
                print(f"✓ Saved {len(nav_df)} records")
                collected.append({'code': code, 'name': name, 'records': len(nav_df)})
            
            import time
            time.sleep(1)
        
        print("\nCollection complete.")
        return collected
    else:
        print("\nCollection cancelled.")
        return None


def main_menu():
    while True:
        print("\n" + "="*50)
        print("MUTUAL FUND DATA COLLECTION - MENU")
        print("="*50)
        print("\n")

        print("1. Get list of all schemes available on MFAPI")
        print("2. Browse Schemes Interactively")
        print("3. Get data of specific schemes by Scheme Code")
        print("4. Exit")
        
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == '1':
            SchemesList()

        elif choice == '3':
            CollectSpecificSchemes()
        
        elif choice == '2':
            browser = SchemeBrowser()
            browser.interactive_search()
        
        elif choice == '4':
            print("\nThankyou for using the Mutual Fund Data Collector. Goodbye!")
            break
        
        else:
            print("\nInvalid choice. Please try again.")


if __name__ == "__main__":    
    main_menu()