import pandas as pd
from datetime import datetime, timedelta
import numpy as np

def load_and_analyze_transportation_data(input_file, output_file):
    """
    Load transportation CSV and create summary with bus lines as columns 
    and dates as rows showing count of 'yes' responses.
    """
    
    # Load the CSV file
    try:
        df = pd.read_csv(input_file, encoding='utf-8')
        print(f"Successfully loaded {input_file}")
        print(f"Data shape: {df.shape}")
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.")
        return
    except Exception as e:
        print(f"Error loading file: {e}")
        return
    
    # Clean column names (remove extra spaces)
    df.columns = df.columns.str.strip()
    
    # Get unique bus lines
    bus_lines = df['bus line'].unique()
    print(f"Found {len(bus_lines)} unique bus lines:")
    for i, bus_line in enumerate(bus_lines, 1):
        print(f"{i}. {bus_line}")
    
    # Find date columns (columns that contain week information)
    date_columns = [col for col in df.columns if 'Week' in col and '] -' in col]
    print(f"\nFound {len(date_columns)} date columns")
    
    # Create a dictionary to store results
    results = {}
    
    # Process each date column
    for date_col in date_columns:
        # Use the original column name as is - no date conversion
        date_str = date_col
        
        # Count 'yes' responses for each bus line on this date
        bus_line_counts = {}
        for bus_line in bus_lines:
            # Filter data for this bus line
            bus_line_data = df[df['bus line'] == bus_line]
            # Count 'yes' responses for this date column
            yes_count = (bus_line_data[date_col] == 'yes').sum()
            bus_line_counts[bus_line] = yes_count
        
        results[date_str] = bus_line_counts
    
    # Create the output DataFrame
    output_df = pd.DataFrame.from_dict(results, orient='index')
    
    # Keep the original order of columns as they appear in the CSV
    
    # Fill NaN values with 0
    output_df = output_df.fillna(0)
    
    # Convert to integer type
    output_df = output_df.astype(int)
    
    # Add a total row
    total_row = output_df.sum()
    total_row.name = 'TOTAL'
    output_df = pd.concat([output_df, total_row.to_frame().T])
    
    # Add a total column
    output_df['TOTAL'] = output_df.sum(axis=1)
    
    # Save to CSV
    try:
        output_df.to_csv(output_file, encoding='utf-8-sig')
        print(f"\nSummary saved to '{output_file}'")
        print(f"Output shape: {output_df.shape}")
    except Exception as e:
        print(f"Error saving file: {e}")
        return
    
    # Display preview
    print("\nPreview of the summary:")
    print(output_df.head(10))
    
    # Display statistics
    print(f"\nStatistics:")
    print(f"Total date columns: {len(output_df) - 1}")  # -1 for TOTAL row
    print(f"Total unique bus lines: {len(output_df.columns) - 1}")  # -1 for TOTAL column
    print(f"Maximum daily count per bus line: {output_df.iloc[:-1, :-1].max().max()}")
    print(f"Average daily count per bus line: {output_df.iloc[:-1, :-1].mean().mean():.2f}")
    
    return output_df

# Main execution
if __name__ == "__main__":
    input_filename = "Medicine Staff Transportation for Summer.csv"
    output_filename = "Transportation_Summary_by_BusLine_and_Date.csv"
    
    print("Transportation Data Analysis")
    print("=" * 50)
    
    # Run the analysis
    result = load_and_analyze_transportation_data(input_filename, output_filename)
    
    if result is not None:
        print("\nAnalysis completed successfully!")
        print(f"Check the output file: {output_filename}")
    else:
        print("\nAnalysis failed. Please check the error messages above.")