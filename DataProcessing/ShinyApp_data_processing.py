
import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx
import os
import math
import pandas as pd
from shapely.geometry import Point
from shapely.ops import unary_union
from matplotlib.colors import LinearSegmentedColormap
from mpl_toolkits.axes_grid1 import make_axes_locatable
import requests
from dotenv import load_dotenv
from matplotlib_scalebar.scalebar import ScaleBar
from matplotlib_map_utils.core.north_arrow import north_arrow

# Load environment variables
load_dotenv()
MAPBOX_ACCESS_TOKEN = os.getenv('MAPBOX_ACCESS_TOKEN')

# Define input file paths
INPUT_FILES = {
    'sa3_areas': "Data/Stats_NZ/statsnz-statistical-area-3-2023-generalised-SHP/statistical-area-3-2023-generalised.shp",
    'sa2_areas': "Data/Stats_NZ/statsnz-statistical-area-2-2023-generalised-SHP/statistical-area-2-2023-generalised.shp",
    'sa1_areas': "Data/Stats_NZ/statsnz-2018-census-electoral-population-meshblock-2020-SHP/2018-census-electoral-population-meshblock-2020.shp",
    'building_outlines': "Data/Stats_NZ/lds-nz-building-outlines-SHP/nz-building-outlines.shp",
    'population_data': "Data/Stats_NZ/statsnz-2023-census-population-change-by-statistical-area-2-SHP/2023-census-population-change-by-statistical-area-2.shp",
    'bus_stops': "Data/Processed/Bus_Stops_routes.geojson",
    'bus_routes': "Data/Processed/processed_busroutes.geojson"
}

# Define output directories
OUTPUT_DIRS = {
    'accessibility_maps': "outputs/accessibility_maps",
    'geojson': "outputs/geojson"
}

def load_input_data(study_circle=None):
    """Load all input data files and perform initial processing."""
    print("Loading input data files...")
    
    # Create study area if not provided
    if study_circle is None:
        study_circle = create_study_area()
    
    # Load SA3 areas first as they define the study boundary
    sa3_areas = load_and_process_areas(
        INPUT_FILES['sa3_areas'], 
        study_circle, 
        'SA3'
    )
    study_boundary = sa3_areas.geometry.union_all()
    study_boundary_buffer = study_boundary.buffer(400)
    
    # Load remaining statistical areas
    sa2_areas = load_and_process_areas(
        INPUT_FILES['sa2_areas'], 
        study_circle, 
        'SA2', 
        sa3_areas
    )
    sa1_areas = load_and_process_areas(
        INPUT_FILES['sa1_areas'], 
        study_circle, 
        'SA1', 
        sa3_areas
    )
    
    # Load and process building data
    building_outlines = gpd.read_file(INPUT_FILES['building_outlines']).to_crs('EPSG:2193')
    building_outlines = building_outlines[building_outlines.intersects(study_boundary)].copy()
    
    # Load and process population data
    population_data = gpd.read_file(INPUT_FILES['population_data']).to_crs('EPSG:2193')
    population_data['Population'] = population_data['VAR_1_3'].apply(lambda x: max(0, x))
    
    # Load transport infrastructure
    bus_stops = gpd.read_file(INPUT_FILES['bus_stops']).to_crs('EPSG:2193')
    bus_stops = bus_stops[bus_stops.intersects(study_boundary_buffer)].copy()
    
    bus_routes = gpd.read_file(INPUT_FILES['bus_routes']).to_crs('EPSG:2193')
    bus_routes = bus_routes[bus_routes.intersects(study_boundary_buffer)].copy()
    
    return {
        'sa3_areas': sa3_areas,
        'sa2_areas': sa2_areas,
        'sa1_areas': sa1_areas,
        'building_outlines': building_outlines,
        'population_data': population_data,
        'bus_stops': bus_stops,
        'bus_routes': bus_routes,
        'study_boundary': study_boundary,
        'study_boundary_buffer': study_boundary_buffer
    }

def create_study_area():
   # Create point and buffer for Auckland CBD study area
   return gpd.GeoDataFrame(
       geometry=[Point(174.763336, -36.848461)],
       crs='EPSG:4326'
   ).to_crs('EPSG:2193').geometry.buffer(100).iloc[0] # change this value to increase study radius(m) from Auckland CBD

def load_and_process_areas(filepath, study_circle, area_type, parent_areas=None):
   # Process Selected SA3's and all finer areas contained within
   areas = gpd.read_file(filepath).to_crs('EPSG:2193')
   
   if area_type == 'SA3':
       return areas[
           (areas.intersects(study_circle)) & 
           (~areas['SA32023__1'].str.contains('Inlets|Oceanic', na=False))
       ].copy()
   
   if parent_areas is None:
       raise ValueError(f"Parent areas must be provided for {area_type}")
   
   return areas[areas.geometry.within(parent_areas.geometry.union_all().buffer(10))].copy()

def get_isochrone(coordinates, contours_metres=[100, 200, 300, 400]):
   # Get walking isochrones from Mapbox API
   if not MAPBOX_ACCESS_TOKEN:
       return None
       
   try:
       response = requests.get(
           f"https://api.mapbox.com/isochrone/v1/mapbox/walking/{coordinates[0]},{coordinates[1]}", 
           params={
               "contours_meters": ",".join(map(str, contours_metres)),
               "polygons": "true",
               "access_token": MAPBOX_ACCESS_TOKEN,
               "generalize": 0
           }
       )
       return response.json() if response.status_code == 200 else None
   except requests.exceptions.RequestException:
       return None

def create_network_buffer(bus_stops_gdf):
   # Convert bus stops to WGS84 and get isochrones
   bus_stops_wgs84 = bus_stops_gdf.to_crs('EPSG:4326')
   isochrones = [
       gpd.GeoDataFrame.from_features(iso['features'], crs='EPSG:4326')
       for _, stop in bus_stops_wgs84.iterrows()
       if (iso := get_isochrone((stop.geometry.x, stop.geometry.y))) 
       and 'features' in iso
   ]
   
   return pd.concat(isochrones).to_crs('EPSG:2193') if isochrones else None

def calculate_building_accessibility(buildings, network_buffer):
   # Initialise accessibility fields
   buildings[['walking_distance', 'distance_band', 'is_accessible']] = None, None, False
   buildings['population_density'] = buildings['population'] / buildings.geometry.area * 1000000
   
   if network_buffer is not None and not network_buffer.empty:
       # Process each distance band (100m increments)
       for distance in [100, 200, 300, 400]:
           isochrones = network_buffer[network_buffer['contour'] == distance]
           if not isochrones.empty:
               combined_isochrone = unary_union(isochrones.geometry.to_list())
               unassigned_mask = buildings['walking_distance'].isnull()
               within_mask = buildings[unassigned_mask].geometry.intersects(combined_isochrone)
               
               if distance == 100:
                   buildings.loc[within_mask & unassigned_mask, ['walking_distance', 'distance_band']] = ["50", '0-100m']
               else:
                   lower = distance - 100
                   buildings.loc[within_mask & unassigned_mask, ['walking_distance', 'distance_band']] = [
                       str(lower + 50), f'{lower}-{distance}m'
                   ]
       
       # Mark remaining buildings beyond 400m
       unassigned_mask = buildings['walking_distance'].isnull()
       buildings.loc[unassigned_mask, ['walking_distance', 'distance_band']] = ["450", '400m+']
       buildings['is_accessible'] = buildings['walking_distance'].apply(lambda x: int(x) <= 400)
   
   return buildings

def calculate_accessibility_stats(buildings, statistical_areas):
    # Initialise statistics columns
    distance_bands = ['0-100m', '100-200m', '200-300m', '300-400m', '400m+']
    stats_columns = ['total_buildings', 'accessible_buildings', 'total_population', 
                    'accessible_population'] + distance_bands
    
    statistical_areas[stats_columns] = 0.0
    statistical_areas['accessibility_percentage'] = float('nan')
    
    for idx, area in statistical_areas.iterrows():
        area_buildings = buildings[buildings.geometry.centroid.within(area.geometry)]
        
        if not area_buildings.empty:
            # Calculate basic accessibility stats
            total_buildings = len(area_buildings)
            accessible_buildings = area_buildings['is_accessible'].sum()
            total_population = area_buildings['population'].sum()
            accessible_population = area_buildings[area_buildings['is_accessible']]['population'].sum()
            
            # Update distance band counts
            for band in distance_bands:
                count = len(area_buildings[area_buildings['distance_band'] == band])
                statistical_areas.at[idx, band] = int(count)
            
            # Update main statistics
            statistical_areas.at[idx, 'total_buildings'] = int(total_buildings)
            statistical_areas.at[idx, 'accessible_buildings'] = int(accessible_buildings)
            statistical_areas.at[idx, 'total_population'] = total_population
            statistical_areas.at[idx, 'accessible_population'] = accessible_population
            
            if total_buildings > 0:
                statistical_areas.at[idx, 'accessibility_percentage'] = (
                    accessible_buildings / total_buildings * 100
                )
    
    return statistical_areas

def calculate_bus_stop_statistics(bus_stops, network_buffer, buildings):
    # Initialise bus stops with accessibility columns
    bus_stops = bus_stops.copy()
    bus_stops[['accessible_buildings', 'accessible_population']] = 0
    
    if network_buffer is not None and not network_buffer.empty:
        # Only use 400m walking distance isochrones
        isochrones_400m = network_buffer[network_buffer['contour'] == 400]
        
        for idx, bus_stop in bus_stops.iterrows():
            stop_isochrone = isochrones_400m[isochrones_400m.geometry.intersects(bus_stop.geometry)]
            
            if not stop_isochrone.empty:
                accessible_buildings = buildings[buildings.geometry.intersects(stop_isochrone.geometry.iloc[0])]
                bus_stops.at[idx, 'accessible_buildings'] = int(len(accessible_buildings))
                bus_stops.at[idx, 'accessible_population'] = int(round(accessible_buildings['population'].sum()))
    
    return bus_stops.astype({'accessible_buildings': int, 'accessible_population': int})

def prepare_stats_for_export(stats_gdf, area_type, sa2_areas=None):
    output_gdf = stats_gdf.copy()
    output_gdf = output_gdf.drop(columns=['area_id']) if 'area_id' in output_gdf.columns else output_gdf
    
    # Calculate accessibility percentages
    output_gdf = output_gdf.rename(columns={'accessibility_percentage': 'building_acc_percentage'})
    output_gdf['pop_acc_percentage'] = (output_gdf['accessible_population'] / output_gdf['total_population'] * 100).fillna(0)
    
    # Define column mappings for different statistical area types
    column_mappings = {
        'SA3': {'SA32023_V1': 'area_id', 'SA32023__1': 'Name', 'LAND_AREA_': 'LAND_AREA'},
        'SA2': {'SA22023_V1': 'area_id', 'SA22023__1': 'Name', 'LAND_AREA_': 'LAND_AREA'},
        'SA1': {'MB2020_V2_': 'area_id', 'LAND_AREA_': 'LAND_AREA'}
    }
    
    # Special handling for SA1 areas
    if area_type == 'SA1':
        if sa2_areas is None:
            raise ValueError("SA2 areas must be provided for SA1 processing")
        output_gdf['centroid'] = output_gdf.geometry.centroid
        output_gdf['Name'] = output_gdf.apply(lambda row: 
            sa2_areas[sa2_areas.geometry.contains(row['centroid'])].iloc[0]['SA22023__1'] 
            if not sa2_areas[sa2_areas.geometry.contains(row['centroid'])].empty else 'Unknown', axis=1)
        output_gdf = output_gdf.drop(columns=['centroid'])
    
    output_gdf = output_gdf.rename(columns=column_mappings[area_type])
    
    # Define and ensure all required columns exist
    final_cols = ['area_id', 'Name', 'LAND_AREA', 'AREA_SQ_KM', 'Shape_Leng',
                 'total_buildings', 'accessible_buildings', 'building_acc_percentage',
                 'total_population', 'accessible_population', 'pop_acc_percentage',
                 '0-100m', '100-200m', '200-300m', '300-400m', '400m+', 'geometry']
    
    for col in final_cols:
        if col not in output_gdf.columns:
            output_gdf[col] = None
    
    return output_gdf[final_cols]

def create_visualisation(statistical_areas, area_type, output_path):
   # Create base map with accessibility percentage choropleth
   fig, ax = plt.subplots(figsize=(15, 15))
   areas_web_merc = statistical_areas.to_crs(epsg=3857)
   
   cmap = LinearSegmentedColormap.from_list('custom_greens',
       ['#ffffff', '#b2e0b1', '#6abf69', '#3d8c40', '#1a5928'])
   
   areas_web_merc.plot(
       column='accessibility_percentage', cmap=cmap, linewidth=0.5,
       edgecolor='black', ax=ax, vmin=0, vmax=100,
       missing_kwds={'color': 'lightgrey'}
   )
   
   try:
       ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, alpha=0.5)
   except Exception:
       pass
       
   north_arrow(ax=ax, location="upper right", rotation={"crs":3857, "reference":"center"})
   scalebar = ScaleBar(1, "m", length_fraction=0.25, location="lower left",
                      pad=0.5, border_pad=0, sep=5, frameon=True, color="black")
   ax.add_artist(scalebar)
   
   divider = make_axes_locatable(ax)
   cax = divider.append_axes("right", size="5%", pad=0.1)
   sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=0, vmax=100))
   cbar = plt.colorbar(sm, cax=cax)
   cbar.set_label('Percentage of Buildings with Bus Stop Access (400m walking distance)')
   
   plt.title(f'{area_type} Level Building Accessibility to Bus Stops\n'
            'Auckland City Centre - 2km Radius', pad=20, fontsize=16)
   
   total_buildings = int(statistical_areas['total_buildings'].sum())
   accessible_buildings = int(statistical_areas['accessible_buildings'].sum())
   total_population = statistical_areas['total_population'].sum()
   accessible_population = statistical_areas['accessible_population'].sum()
   
   stats_text = (
       f'Total Buildings: {total_buildings:,}\n'
       f'Accessible Buildings: {accessible_buildings:,} ({accessible_buildings/total_buildings*100:.1f}%)\n'
       f'Total Population: {int(total_population):,}\n'
       f'Accessible Population: {int(accessible_population):,} ({accessible_population/total_population*100:.1f}%)'
   )
   
   plt.text(0.7, 0.02, stats_text, transform=ax.transAxes,
           bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'),
           fontsize=12, verticalalignment='bottom')
   
   ax.axis('off')
   plt.tight_layout()
   plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.5)
   plt.close()

def assign_population(building_outlines, meshblocks):
    # Initialise population data
    meshblocks['VAR_1_3'] = meshblocks['VAR_1_3'].fillna(0).clip(lower=0)
    building_outlines['population'] = 0.0
    building_outlines['area'] = building_outlines.geometry.area
    
    # Process only meshblocks with population
    for idx, meshblock in meshblocks[meshblocks['VAR_1_3'] > 0].iterrows():
        # Find buildings in meshblock that could contain population
        intersecting_buildings = building_outlines[
            (building_outlines.intersects(meshblock.geometry)) &
            (building_outlines['use'].isin(['Unknown', 'Residential', '']))
        ]
        
        if not intersecting_buildings.empty:
            # Calculate area-weighted population distribution
            sqrt_areas = {idx: math.sqrt(area) for idx, area 
                        in building_outlines.loc[intersecting_buildings.index, 'area'].items()}
            total_sqrt_area = sum(sqrt_areas.values())
            
            if total_sqrt_area > 0:
                # Assign population to buildings based on sqrt area proportion
                for building_idx, sqrt_area in sqrt_areas.items():
                    population_share = min(meshblock['VAR_1_3'] * sqrt_area / total_sqrt_area, 100)
                    building_outlines.loc[building_idx, 'population'] += population_share
    
    return building_outlines

def main():
    # Create output directories
    for directory in OUTPUT_DIRS.values():
        os.makedirs(directory, exist_ok=True)
    
    print("\nInitialising analysis for Auckland CBD...")
    study_circle = create_study_area()
    
    # Load all input data
    data = load_input_data(study_circle)
    
    print("Processing building data and population...")
    building_outlines = assign_population(data['building_outlines'], data['population_data'])
    
    print("Calculating accessibility metrics...")
    network_buffer = create_network_buffer(data['bus_stops'])
    building_outlines = calculate_building_accessibility(building_outlines, network_buffer)
    
    print("Processing transport infrastructure...")
    bus_stops_with_stats = calculate_bus_stop_statistics(
        data['bus_stops'], 
        network_buffer, 
        building_outlines
    )
    
    print("Generating statistics and visualisations...")
    # Process buildings for export
    processed_buildings = building_outlines[
        ['population', 'walking_distance', 'is_accessible', 'population_density', 'geometry']
    ].rename(columns={'is_accessible': 'has_access'})
    
    # Calculate statistics for each area type
    sa3_stats = calculate_accessibility_stats(building_outlines, data['sa3_areas'])
    sa2_stats = calculate_accessibility_stats(building_outlines, data['sa2_areas'])
    sa1_stats = calculate_accessibility_stats(building_outlines, data['sa1_areas'])
    
    # Prepare exports
    sa3_output = prepare_stats_for_export(sa3_stats, 'SA3')
    sa2_output = prepare_stats_for_export(sa2_stats, 'SA2')
    sa1_output = prepare_stats_for_export(sa1_stats, 'SA1', data['sa2_areas'])
    
    # Save all GeoJSON outputs
    outputs = {
        'processed_buildings.geojson': processed_buildings,
        'processed_busstops.geojson': bus_stops_with_stats,
        'processed_busroutes.geojson': data['bus_routes'],
        'sa3_stats.geojson': sa3_output,
        'sa2_stats.geojson': sa2_output,
        'sa1_stats.geojson': sa1_output
    }
    
    for name, data in outputs.items():
        data.to_file(
            os.path.join(OUTPUT_DIRS['geojson'], name), 
            driver='GeoJSON'
        )
    
    # Create visualisations
    for area_type, stats in [
        ('SA3', sa3_stats), 
        ('SA2', sa2_stats), 
        ('SA1', sa1_stats)
    ]:
        create_visualisation(
            stats, 
            area_type, 
            os.path.join(OUTPUT_DIRS['accessibility_maps'], f'{area_type.lower()}_accessibility.png')
        )
    
    print("\nAnalysis complete!")
    print(f"Visualisations saved to: {OUTPUT_DIRS['accessibility_maps']}")
    print(f"GeoJSON files saved to: {OUTPUT_DIRS['geojson']}")

if __name__ == "__main__":
    main()