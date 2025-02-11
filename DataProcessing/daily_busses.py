import pandas as pd

def load_gtfs_data():
    trips_df = pd.read_csv('Data/gtfs_data/trips.txt')
    calendar_df = pd.read_csv('Data/gtfs_data/calendar.txt')
    routes_df = pd.read_csv('Data/gtfs_data/routes.txt')
    return trips_df, calendar_df, routes_df

def create_service_day_mapping(calendar_df):
    days_of_week = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    service_days = {}
    for _, row in calendar_df.iterrows():
        service_days[row['service_id']] = {day: row[day] for day in days_of_week}
    return service_days

def calculate_daily_frequencies(trips_df, service_days, routes_df):
    route_frequencies = {}
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    days_lower = [day.lower() for day in days]
    
    for route_id in trips_df['route_id'].unique():
        route_trips = trips_df[trips_df['route_id'] == route_id]
        daily_counts = {day: 0 for day in days}
        
        for service_id in route_trips['service_id'].unique():
            if service_id in service_days:
                num_trips = len(route_trips[route_trips['service_id'] == service_id])
                for day, day_lower in zip(days, days_lower):
                    if service_days[service_id][day_lower]:
                        daily_counts[day] += num_trips
                        
        route_frequencies[route_id] = daily_counts

    results_df = pd.DataFrame.from_dict(route_frequencies, orient='index')
    results_df = results_df.reset_index().rename(columns={'index': 'route_id'})
    results_df = results_df.merge(
        routes_df[['route_id', 'route_short_name']],
        on='route_id',
        how='left'
    )
    
    column_order = ['route_id', 'route_short_name'] + days
    return results_df[column_order]

def main():
    trips_df, calendar_df, routes_df = load_gtfs_data()
    service_days = create_service_day_mapping(calendar_df)
    results_df = calculate_daily_frequencies(trips_df, service_days, routes_df)
    
    output_path = 'Data/Processed/daily_bus_frequencies.csv'
    results_df.to_csv(output_path, index=False)
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    main()