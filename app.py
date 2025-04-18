import json
import pandas as pd
from flask import Flask, render_template, jsonify
import plotly.express as px
import plotly.graph_objects as go
import os

app = Flask(__name__)

# Define file paths
CLUB_FILE = 'Golf-CLUB.json'
CLUB_TYPES_FILE = 'Golf-CLUB_TYPES.json'
COURSE_FILE = 'Golf-COURSE.json'
SHOT_FILE = 'Golf-SHOT.json'

# Data storage (in a real multi-user app, this would be a database)
club_data = pd.DataFrame()
club_types_data = pd.DataFrame()
course_data = pd.DataFrame()
shot_data = pd.DataFrame()
merged_shot_data = pd.DataFrame() # Dataframe after merging shot and club info

def load_data():
    """Loads data from JSON files into pandas DataFrames."""
    global club_data, club_types_data, course_data, shot_data, merged_shot_data

    try:
        with open(CLUB_FILE, 'r') as f:
            club_data = pd.DataFrame(json.load(f)['data'])
            # Rename id to clubId to match shot_data for merging
            club_data = club_data.rename(columns={'id': 'clubId'})
        print(f"Loaded {len(club_data)} clubs from {CLUB_FILE}")

        with open(CLUB_TYPES_FILE, 'r') as f:
            club_types_data = pd.DataFrame(json.load(f)['data'])
            # Rename value to clubTypeId to match club_data for merging
            club_types_data = club_types_data.rename(columns={'value': 'clubTypeId'})
        print(f"Loaded {len(club_types_data)} club types from {CLUB_TYPES_FILE}")

        with open(COURSE_FILE, 'r') as f:
            # The course data format is a bit unusual, list of dicts with one key-value pair
            course_list = []
            for entry in json.load(f)['data']:
                 for id, name in entry.items():
                      course_list.append({'courseId': int(id), 'courseName': name})
            course_data = pd.DataFrame(course_list)
        print(f"Loaded {len(course_data)} courses from {COURSE_FILE}")


        with open(SHOT_FILE, 'r') as f:
            shot_data = pd.DataFrame(json.load(f)['data'])
            # Convert meters to yards for easier understanding (optional)
            shot_data['yards'] = shot_data['meters'] * 1.09361
        print(f"Loaded {len(shot_data)} shots from {SHOT_FILE}")

        # Merge shot data with club data and club types data
        # Assuming clubId in shot_data links to id in club_data
        # Assuming clubTypeId in club_data links to value in club_types_data
        merged_shot_data = shot_data.merge(
            club_data[['clubId', 'clubTypeId', 'shaftLength', 'flexTypeId']],
            on='clubId',
            how='left'
        )
        merged_shot_data = merged_shot_data.merge(
            club_types_data[['clubTypeId', 'name', 'loftAngle']],
            on='clubTypeId',
            how='left'
        )
        # Fill NaN club names with 'Unknown Club' if clubId was 0 or not found
        merged_shot_data['name'] = merged_shot_data['name'].fillna('Unknown Club')
        print("Merged shot data with club and club type information.")

    except FileNotFoundError as e:
        print(f"Error loading data file: {e}")
        # In a real app, handle this gracefully, maybe return an error page
    except json.JSONDecodeError as e:
         print(f"Error decoding JSON: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during data loading: {e}")


# Load data when the application starts
load_data()

@app.route('/')
def index():
    """Homepage listing available charts."""
    charts = [
        {'url': '/chart/shot_distance_distribution_overall', 'title': 'Overall Shot Distance Distribution'},
        {'url': '/chart/shot_distance_by_lie', 'title': 'Shot Distance by Lie Type'},
        {'url': '/chart/shots_per_hole', 'title': 'Number of Shots Per Hole'},
        # Add more charts here as you create functions for them
        # {'url': '/chart/distance_by_club_type', 'title': 'Average Distance by Club Type'}, # Uncomment and implement when clubIds are meaningful
    ]
    return render_template('index.html', charts=charts)

@app.route('/chart/<chart_name>')
def show_chart(chart_name):
    """Renders a specific chart."""
    plot_json = {}
    chart_title = "Unknown Chart"

    if chart_name == 'shot_distance_distribution_overall':
        chart_title = 'Overall Shot Distance Distribution'
        if not merged_shot_data.empty:
             # Exclude putting shots (usually very short distances)
             non_putting_shots = merged_shot_data[merged_shot_data['lie'].isin(['TeeBox', 'Fairway', 'Rough', 'Bunker'])]
             fig = px.histogram(non_putting_shots, x='yards', nbins=50, title=chart_title)
             fig.update_layout(xaxis_title="Distance (yards)", yaxis_title="Number of Shots")
             plot_json = fig.to_json()

    elif chart_name == 'shot_distance_by_lie':
        chart_title = 'Shot Distance by Lie Type'
        if not merged_shot_data.empty:
            # Exclude putting shots from this analysis as they skew the scale
            non_putting_lies = merged_shot_data[merged_shot_data['lie'].isin(['TeeBox', 'Fairway', 'Rough', 'Bunker'])]
            fig = px.box(non_putting_lies, x='lie', y='yards', title=chart_title)
            fig.update_layout(xaxis_title="Lie Type", yaxis_title="Distance (yards)")
            plot_json = fig.to_json()

    elif chart_name == 'shots_per_hole':
        chart_title = 'Number of Shots Per Hole'
        if not merged_shot_data.empty:
            shots_count = merged_shot_data['holeNumber'].value_counts().sort_index().reset_index()
            shots_count.columns = ['Hole', 'Shot Count']
            fig = px.bar(shots_count, x='Hole', y='Shot Count', title=chart_title)
            fig.update_layout(xaxis_title="Hole Number", yaxis_title="Number of Shots")
            plot_json = fig.to_json()

    # Example for average distance by club type (will likely show mostly 'Unknown Club' due to data)
    # Uncomment and refine when your shot data has valid clubIds
    # elif chart_name == 'distance_by_club_type':
    #     chart_title = 'Average Distance by Club Type'
    #     if not merged_shot_data.empty:
    #         # Filter out putting and very short shots that might be chips/pitches not representative of full swings
    #         # You might need to adjust the distance threshold
    #         full_swings = merged_shot_data[(merged_shot_data['lie'].isin(['TeeBox', 'Fairway', 'Rough'])) & (merged_shot_data['yards'] > 30)]
    #         avg_distance = full_swings.groupby('name')['yards'].mean().reset_index()
    #         fig = px.bar(avg_distance, x='name', y='yards', title=chart_title)
    #         fig.update_layout(xaxis_title="Club Type", yaxis_title="Average Distance (yards)")
    #         plot_json = fig.to_json()

    if plot_json:
        return render_template('chart.html', plot_json=plot_json, chart_title=chart_title)
    else:
        return "Chart not found or data not available.", 404

if __name__ == '__main__':
    # To run the app, use 'flask run' in your terminal in the directory
    # containing app.py, or uncomment the line below for simple execution.
    # app.run(debug=True) # Set debug=False in production
    pass