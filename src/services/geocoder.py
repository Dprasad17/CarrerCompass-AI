import logging
import requests
import streamlit as st
from typing import Dict, Any

logger = logging.getLogger("Geocoder")

SUPPORTED_ADZUNA_COUNTRIES = {"au", "at", "br", "ca", "ch", "de", "es", "fr", "gb", "in", "it", "mx", "nl", "nz", "pl", "ru", "sg", "us", "za"}

@st.cache_data(show_spinner=False)
def geocode_location(location_name: str) -> Dict[str, Any]:

    """
    Geocodes a location name using Nominatim OpenStreetMap API.
    Returns latitude, longitude, and detected country code for Adzuna compatibility.
    """
    if not location_name:
        return {
            "lat": 51.5074,
            "lon": -0.1278,
            "country_code": "gb",
            "display_name": "London, UK"
        }

    # Nominatim requires a user-agent to prevent 403 blocks
    headers = {
        "User-Agent": "CareerCompassAI/1.0 (contact: durga_prasad_a)"
    }
    
    # Clean location name
    query = location_name.strip()
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": 1
    }

    try:
        logger.info(f"Geocoding location: '{query}' via Nominatim...")
        response = requests.get(url, headers=headers, params=params, timeout=5)
        
        if response.status_code == 200 and response.json():
            data = response.json()[0]
            lat = float(data["lat"])
            lon = float(data["lon"])
            
            address = data.get("address", {})
            country_code = address.get("country_code", "gb").lower()
            
            # Map common variants to Adzuna codes
            if country_code == "uk":
                country_code = "gb"
                
            # If the detected country is not supported by Adzuna, fall back to "us" or "gb"
            if country_code not in SUPPORTED_ADZUNA_COUNTRIES:
                # Simple check: if search query mentions India, ensure we use 'in'
                if "india" in query.lower() or "bangalore" in query.lower() or "bengaluru" in query.lower():
                    country_code = "in"
                else:
                    country_code = "us"
            
            display_name = data.get("display_name", query)
            
            logger.info(f"Geocoding success: '{query}' mapped to lat={lat}, lon={lon}, country_code={country_code}")
            return {
                "lat": lat,
                "lon": lon,
                "country_code": country_code,
                "display_name": display_name
            }
            
    except Exception as e:
        logger.error(f"Geocoding API failed for location '{query}': {e}")

    # Manual backup rules if the geocoding request fails
    query_lower = query.lower()
    if "india" in query_lower or "bangalore" in query_lower or "bengaluru" in query_lower:
        return {"lat": 12.9716, "lon": 77.5946, "country_code": "in", "display_name": "Bengaluru, Karnataka, India"}
    if "delhi" in query_lower:
        return {"lat": 28.6139, "lon": 77.2090, "country_code": "in", "display_name": "Delhi, India"}
    if "mumbai" in query_lower:
        return {"lat": 19.0760, "lon": 72.8777, "country_code": "in", "display_name": "Mumbai, Maharashtra, India"}
    if "hyderabad" in query_lower:
        return {"lat": 17.3850, "lon": 78.4867, "country_code": "in", "display_name": "Hyderabad, Telangana, India"}
    if "pune" in query_lower:
        return {"lat": 18.5204, "lon": 73.8567, "country_code": "in", "display_name": "Pune, Maharashtra, India"}
    if "chennai" in query_lower:
        return {"lat": 13.0827, "lon": 80.2707, "country_code": "in", "display_name": "Chennai, Tamil Nadu, India"}
    if "new york" in query_lower:
        return {"lat": 40.7128, "lon": -74.0060, "country_code": "us", "display_name": "New York, USA"}
    if "london" in query_lower:
        return {"lat": 51.5074, "lon": -0.1278, "country_code": "gb", "display_name": "London, UK"}

    return {
        "lat": 51.5074,
        "lon": -0.1278,
        "country_code": "gb",
        "display_name": "London, UK"
    }
