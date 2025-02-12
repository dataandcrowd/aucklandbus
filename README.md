## 🚌 Auckland Bus Accessibility Using Shiny
Welcome! 👋 This repository explores how Auckland's bus routes operate and quantifies spatial accessibility at popular sites, including the CBD and suburbs like Mount Eden. 🚍

As an undergraudate summer research project, we’ve developed an interactive Shiny app to visualise and understand the dynamics of accessibility across the city. Whether you're a transport planner, urban analyst, or just curious about Auckland's public transport system, this project offers valuable insights! 🌏

🧐 Why This Matters
Public transport accessibility is a critical factor in urban mobility. By analyzing bus routes and accessibility in Auckland, this project aims to:

* Highlight gaps in the public transport network.
* Provide insights for improved urban planning and policy-making.


## ✨ Key Features
* Dynamic Visualisation
* Explore accessibility changes in real time using the Shiny app.
* Dive into metrics that highlight disparities in accessibility.

## 🛠️ Technology Stack
* Python for data processing and analysis.
* Shiny in Python for interactive visualization.
* GIS tools for spatial analysis.

## 📂 Repository Structure
* ShinyApp/: Contains the Shiny app code.
* ShinyApp/data/: Preprocessed datasets used in the analysis.
* DataProcessing/: Python scripts for cleaning and processing raw data to be used by the Shiny app.
* DataProcessing/Data/: Raw data sourced from Auckland Transport and Stats NZ
* Both data folders can be found for download at: https://uoa-my.sharepoint.com/:f:/g/personal/hshi103_uoa_auckland_ac_nz/EkJpKkNH7xlFtMg4sWBgh-0BWUKdaXt0rRnYjrLKdokGUw?e=RIwn1C

## 🚀 How to Run
### Processing Custom Data
* Execute Python scripts in DataProcessing/ in sequence:
  * daily_busses.py
  * add_routes_to_busstops.py
  * process_routes.py
  * ShinyApp_data_processing.py (customise center coordinates and study radius)
* Copy generated GeoJSON files from DataProcessing/outputs/geojson to ShinyApp/data

### Running the App
To run the app locally:
```bash
pip install shiny
python -m shiny run ShinyApp/app.py
```
Instructions for hosting can be found at: https://shiny.posit.co/py/docs/deploy.html


## 🙌 Contributing
We welcome contributions! If you have ideas or suggestions, feel free to reach out!
