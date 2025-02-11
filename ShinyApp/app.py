from pathlib import Path
import geopandas as gpd
import ipyleaflet as leaf
import numpy as np
import ipywidgets
from faicons import icon_svg
from shiny import App, Inputs, Outputs, Session, reactive, render, ui
from shinywidgets import output_widget, render_widget, render_plotly
from branca.colormap import LinearColormap
import plotly.graph_objects as go
from utils import create_distance_histogram, create_density_plot

# Load data
app_dir = Path(__file__).parent
sa1_data = gpd.read_file('data/sa1_stats.geojson').to_crs('EPSG:4326').__geo_interface__
sa2_data = gpd.read_file('data/sa2_stats.geojson').to_crs('EPSG:4326').__geo_interface__
sa3_data = gpd.read_file('data/sa3_stats.geojson').to_crs('EPSG:4326').__geo_interface__
bus_stops_data = gpd.read_file('data/processed_busstops.geojson').to_crs('EPSG:4326').__geo_interface__
buildings_data = gpd.read_file('data/processed_buildings.geojson').to_crs('EPSG:4326').__geo_interface__
bus_route_data = gpd.read_file('data/processed_busroutes.geojson').to_crs('EPSG:4326').__geo_interface__

# Mapbox configuration
MAPBOX_TOKEN = "pk.eyJ1Ijoic2FsdS1mZXJyZXJlIiwiYSI6ImNsdnd6cDJyczA0eHYybHBmdTFzZGRhdXQifQ.U2JVnSqiy2LsMwdd1Rqesg"

# Variables for dropdown selection
vars = {
    "building_acc_percentage": "Building Accessibility",
    "pop_acc_percentage": "Population Accessibility"
}

area_sizes = {
    "sa3": "SA3 (Large)",
    "sa2": "SA2 (Medium)",
    "sa1": "SA1 (Small)",
    "none": "None"
}

def create_building_legend():
    # Create building distance colour legend items 
    colors = [
        ('rgb(0, 0, 85)', '0-100m'),
        ('rgb(0, 0, 185)', '100-200m'),
        ('rgb(0, 127, 255)', '200-300m'),
        ('rgb(135, 206, 235)', '300-400m'),
        ('rgb(232, 255, 252)', '400m+')
    ]
    
    legend_items = [
        f"""<div style="display: inline-block; text-align: center; margin-left: {'5px' if i == 0 else '40px'}">
            <div style="width: 48px; height: 24px; border: 1px solid black; background-color: {color};"></div>
            <div style="font-size: 12px; margin-top: 4px;">{label}</div>
        </div>"""
        for i, (color, label) in enumerate(colors)
    ]
    return ui.HTML(f"""<div style="display: flex; justify-content: flex-start; align-items: center;">{''.join(legend_items)}</div>""")

## UI Layout      
app_ui = ui.page_fluid(
    ui.page_navbar(
        ui.nav_spacer(),
        ui.nav_panel(
            "Area Map",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.div(
                        ui.output_text("sidebar_title"),
                        ui.tooltip(
                            icon_svg("circle-info"),
                            ui.output_text("tooltip_text")
                        ),
                        class_="d-inline-flex align-items-center gap-2 mb-1"
                    ),
                    ui.output_text_verbatim("area_info"),
                    ui.div(
                        output_widget("distance_chart"),
                        class_="d-flex justify-content-center"
                    ),
                    ui.div(
                        output_widget("density_plot"),
                        class_="d-flex justify-content-center"
                    ),
                    position="right",
                    width=400,
                ),
                ui.card(
                    ui.card_header(
                        "Map showing ",
                        ui.input_select("variable", None, vars, width="auto"),
                        "Area size ",
                        ui.input_select("area_level", None, area_sizes, width="auto"),
                        class_="d-flex align-items-center gap-3"
                    ),
                    output_widget("area_map"),
                    ui.card_footer(
                        ui.div(
                            ui.div(
                                ui.div("Created by: Salu Rodriguez-Ferrere"),
                                ui.div([
                                    "Source: ",
                                    ui.a("https://github.com/dataandcrowd/aucklandbus.git", 
                                        href="https://github.com/dataandcrowd/aucklandbus.git", 
                                        target="_blank")
                                ]),
                                class_="d-flex flex-column gap-0"
                            ),
                            ui.div(
                                ui.div("Data from: Auckland Transport"),
                                ui.div("Last updated: December 21, 2023"),
                                class_="ms-auto"
                            ),
                            class_="d-flex justify-content-between w-100"
                        )
                    ),
                    full_screen=True
                )
            )
        ),
        ui.nav_panel(
            "Features Map",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.row(
                        ui.column(6,
                            ui.div(
                                "Building Distances",
                                ui.tooltip(
                                    icon_svg("circle-info"),
                                    "Walking distance from buildings to nearest bustop"
                                ),
                                class_="d-inline-flex align-items-center gap-2 mb-0"
                            ),
                        ),
                    ),
                    ui.div(
                        create_building_legend(),
                        class_='mb-2'
                    ),
                    ui.row(
                        ui.column(6,
                            ui.div(
                                ui.div(
                                    "Bus Stops",
                                    ui.tooltip(
                                        icon_svg("circle-info"),
                                        "Displays information on the area within a 400m walking distance of the selected bus stop"
                                    ),
                                    class_="d-inline-flex align-items-center gap-2 mb-4"
                                ),
                                ui.output_text_verbatim("stop_info"),
                                ui.div(
                                    output_widget("buildings_density"),
                                    class_="mb-4"
                                ),
                                output_widget("population_density"),
                                style="border: 1px solid #dee2e6; padding: 8px; border-radius: 4px; margin: -4px 0;"
                            ),
                            style="padding: 0 4px;"
                        ),
                        ui.column(6,
                            ui.div(
                                ui.div(
                                    "Bus Routes",
                                    ui.tooltip(
                                        icon_svg("circle-info"),
                                        "Displays route information of the selected bus route"
                                    ),
                                    class_="d-inline-flex align-items-center gap-2 mb-4"
                                ),
                                ui.output_text_verbatim("route_info"),
                                ui.div(
                                    output_widget("patronage_density"),
                                    class_="mb-4"
                                ),
                                output_widget("trips_density"),
                                style="border: 1px solid #dee2e6; padding: 8px; border-radius: 4px; margin: -4px 0;"
                            ),
                            style="padding: 0 4px;"
                        ),
                    ),
                    position="right",
                    width=650,
                ),
                ui.card(
                    ui.card_header(
                        ui.div(
                            ui.div(
                                ui.input_checkbox_group(
                                    "feature_types",
                                    None,
                                    {"bus_stops": "Bus Stops", "bus_routes": "Bus Routes", "buildings": "Buildings"},
                                    inline=True
                                ),
                                style="margin-right: 8px;"
                            ),
                            ui.tooltip(
                                icon_svg("circle-info"),
                                "Zoom in to load building outlines"
                            ),
                            class_="d-flex align-items-center"
                        ),
                        class_="d-flex align-items-center gap-3"
                    ),
                    output_widget("feature_map"),
                    ui.card_footer(
                        ui.div(
                            ui.div(
                                ui.div("Created by: Salu Rodriguez-Ferrere"),
                                ui.div([
                                    "Source: ",
                                    ui.a("https://github.com/dataandcrowd/aucklandbus.git", 
                                        href="https://github.com/dataandcrowd/aucklandbus.git", 
                                        target="_blank")
                                ]),
                                class_="d-flex flex-column gap-0"
                            ),
                            ui.div(
                                ui.div("Data from: Auckland Transport"),
                                ui.div("Last updated: December 21, 2023"),
                                class_="ms-auto"
                            ),
                            class_="d-flex justify-content-between w-100"
                        )
                    ),
                    full_screen=True
                )
            )
        ),
        title=ui.div(
            ui.img(src="UoA-Logo-DarkBlue.png", height="70px", width="70px", class_= "my-0 me-4"),
            "Auckland Bus Stop Accessibility Explorer",
            class_="d-flex align-items-center"
        ),
        header=ui.tags.style("""
            .navbar { 
                padding-top: 0 !important;
                padding-bottom: 0 !important;
                min-height: 65px !important;
            }
        """),
        window_title="Auckland Bus Stop Accessibility Explorer",
        bg="#0073BD",
        inverse=True,
        fillable=True
    )
)

## Helper Functions

def calculate_total_stats(data, variable):
    #Calculate total statistics for all areas
    total_acc = total_count = 0
    distance_totals = {f'{i}-{i+100}m' if i < 400 else '400m+': 0 for i in range(0, 401, 100)}
    
    for feature in data['features']:
        props = feature['properties']
        if props[variable] is not None:
            is_building = variable == "building_acc_percentage"
            metric = 'total_buildings' if is_building else 'total_population'
            acc_type = 'building_acc_percentage' if is_building else 'pop_acc_percentage'
            
            total_acc += props[acc_type] * props[metric]
            total_count += props[metric]
            
            for dist_key in distance_totals:
                distance_totals[dist_key] += props.get(dist_key, 0)
    
    return {'percentage': total_acc / total_count, 'total': total_count, **distance_totals} if total_count > 0 else None

def create_map():
    #Get map from mapbox api
    m = leaf.Map(center=(-36.8485, 174.7633), zoom=12, scroll_wheel_zoom=True)
    m.add_layer(leaf.TileLayer(
        url=f'https://api.mapbox.com/styles/v1/mapbox/streets-v11/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_TOKEN}',
        attribution='© Mapbox',
        name='Mapbox Streets'
    ))
    return m

def create_color_scale(features, variable):
    #Create colour scale for statistical areas
    percentages = [f['properties'][variable] for f in features if f['properties'][variable] is not None]
    avg = sum(percentages) / len(percentages)
    min_val = min(percentages)
    max_val = max(percentages)

    # Create two separate color scales
    lower_scale = LinearColormap(['red', 'white'], vmin=min_val, vmax=avg)
    upper_scale = LinearColormap(['white', 'blue'], vmin=avg, vmax=max_val)

    # Return a combined color function
    def combined_color_scale(value):
        if value <= avg:
            return lower_scale(value)
        else:
            return upper_scale(value)

    return combined_color_scale

def create_style(feature, color_scale, variable):
    base_style = {'color': 'black', 'weight': 1, 'fillOpacity': 0.7}
    percentage = feature['properties'][variable]

    return {**base_style, 'fillColor': color_scale(percentage) if percentage is not None else '#808080'}

def create_route_style(feature):
    #Create map styling for bus route lines
    patronage = feature['properties'].get('avg_daily_patrons')
    if patronage is None:
        return {'color': '#808080', 'weight': 3, 'opacity': 0.7}
    
    patronage_values = [f['properties'].get('avg_daily_patrons', 0) 
                       for f in bus_route_data['features'] 
                       if f['properties'].get('avg_daily_patrons') is not None]
    
    color_scale = LinearColormap(
        colors=['green', 'yellow', 'red'],
        vmin=min(patronage_values),
        vmax=np.percentile(patronage_values, 90)
    )
    return {'color': color_scale(patronage), 'weight': 3, 'opacity': 0.7}

def create_building_layers(feature_map, buildings_data):
    # Create building layer with effecicent loading 
    buildings_layer = leaf.GeoJSON(
        data={"type": "FeatureCollection", "features": []},
        style={'weight': 1}, 
        hover_style={'fillOpacity': 0},
        style_callback=building_style,
        interactive = False,
        name="buildings"
    )
    # Only load in buildings within view
    def get_features_in_bounds(bounds):
        if not bounds:
            return []
        
        lat_min, lat_max = sorted([bounds[0][0], bounds[1][0]])
        lon_min, lon_max = sorted([bounds[0][1], bounds[1][1]])
        
        return [
            feature for feature in buildings_data['features']
            if any(lat_min <= coord[1] <= lat_max and lon_min <= coord[0] <= lon_max
                  for coord in feature['geometry']['coordinates'][0])
        ]
    #Only load buildings once sufficiently zoomed in
    def handle_view_change(change):
        buildings_layer.data = {
            "type": "FeatureCollection",
            "features": get_features_in_bounds(feature_map.bounds) if feature_map.zoom >= 15 else []
        }
    
    feature_map.observe(handle_view_change, names=['zoom', 'bounds'])
    handle_view_change(None)

    return buildings_layer

def building_style(feature):
    distance = feature['properties'].get('walking_distance')
    if distance is None:
        return {'color': 'black', 'fillColor': '#808080', 'weight': 1, 'fillOpacity': 0.7}
    
    colors = {
        50: 'rgb(0, 0, 85)',
        150: 'rgb(0, 0, 185)',
        250: 'rgb(0, 127, 255)',
        350: 'rgb(135, 206, 235)',
        float('inf'): 'rgb(232, 255, 252)'
    }
    color = next(v for k, v in colors.items() if float(distance) <= k)
    return {'color': 'black', 'fillColor': color, 'weight': 1, 'fillOpacity': 0.7}

## Server Functions

def server(input: Inputs, output: Outputs, session: Session):

    selected_area, selected_stop, selected_route = map(reactive.Value, [None] * 3)
    feature_layers = reactive.Value({'buildings': None, 'bus_routes': None, 'bus_stops': []})
    feature_map_initialised = reactive.Value(False)
    clicked_feature = reactive.Value(False)

    def create_stop_marker(feature):
        # Create bus stop markers with popups 
        marker = leaf.CircleMarker(
            location=(feature['geometry']['coordinates'][1], feature['geometry']['coordinates'][0]),
            popup=ipywidgets.HTML(
                f"""<b>{feature['properties'].get('STOPNAME', 'Unknown')}</b><br/>
                Stop Code: {feature['properties'].get('STOPCODE', 'Unknown')}<br/>
                Routes: {feature['properties'].get('routes_str', 'Unknown')}<br/>
                Buildings with Access: {feature['properties'].get('accessible_buildings', 0):,}<br/>
                Population with Access: {feature['properties'].get('accessible_population', 0):,}"""
            ),
            radius=4, weight=2, color='purple',
            name=f"stop-{feature['properties'].get('STOPCODE', 'Unknown')}",
            fill=True, fill_opacity=0, opacity=0
        )
        marker.on_click(lambda **kwargs: selected_stop.set(feature['properties']))
        return marker
    
    @render_widget
    def area_map():
        # Initialise area map
        m = create_map()
        m.on_interaction(lambda **kwargs: handle_map_click(kwargs, clicked_feature, selected_area))
        area_layer = leaf.GeoJSON(
            data={"type": "FeatureCollection", "features": []},
            style={'opacity': 1, 'fillOpacity': 0.7, 'weight': 1},
            hover_style={'fillOpacity': 1}
        )
        m.add_layer(area_layer)
        m.area_layer = area_layer
        return m

    @reactive.Effect
    @reactive.event(input.area_level, input.variable)
    def handle_areas():
        # Process changes in statistical area map
        map_widget = area_map.widget
        
        if input.area_level() == 'none':
            map_widget.area_layer.data = {"type": "FeatureCollection", "features": []}
            selected_area.set(None)
            return

        current_data = {
            'sa1': sa1_data,
            'sa2': sa2_data,
            'sa3': sa3_data
        }[input.area_level()]

        color_scale = create_color_scale(current_data['features'], input.variable())
        map_widget.area_layer.style_callback = lambda feature: create_style(feature, color_scale, input.variable())

        def on_feature_click(feature, **kwargs):
            clicked_feature.set(True)
            selected_area.set(feature['properties'])
            map_widget.layers = tuple(l for l in map_widget.layers if not isinstance(l, leaf.Popup))
            
            coords = feature['geometry']['coordinates'][0] if feature['geometry']['type'] == 'Polygon' else feature['geometry']['coordinates'][0][0]
            center = (sum(coord[1] for coord in coords) / len(coords), sum(coord[0] for coord in coords) / len(coords))

            import time
            time.sleep(0.1)
            map_widget.add_layer(leaf.Popup(
                location=center,
                child=ipywidgets.HTML(create_area_popup_content(feature['properties'])),
                close_button=True, auto_close=True, close_on_escape_key=True
            ))

        map_widget.area_layer.on_click(on_feature_click)
        map_widget.area_layer.data = current_data

    @render_widget
    def feature_map():
        # Initialise features map
        m = create_map()
        
        buildings_layer = create_building_layers(m, buildings_data)
        buildings_layer.style = {'opacity': 0, 'fillOpacity': 0, 'weight': 0}
        
        routes_layer = leaf.GeoJSON(
            data={'type': 'FeatureCollection', 
                  'features': sorted(bus_route_data['features'],
                                  key=lambda x: x['properties'].get('avg_daily_patrons', 0))},
            style={'opacity': 0, 'weight': 0},
            hover_style={'opacity': 0},
            style_callback=create_route_style,
            interactive=False
        )
        routes_layer.on_click(lambda feature, **kwargs: selected_route.set(feature['properties']))
        
        stop_layer_group = leaf.LayerGroup()
        for feature in bus_stops_data['features']:
            stop_layer_group.add_layer(create_stop_marker(feature))
        
        m.add_layer(buildings_layer)
        m.add_layer(routes_layer)
        
        feature_layers.set({
            'buildings': buildings_layer,
            'bus_routes': routes_layer,
            'bus_stops': stop_layer_group
        })
        feature_map_initialised.set(True)
        return m

    @reactive.Effect
    @reactive.event(input.feature_types)
    def handle_features():
        # Process changes in features map
        layers = feature_layers()
        if not layers:
            return
        
        selected_types = input.feature_types() or []
        prev_types = getattr(handle_features, 'prev_types', set())
        handle_features.prev_types = set(selected_types)
        
        if layers['buildings']:
            should_be = 'buildings' in selected_types
            update_building_layer(layers['buildings'], should_be)
        
        if layers['bus_routes']:
            should_be = 'bus_routes' in selected_types
            update_route_layer(layers['bus_routes'], should_be)
        
        if layers['bus_stops'] and 'bus_stops' in (set(selected_types) ^ prev_types):
            update_stop_layer(layers['bus_stops'], 'bus_stops' in selected_types, feature_map.widget)

    def create_area_popup_content(props):
        return f"""<div style='min-width: 200px;'>
            <b>{props.get('Name', 'Unknown')}</b><br/>
            ID: {props.get('area_id', 'Unknown')}<br/>
            Building Accessibility: {props.get('building_acc_percentage', 0):.1f}%<br/>
            Total Buildings: {props.get('total_buildings', 0):,}<br/>
            Population Accessibility: {props.get('pop_acc_percentage', 0):.1f}%<br/>
            Total Population: {round(props.get('total_population', 0)):,}
        </div>"""

    def handle_map_click(kwargs, clicked_feature, selected_area):
        if kwargs.get('type') == 'click' and not clicked_feature.get():
            selected_area.set(None)
        clicked_feature.set(False)

    def update_building_layer(layer, visible):
        layer.interactive = visible
        layer.style = {'opacity': 1 if visible else 0, 'fillOpacity': 0.6 if visible else 0, 'weight': 1}
        layer.hover_style = {'fillOpacity': 1} if visible else {'opacity': 0}

    def update_route_layer(layer, visible):
        layer.interactive = visible
        layer.style = {'opacity': 1 if visible else 0, 'weight': 3}
        layer.hover_style = {'weight': 6} if visible else {'opacity': 0}

    def update_stop_layer(layer, visible, map_widget):
        if layer in map_widget.layers:
            map_widget.remove_layer(layer)
        
        if visible:
            for marker in layer.layers:
                marker.interactive = True
                marker.opacity = 1
                marker.fill_opacity = 0.6
            map_widget.add_layer(layer)

    @render.text
    def area_info():
        area = selected_area()
        if area is None:
            total_stats = calculate_total_stats(sa3_data, input.variable())
            if not total_stats:
                return "Error calculating overall statistics"
            metric = "Buildings" if input.variable() == "building_acc_percentage" else "Population"
            return f"Overall Statistics\nAverage Accessibility: {total_stats['percentage']:.1f}%\nTotal {metric}: {total_stats['total']:.0f}"
        
        try:
            is_building = input.variable() == "building_acc_percentage"
            metric = "buildings" if is_building else "population"
            acc_type = "building_acc_percentage" if is_building else "pop_acc_percentage"
            total_type = f"total_{metric}"
            return f"{area['Name']}\nAccessibility: {area[acc_type]:.1f}%\nTotal {metric.capitalize()}: {area[total_type]:.0f}"
        except Exception:
            return "No buildings in selected area"

    @render.text
    def stop_info():
        feature = selected_stop()
        return "Click a bus stop to see details" if not feature else \
               f"Stop Name: {feature.get('STOPNAME', 'Unknown stop')}\n" \
               f"Routes: {feature.get('routes_str', 'Unknown')}\n" \
               f"Accessibe Buildings: {feature.get('accessible_buildings', 'Unknown')}\n" \
               f"Accessible Population: {feature.get('accessible_population', 'Unknown')}"

    @render.text
    def route_info():
        feature = selected_route()
        return "Click a bus route to see details" if not feature or 'ROUTENUMBER' not in feature else \
               f"Route Name: '{feature.get('ROUTENUMBER', 'Unknown route')}'\n" \
               f"Service Days: {feature.get('service_days', 'Unknown')}\n" \
               f"Average Daily Passengers: {feature.get('avg_daily_patrons', 'Unknown')}\n" \
               f"Average Daily Trips: {feature.get('avg_daily_trips', 'Unknown')}"

    @render.text
    def sidebar_title(): 
        return vars[input.variable()]

    @render.text
    def tooltip_text():
        return "Percent of buildings in the area that are within a 400m walking distance to a bus stop" \
               if input.variable() == "building_acc_percentage" else \
               "Percent of population in the area that are within a 400m walking distance to a bus stop"

    def create_density_params(feature, value_key, name_key):
        if feature is None:
            return None, None
        return feature.get(value_key), feature.get(name_key)

    distance_chart_data = reactive.Value(None)
    density_plot_data = reactive.Value(None)

    @reactive.Effect
    @reactive.event(input.variable, input.area_level, selected_area)
    def update_chart_data():
        area = selected_area.get()
        if area is None:
            total_stats = calculate_total_stats(sa3_data, input.variable())
            if total_stats:
                distance_chart_data.set(('total_stats', total_stats, input.variable(), True))
        else:
            distance_chart_data.set((area, input.variable(), False))
        
        data = {'sa1': sa1_data, 'sa2': sa2_data}.get(input.area_level(), sa3_data)
        selected_value, selected_name = create_density_params(area, input.variable(), 'Name')
        is_building = input.variable() == "building_acc_percentage"
        title = "Distribution of Building Accessibility" if is_building else "Distribution of Population Accessibility"
        x_axis = "Building Accessibility Percentage" if is_building else "Population Accessibility Percentage"
        density_plot_data.set((data, input.variable(), selected_value, selected_name, title, x_axis))

    @render_plotly
    def distance_chart():
        if not hasattr(distance_chart, '_fig'):
            distance_chart._fig = go.Figure()
            distance_chart._fig.update_layout(uirevision="static")
        
        data = distance_chart_data.get()
        if data is None:
            return distance_chart._fig
        
        area = {'total_stats': data[1]} if len(data) == 4 else data[0]
        variable = data[2] if len(data) == 4 else data[1]
        is_overall = len(data) == 4
        
        return create_distance_histogram(area, variable, is_overall, distance_chart._fig)

    @render_plotly
    def density_plot():
        data = density_plot_data.get()
        return create_density_plot(*data) if data else go.Figure()

    @render_plotly
    def buildings_density():
        feature = selected_stop()
        selected_value, selected_name = create_density_params(feature, 'accessible_buildings', 'STOPNAME')
        return create_density_plot(bus_stops_data, 'accessible_buildings', selected_value, selected_name,
                            "Accessible Buildings Distribution", "Number of Buildings")

    @render_plotly
    def population_density():
        feature = selected_stop()
        selected_value, selected_name = create_density_params(feature, 'accessible_population', 'STOPNAME')
        return create_density_plot(bus_stops_data, 'accessible_population', selected_value, selected_name,
                            "Accessible Population Distribution", "Population")

    @render_plotly
    def patronage_density():
        feature = selected_route()
        if not feature or 'ROUTENUMBER' not in feature:
            feature = None
        selected_value, selected_name = create_density_params(feature, 'avg_daily_patrons', 'ROUTENUMBER')
        return create_density_plot(bus_route_data, 'avg_daily_patrons', selected_value, selected_name,
                            "Daily Passenger Distribution", "Average Daily Passengers")

    @render_plotly
    def trips_density():
        feature = selected_route()
        if not feature or 'ROUTENUMBER' not in feature:
            feature = None
        selected_value, selected_name = create_density_params(feature, 'avg_daily_trips', 'ROUTENUMBER')
        return create_density_plot(bus_route_data, 'avg_daily_trips', selected_value, selected_name,
                            "Daily Trips Distribution", "Average Daily Trips")

app = App(app_ui, server, static_assets=app_dir / "www")