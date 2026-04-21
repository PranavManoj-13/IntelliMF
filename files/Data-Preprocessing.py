import pandas as pd
import os
from glob import glob

# ============================================================================
# STEP 1: Check for Missing NAV Values and Impute
# ============================================================================

def ImputeNAV(file_path):

    df = pd.read_csv(file_path)
    
    df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
    df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
    
    df = df.sort_values('date')
    
    missing_before = df['nav'].isna().sum()
    total_records = len(df)
    missing_percentage = (missing_before / total_records) * 100
    
    print(f"\nFile: {os.path.basename(file_path)}")
    print(f"Total Records: {total_records}")
    print(f"Missing NAV values: {missing_before} ({missing_percentage:.2f}%)")
    
    df['nav'] = df['nav'].fillna(method='ffill')
    df['nav'] = df['nav'].fillna(method='bfill')
    
    missing_after = df['nav'].isna().sum()
    print(f"Missing NAV after imputation: {missing_after}")
    
    return df

# ============================================================================
# STEP 2: Remove Specific Columns from Multiple CSV Files
# ============================================================================

def RemoveCSVCols(file_path, columns_to_remove):

    df = pd.read_csv(file_path)
    
    existing_columns = [col for col in columns_to_remove if col in df.columns]
    
    if existing_columns:
        print(f"\nRemoving columns {existing_columns} from {os.path.basename(file_path)}")
        df = df.drop(columns=existing_columns)
    else:
        print(f"\nNo matching columns to remove in {os.path.basename(file_path)}.")
    
    return df

# ============================================================================
# STEP 3: Process All CSV Files in a Directory
# ============================================================================

def ProcessAllCSVFiles(input_dir, output_dir=None):

    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    columns_to_remove = ['scheme_name', 'fund_house']
    
    csv_files = glob(os.path.join(input_dir, '*.csv'))
    
    if not csv_files:
        print(f"No CSV files found in {input_dir}")
        return
    
    print(f"Found {len(csv_files)} CSV files to process.")
    print("=" * 70)
    
    total_missing = 0
    total_records = 0
    files_processed = 0
    
    for file_path in csv_files:
        try:
            df = ImputeNAV(file_path)
            
            total_records += len(df)
            
            df = RemoveCSVCols(file_path, columns_to_remove)
            
            if output_dir:
                output_path = os.path.join(output_dir, os.path.basename(file_path))
            else:
                output_path = file_path
            
            df.to_csv(output_path, index=False)
            print(f"Saved to: {output_path}.")
            
            files_processed += 1
            
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    print("\n" + "=" * 70)
    print("PROCESSING SUMMARY")
    print("=" * 70)
    print(f"Files processed: {files_processed}/{len(csv_files)-1}")
    print(f"Total records processed: {total_records}")
    print("=" * 70)

# ============================================================================
# STEP 4: Detailed Missing Value Report
# ============================================================================

def generateMissingValReport(input_dir):

    csv_files = glob(os.path.join(input_dir, '*.csv'))

    report_data = []
    
    for file_path in csv_files:
        try:
            df = pd.read_csv(file_path)
            
            df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
            df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
            
            total_rows = len(df)
            missing_nav = df['nav'].isna().sum()
            missing_date = df['date'].isna().sum()
            missing_pct = (missing_nav / total_rows) * 100 if total_rows > 0 else 0
            
            scheme_code = os.path.basename(file_path).replace('scheme_', '').replace('.csv', '')
            
            report_data.append({
                'Scheme_Code': scheme_code,
                'Total_Records': total_rows,
                'Missing_NAV': missing_nav,
                'Missing_Date': missing_date,
                'Missing_Percentage': round(missing_pct, 2)
            })
            
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    report_df = pd.DataFrame(report_data)
    report_df = report_df.sort_values('Missing_Percentage', ascending=False)
    
    return report_df

# ============================================================================
# CODE EXECUTION
# ============================================================================

if __name__ == "__main__":

    input_directory = "data/raw"  
    output_directory = "data/processed"
    
    print("=" * 70)
    print("MUTUAL FUND DATA PREPROCESSING")
    print("=" * 70)
    
    print("\nGenerating Missing Value Report...")
    report = generateMissingValReport(input_directory)
    print("\nMissing Value Report:")
    print(report.to_string(index=False))
    
    report.to_csv(os.path.join(input_directory, 'Missing-Value-Report.csv'), index=False)
    print(f"\nReport saved to: {input_directory}/Missing-Value-Report.csv")
    
    print("\n" + "=" * 70)
    print("Processing all CSV files...")
    print("=" * 70)
    
    ProcessAllCSVFiles(input_directory, output_directory)
    
    print("\nAll files processed successfully.")
    print(f"Processed files saved to: {output_directory}")