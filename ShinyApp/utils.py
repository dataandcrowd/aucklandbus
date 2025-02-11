import plotly.graph_objects as go
import numpy as np
from scipy import stats

def create_density_plot(data, variable, selected_value=None, selected_name=None, title=None, x_axis_title=None, fig=None):
    
    values = [f['properties'][variable] for f in data['features'] if f['properties'][variable] is not None]
    if not values:
        return fig if fig else go.Figure()

    kde = stats.gaussian_kde(values)
    x_range = np.linspace(min(values), max(values), 200)
    is_route_plot = variable in ['avg_daily_patrons', 'avg_daily_trips']
    
    base_color = 'rgb(144, 238, 144)' if is_route_plot else 'rgb(135, 206, 250)'
    colors = {
        'line': base_color,
        'fill': base_color.replace('rgb', 'rgba').replace(')', ', 0.2)')
    }

    if fig is None or not fig.data:
        fig = go.Figure(
            data=[go.Scatter(
                x=x_range, y=kde(x_range),
                mode='lines', showlegend=False,
                line=dict(color=colors['line'], width=2),
                fill='tozeroy', fillcolor=colors['fill']
            )],
            layout=dict(
                title=title or "Distribution",
                plot_bgcolor='white', paper_bgcolor='white',
                xaxis=dict(title=x_axis_title or "Value", showgrid=True, gridwidth=1, 
                          gridcolor='rgb(230, 230, 230)', zeroline=False),
                yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, title=None),
                showlegend=False, margin=dict(l=20, r=20, t=40, b=20),
                height=200, width=300, font=dict(size=10)
            )
        )
    else:
        with fig.batch_update():
            fig.data[0].update(x=x_range, y=kde(x_range), line_color=colors['line'], 
                             fillcolor=colors['fill'])
            if len(fig.data) > 1:
                fig.data = [fig.data[0]]

    if selected_value is not None and selected_name is not None:
        fig.add_vline(x=selected_value, line_dash="dash", line_color='rgb(50, 50, 50)',
                     annotation_text=selected_name, annotation_position="top")
    
    return fig

def create_distance_histogram(area, variable, is_overall=False, fig=None):

    if fig is None:
        fig = go.Figure()
    
    fig.data = []

    distances = {}
    for i in range(0, 401, 100):
        key = f'{i}-{i+100}m' if i < 400 else '400m+'
        if is_overall:
            distances[key] = area['total_stats'].get(key, 0)
        else:
            distances[key] = area.get(key, 0)

    colours = ['rgb(0, 0, 85)', 'rgb(0, 0, 185)', 'rgb(0, 127, 255)', 
              'rgb(135, 206, 235)', 'rgb(232, 255, 252)']
    
    base_title = "Building Distance Distribution" if variable == "building_acc_percentage" else "Population Distance Distribution"
    
    fig.add_trace(go.Bar(
        x=list(distances.keys()),
        y=list(distances.values()),
        marker_color=colours,
        customdata=[variable, is_overall],
        hoverinfo='y'
    ))
    
    fig.update_layout(
        title=base_title,
        plot_bgcolor='white', paper_bgcolor='white',
        xaxis=dict(title="Distance from Bus Stop", showgrid=False, zeroline=False),
        yaxis=dict(
            title="Number of Buildings" if variable == "building_acc_percentage" else "Population",
            showgrid=True, gridwidth=1, gridcolor='rgb(230, 230, 230)', zeroline=False
        ),
        margin=dict(l=20, r=20, t=40, b=20),
        height=250, width=350, font=dict(size=10),
        showlegend=False, transition_duration=0, uirevision='static'
    )
    
    return fig