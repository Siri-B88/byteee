import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Healthy City Environmental Dashboard",
    page_icon="🌍",
    layout="wide",
)

# --- BACKEND API URL ---
API_BASE_URL = "http://127.0.0.1:8000"

# --- CUSTOM CSS FOR ADVANCED STYLING ---
st.markdown("""
<style>
    /* Main container and block styling */
    .main .block-container {
        padding: 2rem;
        background-color: #F8F9FA; /* Light grey background */
    }
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E6EAF1;
    }
    /* Sidebar button styling */
    [data-testid="stSidebar"] .stButton>button {
        background-color: transparent;
        color: #31333F; /* Darker text */
        border: none;
        text-align: left;
        padding: 12px 10px;
        font-size: 16px;
        font-weight: 600;
        width: 100%;
        border-radius: 8px;
        transition: background-color 0.2s ease-in-out, color 0.2s ease-in-out;
    }
    [data-testid="stSidebar"] .stButton>button:hover {
        background-color: #E6F3FF; /* Light blue on hover */
        color: #007BFF; /* Blue text on hover */
    }
    /* Metric card styling */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E6EAF1;
        border-radius: 10px;
        padding: 1.5rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    /* Custom containers for a card-like look */
    .card {
        background-color: white;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #E6EAF1;
    }
    /* Main title */
    h1, h2, h3 {
        color: #0056b3; /* Darker blue for titles */
    }
</style>
""", unsafe_allow_html=True)


# --- API & UI HELPER FUNCTIONS ---
def get_api_data(endpoint):
    try:
        # Using a longer timeout as GEE can be slow
        response = requests.get(f"{API_BASE_URL}/{endpoint}", timeout=180)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error("Connection Timeout: The request to the backend took too long. Google Earth Engine might be busy. Please try again later.")
        return None
    except requests.exceptions.RequestException as e:
        error_detail = e.response.json().get("detail", str(e)) if e.response else str(e)
        st.error(f"API Error: {error_detail}")
        return None

def create_map(location, zoom=12):
    return folium.Map(location=[location['lat'], location['lon']], zoom_start=zoom, tiles="CartoDB positron")

def render_overview_card(city):
    data = get_api_data(f"city/{city}/overview")
    if not data: return
    
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"#### {data['city']}, {data.get('country', 'Global')}")
    st.markdown(f"<span style='background-color:#FFF0E6; color:#FF7A00; padding: 3px 8px; border-radius:12px;'>{data['risk_level']}</span>", unsafe_allow_html=True)
    cols = st.columns(2)
    cols[0].metric("🌡 Temp", data['temperature'])
    cols[0].metric("💧 Flood Risk", data['flood_risk'])
    cols[1].metric("🌳 Green Cover", data['green_cover'])
    cols[1].metric("💨 AQI", data['aqi'])
    if st.button("View Full Analysis", key=f"view_{data['city']}", use_container_width=True):
        st.session_state.city = data['city']
        st.session_state.page = 'Heat Map'
        st.rerun() # FIXED: Using the new, correct rerun function
    st.markdown('</div>', unsafe_allow_html=True)


# --- PAGE RENDERING FUNCTIONS ---

def render_city_search():
    st.title("🌍 Healthy City Search")
    st.markdown("Discover environmental insights for cities worldwide using real-time satellite data and advanced analytics.")
    
    search_query = st.text_input("", placeholder="Search for any city worldwide, e.g., Tokyo, New York, London...", label_visibility="collapsed", key="search_input")
    if st.button("Search"):
        if search_query:
            st.session_state.city = search_query
            st.session_state.page = 'Heat Map'
            st.rerun() # FIXED: Using the new, correct rerun function
        else:
            st.warning("Please enter a city name.")

    st.subheader("Key Cities")
    cols = st.columns(3)
    with cols[0]: render_overview_card("Tokyo")
    with cols[1]: render_overview_card("London")
    with cols[2]: render_overview_card("Mumbai")

def render_analysis_page(page_title, endpoint, render_metrics_func):
    st.header(page_title)
    city = st.session_state.get("city", "London") # Default city
    with st.spinner(f"Analyzing {page_title.split(' ')[1]} for {city}... This involves processing satellite data and may take a moment."):
        data = get_api_data(f"city/{city}/{endpoint}")

    if not data: return # Error is handled by get_api_data
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(f"### {data['city']} Analysis")
        render_metrics_func(data)
    with col2:
        m = create_map(data['location'])
        folium.Marker(
            location=[data['location']['lat'], data['location']['lon']],
            popup=f"{data['city']} Center", tooltip="City Center"
        ).add_to(m)
        st_folium(m, width=700, height=500)

# --- METRIC LOGIC FOR EACH PAGE ---

def metrics_heat_map(data):
    st.metric("🌡 Avg. Surface Temperature", data['avg_temp'])
    st.info(f"🛰 Data Source: {data['data_source']}")

def metrics_green_cover(data):
    st.metric("🌳 Average Green Cover", data['avg_coverage'])
    st.metric("Average NDVI", data['avg_ndvi'])
    st.info(f"🛰 Data Source: {data['data_source']}")
    
def metrics_flood_risk(data):
    st.metric("💧 Vulnerability Score", data['risk_score'])
    st.metric("High Risk Zones", data['high_risk_zones'])
    st.metric("Avg. Elevation", data['avg_elevation'])
    st.warning("Data on this page is simulated.")

def metrics_air_quality(data):
    st.metric("💨 Average AQI", data['avg_aqi'])
    st.metric("Unhealthy Sensors (>100)", data['unhealthy_sensors'])
    st.metric("Main Pollutant", data['main_pollutant'])
    st.warning("Data on this page is simulated.")

def render_report_card():
    st.header("📈 Comprehensive Report Card")
    city = st.session_state.get("city", "London")
    st.warning("Data on this page is simulated.")
    data = get_api_data(f"city/{city}/reportcard")
    if not data: return
    st.markdown(f"## {data['city']} | Overall Score: *{data['overall_score']}/100*")
    st.info(f"*Executive Summary:* {data['summary']}")
    cols = st.columns(2)
    cols[0].metric("Air Quality", data['grades']['Air Quality']['grade'])
    cols[1].metric("Green Cover", data['grades']['Green Cover']['grade'])

def render_simulator():
    st.header("🛠 Urban Planning Simulator")
    st.warning("Data on this page is simulated.")
    city = st.session_state.get("city", "London")
    sim_data = get_api_data(f"city/{city}/simulate?intervention=Parks&scale=Medium")
    if not sim_data: return
    st.metric("Projected Temp. Change", sim_data['impact']['temperature']['change'])
    st.metric("Projected AQI Change", sim_data['impact']['aqi']['change'])


# --- MAIN APP LOGIC & NAVIGATION ---
if "page" not in st.session_state: st.session_state.page = "City Search"

with st.sidebar:
    st.markdown("### ENVIRONMENTAL MONITORING")
    pages = {"City Search": "City Search", "Heat Map": "Urban temperature", "Flood Risk": "Flood vulnerability", "Green Cover": "Vegetation coverage", "Air Quality": "Pollution monitoring", "Simulation": "Urban planning", "Report Card": "Comprehensive city"}
    for page, subtext in pages.items():
        if st.button(f"{page}\n_{subtext}", use_container_width=True, key=f"nav{page}"): 
            st.session_state.page = page
            st.rerun() # FIXED: Using the new, correct rerun function

# Page routing
page_map = {
    "City Search": render_city_search,
    "Heat Map": lambda: render_analysis_page("🔥 Urban Heat Map", "heatmap", metrics_heat_map),
    "Flood Risk": lambda: render_analysis_page("💧 Flood Risk Analysis", "floodrisk", metrics_flood_risk),
    "Green Cover": lambda: render_analysis_page("🌳 Green Cover Analysis", "greencover", metrics_green_cover),
    "Air Quality": lambda: render_analysis_page("💨 Air Quality Analysis", "airquality", metrics_air_quality),
    "Report Card": render_report_card,
    "Simulation": render_simulator,
}
page_map.get(st.session_state.page, render_city_search)()