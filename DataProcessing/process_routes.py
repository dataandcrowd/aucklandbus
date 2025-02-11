import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path

def load_frequencies(frequency_file):
    """Load and process the daily bus frequencies data."""
    freq_df = pd.read_csv(frequency_file)
    # Calculate service days (days with any trips)
    freq_df['service_days'] = freq_df[['Monday', 'Tuesday', 'Wednesday', 
                                       'Thursday', 'Friday', 'Saturday', 'Sunday']].gt(0).sum(axis=1)
    return freq_df

def load_patronage_data(excel_2023_file, excel_2024_file):
    """Load and combine the patronage data from both Excel files."""
    # Load both Excel files
    patronage_2023 = pd.read_excel(excel_2023_file)
    patronage_2024 = pd.read_excel(excel_2024_file)

    # Convert route numbers to strings for matching
    patronage_2023['Number'] = patronage_2023['Number'].astype(str)
    patronage_2024['Number'] = patronage_2024['Number'].astype(str)
    
    # Transform data from wide to long format
    patronage_2023_long = pd.melt(
        patronage_2023,
        id_vars=['Number'],
        var_name='Date',
        value_name='Patronage'
    )
    
    patronage_2024_long = pd.melt(
        patronage_2024,
        id_vars=['Number'],
        var_name='Date',
        value_name='Patronage'
    )
    
    # Combine both years' data
    patronage_combined = pd.concat([patronage_2023_long, patronage_2024_long])
    patronage_combined['Date'] = pd.to_datetime(patronage_combined['Date'])
    
    patronage_combined['DayOfWeek'] = patronage_combined['Date'].dt.day_name()
    
    return patronage_combined

def calculate_route_averages(patronage_df):
    """Calculate average daily patrons for each route."""
    # Only consider days with patronage > 0
    valid_patronage = patronage_df[patronage_df['Patronage'] > 0]
    
    route_averages = valid_patronage.groupby('Number').agg({
        'Patronage': 'mean',  # Average daily patrons
        'DayOfWeek': lambda x: len(x.unique())  # Number of service days
    }).reset_index()
    
    route_averages.columns = ['ROUTENUMBER', 'avg_daily_patrons', 'service_days']
    return route_averages

def process_routes(bus_routes_file, excel_2023_file, excel_2024_file, frequencies_file, output_file):
    """Main processing function to combine all data and add new columns."""
    try:
        # Load base route data
        routes_gdf = gpd.read_file(bus_routes_file)
        routes_gdf['ROUTENUMBER'] = routes_gdf['ROUTENUMBER'].astype(str)
        
        # Load and process patronage data from Excel files
        patronage_df = load_patronage_data(excel_2023_file, excel_2024_file)
        route_averages = calculate_route_averages(patronage_df)
        
        # Load frequency data
        freq_df = load_frequencies(frequencies_file)
        
        # Merge all data
        # First merge patronage averages
        routes_gdf = routes_gdf.merge(
            route_averages,
            on='ROUTENUMBER',
            how='left'
        )
        
        # Then merge frequency data
        freq_df['ROUTENUMBER'] = freq_df['route_short_name'].astype(str)
        freq_df['avg_daily_trips'] = freq_df[['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']].replace(0, np.nan).mean(axis=1)
        
        routes_gdf = routes_gdf.merge(
            freq_df[['ROUTENUMBER', 'avg_daily_trips']],
            on='ROUTENUMBER',
            how='left'
        )
        
        # Fill NaN values with 0
        routes_gdf = routes_gdf.fillna({
            'avg_daily_patrons': 0,
            'avg_daily_trips': 0,
            'service_days': 0
        })
        
        # Round and convert to integers
        routes_gdf['avg_daily_patrons'] = routes_gdf['avg_daily_patrons'].round().astype(int)
        routes_gdf['avg_daily_trips'] = routes_gdf['avg_daily_trips'].round().astype(int)
        routes_gdf['service_days'] = routes_gdf['service_days'].astype(int)
        
        # Save to new GeoJSON file
        routes_gdf.to_file(output_file, driver='GeoJSON')
        print(f"Successfully processed data and saved to {output_file}")
        
    except Exception as e:
        print(f"Error processing data: {str(e)}")
        raise

def main():
    # Define input/output paths
    base_path = Path('.')
    input_geojson = base_path / 'Data/AT/Bus_Route.geojson'
    excel_2023_file = base_path / 'Data/AT/Patronage_2023.xlsx'
    excel_2024_file = base_path / 'Data/AT/Patronage_2024.xlsx'
    frequencies_csv = base_path / 'Data/Processed/daily_bus_frequencies.csv'
    
    output_geojson = base_path / 'Data/Processed/processed_busroutes.geojson'
    
    process_routes(input_geojson, excel_2023_file, excel_2024_file, frequencies_csv, output_geojson)

if __name__ == "__main__":
    main()
