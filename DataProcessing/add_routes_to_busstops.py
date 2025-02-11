import pandas as pd
import geopandas as gpd
from collections import defaultdict

def get_routes_per_stop(stops_file, stop_times_file, trips_file, routes_file):
    # Read the GTFS files
    stops = pd.read_csv(stops_file)
    stop_times = pd.read_csv(stop_times_file)
    trips = pd.read_csv(trips_file)
    routes = pd.read_csv(routes_file)
    
    # Merge trips with stop_times to get route_id for each stop
    stop_routes = stop_times.merge(trips[['trip_id', 'route_id']], on='trip_id')
    
    # Merge with routes to get route short names
    stop_routes = stop_routes.merge(
        routes[['route_id', 'route_short_name']], 
        on='route_id'
    )
    
    # Group by stop_id and collect unique route short names
    routes_by_stop = defaultdict(set)
    for _, row in stop_routes.iterrows():
        routes_by_stop[row['stop_id']].add(row['route_short_name'])
    
    # Convert sets to sorted lists
    routes_by_stop = {k: sorted(list(v)) for k, v in routes_by_stop.items()}
    
    return routes_by_stop

def update_geojson(geojson_file, routes_by_stop, output_file):
    # Read the GeoJSON file
    gdf = gpd.read_file(geojson_file)
    
    # Add new column with route lists
    gdf['routes'] = gdf['STOPID'].map(lambda x: routes_by_stop.get(x, []))
    
    # Add column with count of routes
    gdf['route_count'] = gdf['routes'].map(len)
    
    # Add a comma-separated string of routes for easier viewing
    gdf['routes_str'] = gdf['routes'].map(lambda x: ', '.join(map(str, x)))
    
    # Save updated GeoJSON
    gdf.to_file(output_file, driver='GeoJSON')
    
    return gdf

# Example usage:
if __name__ == "__main__":
    # File paths
    stops_file = "Data/gtfs_data/stops.txt"
    stop_times_file = "Data/gtfs_data/stop_times.txt"
    trips_file = "Data/gtfs_data/trips.txt"
    routes_file = "Data/gtfs_data/routes.txt"
    geojson_file = "Data/AT/Bus_Stop.geojson"
    output_file = "Data/Processed/bus_stops_routes.geojson"
    
    # Get routes for each stop
    routes_by_stop = get_routes_per_stop(
        stops_file, 
        stop_times_file, 
        trips_file, 
        routes_file
    )
    
    # Update GeoJSON with routes
    updated_gdf = update_geojson(
        geojson_file,
        routes_by_stop,
        output_file
    )
    
    # Print sample of results
    print(f"Result saved to {output_file}")
 