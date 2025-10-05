import os
import random
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import ee

# --- INITIALIZATION ---
load_dotenv()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")

app = FastAPI(title="HealthyCity Real-Time API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=[""], allow_headers=[""],
)

try:
    if not GOOGLE_CLOUD_PROJECT:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set.")
    ee.Initialize(project=GOOGLE_CLOUD_PROJECT)
    print("✅ Google Earth Engine Initialized Successfully.")
except Exception as e:
    print(f"❌ ERROR: Google Earth Engine failed to initialize. Details: {e}")

# --- HELPER FUNCTIONS ---

def get_city_coords(city_name: str):
    """
    Gets city coordinates. This version uses a reliable, hardcoded list for common
    cities and falls back to the global API for others.
    """
    known_cities = {
        "shimoga": (13.9299, 75.5681),
        "challakere": (14.3135, 76.6534),
        "mumbai": (19.0760, 72.8777),
        "tokyo": (35.6762, 139.6503),
        "london": (51.5072, -0.1276),
        "new york": (40.7128, -74.0060),
    }
    
    city_lower = city_name.lower()
    if city_lower in known_cities:
        return known_cities[city_lower]

    # Fallback to the live API for any other city
    if not OPENWEATHER_API_KEY:
        raise HTTPException(status_code=500, detail="OpenWeatherMap API key is not configured.")
    try:
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={city_name}&limit=1&appid={OPENWEATHER_API_KEY}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            raise HTTPException(status_code=404, detail=f"City '{city_name}' not found.")
        return data[0]["lat"], data[0]["lon"]
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=503, detail="Geocoding service is unavailable.")


# --- REAL SATELLITE DATA ENDPOINTS ---

@app.get("/city/{city}/greencover")
def get_green_cover_real(city: str):
    """Calculates REAL green cover (NDVI) using Google Earth Engine."""
    try:
        lat, lon = get_city_coords(city)
        point = ee.Geometry.Point(lon, lat)
        area_of_interest = point.buffer(5000) # 5km radius

        image = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                   .filterBounds(area_of_interest)
                   .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                   .filter(ee.Filter.date('2023-01-01', '2023-12-31'))
                   .median())

        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

        stats = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=area_of_interest,
            scale=30, maxPixels=1e9
        ).getInfo()

        avg_ndvi = stats.get('NDVI')
        if avg_ndvi is None:
             raise HTTPException(status_code=404, detail="Could not calculate NDVI for this area.")

        green_cover_percentage = (avg_ndvi + 1) * 50

        return {
            "city": city.title(), "location": {"lat": lat, "lon": lon},
            "avg_coverage": f"{green_cover_percentage:.2f}%",
            "avg_ndvi": f"{avg_ndvi:.4f}",
            "data_source": "Sentinel-2 Satellite"
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An Earth Engine error occurred: {str(e)}")


@app.get("/city/{city}/heatmap")
def get_heat_map_real(city: str):
    """Calculates REAL urban heat (LST) using Google Earth Engine."""
    try:
        lat, lon = get_city_coords(city)
        point = ee.Geometry.Point(lon, lat)
        area_of_interest = point.buffer(5000)

        def scale_thermal(image):
            thermal = image.select('ST_B10').multiply(0.00341802).add(149.0)
            return thermal.subtract(273.15)

        latest_image = (ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
                          .filterBounds(area_of_interest)
                          .filter(ee.Filter.lt('CLOUD_COVER', 20))
                          .filter(ee.Filter.date('2023-01-01', '2023-12-31'))
                          .sort('system:time_start', False)
                          .first())
        
        if latest_image is None:
            raise HTTPException(status_code=404, detail="No valid satellite imagery found for the date range.")

        lst_celsius = scale_thermal(latest_image).rename('LST_Celsius')

        stats = lst_celsius.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=area_of_interest,
            scale=30, maxPixels=1e9
        ).getInfo()
        
        avg_temp = stats.get('LST_Celsius')
        if avg_temp is None:
            raise HTTPException(status_code=404, detail="Could not calculate temperature.")

        return {
            "city": city.title(), "location": {"lat": lat, "lon": lon},
            "avg_temp": f"{avg_temp:.2f}°C",
            "data_source": "Landsat 9 Satellite"
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An Earth Engine error occurred: {str(e)}")


# --- SIMULATED ENDPOINTS (For other pages) ---

@app.get("/city/{city}/overview")
def get_city_overview(city: str):
    get_city_coords(city) # Validate city exists
    return {"city": city.title(), "country": "Global", "temperature": f"{random.uniform(25.0, 32.0):.1f}°C", "green_cover": f"{random.randint(40, 65)}%", "flood_risk": f"{random.randint(5, 25)}/100", "aqi": random.randint(40, 90), "risk_level": random.choice(["Low Risk", "Medium Risk"])}

@app.get("/city/{city}/floodrisk")
def get_flood_risk(city: str):
    lat, lon = get_city_coords(city)
    return { "city": city.title(), "location": {"lat": lat, "lon": lon}, "risk_score": f"{random.randint(10, 40)}/100", "high_risk_zones": random.randint(1, 10), "avg_elevation": f"{random.randint(40, 60)}m" }

@app.get("/city/{city}/airquality")
def get_air_quality(city: str):
    lat, lon = get_city_coords(city)
    return {"city": city.title(), "location": {"lat": lat, "lon": lon}, "avg_aqi": random.randint(30, 150), "unhealthy_sensors": random.randint(0, 5), "main_pollutant": random.choice(["PM2.5", "O3", "NO2"])}

@app.get("/city/{city}/reportcard")
def get_report_card(city: str):
    lat, lon = get_city_coords(city)
    return {"city": city.title(), "location": {"lat": lat, "lon": lon}, "overall_score": random.randint(60, 85), "summary": "This is a simulated summary.", "grades": {"Air Quality": {"grade": "C+"}, "Green Cover": {"grade": "A-"}}}

@app.get("/city/{city}/simulate")
def get_simulation(city: str, intervention: str, scale: str):
    return {"impact": {"temperature": {"current": "25.1°C", "change": "-2.5°C"}, "aqi": {"current": 83, "change": -20}}, "benefits": {"co2_absorbed": "150 Tons/year", "investment": "$500K"}}