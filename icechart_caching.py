import os
import requests
import shutil
import zipfile
import geopandas as gpd
from shapely.geometry import box
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from loguru import logger
import json
from requests.auth import HTTPBasicAuth
import numpy as np

os.environ['SHAPE_RESTORE_SHX'] = 'YES'

S250_ZIP_URL = "https://next.api.npolar.no/dataset/a23acc28-288b-49ba-ac6d-025d1fdee246/attachment/663eeae6-67ae-4c7f-a4ff-3d1fc8930efb/_blob"
ICECHART_URL = "https://cryo.met.no/sites/cryo/files/latest/NIS_arctic_latest_pl_a.zip"
PATH_LANDCONTOUR_DATA = './data/landcontour/'
PATH_ICECHART_DATA = './data/icechart/'
ZIP_FILE_PATH = os.path.join(PATH_LANDCONTOUR_DATA, 'S250_Land_f.zip')
EXPORT_PATH = "./export"

def get_land_contour():
    os.makedirs(PATH_LANDCONTOUR_DATA, exist_ok=True)
    target_shapefile = os.path.join(PATH_LANDCONTOUR_DATA, 'S250_SHP/S250_Land_f.shp')
    if not os.path.isfile(target_shapefile):
        logger.info("Downloading land contour data...")
        try:
            response = requests.get(S250_ZIP_URL, stream=True)
            response.raise_for_status()
            with open(ZIP_FILE_PATH, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)
            logger.info("Download completed. Extracting files...")
            with zipfile.ZipFile(ZIP_FILE_PATH, "r") as zip_ref:
                zip_ref.extractall(PATH_LANDCONTOUR_DATA)
            os.remove(ZIP_FILE_PATH)
            logger.info("Extraction completed and ZIP file removed.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise
    return target_shapefile

def get_latest_icechart():
    os.makedirs(PATH_ICECHART_DATA, exist_ok=True)
    zip_file_path = os.path.join(PATH_ICECHART_DATA, "NIS_arctic_latest.zip")
    logger.info(f"Downloading data from {ICECHART_URL}...")
    try:
        response = requests.get(ICECHART_URL, stream=True)
        response.raise_for_status()
        with open(zip_file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024):
                file.write(chunk)
        logger.info("Download complete. Extracting files...")
        with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
            zip_ref.extractall(PATH_ICECHART_DATA)
        os.remove(zip_file_path)
        logger.info("Extraction completed and ZIP file removed.")
        shapefiles = [f for f in os.listdir(PATH_ICECHART_DATA) if f.endswith(".shp")]
        if not shapefiles:
            raise FileNotFoundError("No shapefile found in the downloaded ZIP.")
        shapefile_path = os.path.join(PATH_ICECHART_DATA, shapefiles[0])
        return shapefile_path
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

def clip_land_area(icechart_shape_path, landcontour_shape_path, bbox_to_clip=(7.5, 74.0, 36.0, 81.0)):
    logger.info("Starting clipping process...")
    try:
        logger.info("Loading ice chart shapefile...")
        icechart_gdf = gpd.read_file(icechart_shape_path)
        logger.info("Loading land contour shapefile...")
        landcontour_gdf = gpd.read_file(landcontour_shape_path)
        if icechart_gdf.crs != landcontour_gdf.crs:
            landcontour_gdf = landcontour_gdf.to_crs(icechart_gdf.crs)
        logger.info("Removing open water and ice free")
        icechart_gdf = icechart_gdf[~icechart_gdf['NIS_CLASS'].isin(['Open Water', 'Ice Free'])]
        logger.info("Creating bounding box polygon...")
        bbox_polygon = box(*bbox_to_clip)
        bbox_gdf = gpd.GeoDataFrame(geometry=[bbox_polygon], crs=icechart_gdf.crs)
        logger.info("Clipping ice chart to bounding box...")
        icechart_gdf = gpd.clip(icechart_gdf, bbox_gdf)
        logger.info("Clipping ice chart to land contour...")
        icechart_gdf = gpd.overlay(icechart_gdf, landcontour_gdf, how='difference')
        logger.success("Clipping completed successfully!")
        logger.info("Updating publication date")
        xml_file_path = icechart_shape_path.replace('.shp', '.xml')
        try:
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            pubdate = root.find(".//pubdate").text
            date_obj = datetime.strptime(pubdate, "%Y%m%d")
            icechart_gdf["pubtime"] = date_obj.strftime("%d.%m.%Y")
            logger.success("Publication time updated")
        except Exception as e:
            date_obj = np.nan
            logger.warning(f"Could not update publication date: {e}")
        return icechart_gdf, date_obj
    except Exception as e:
        logger.error(f"An error occurred during clipping: {e}")
        raise


def trigger_truncate_gwc(workspace="swi", layer="latest_sea_ice_chart"):
    """
    Truncate the GeoWebCache for a specified GeoServer layer.

    Args:
        workspace (str): GeoServer workspace name.
        layer (str): GeoServer layer name.
    """
    geoserver_url = os.getenv("SWI-GEOSERVER-URL", "http://localhost:8080/geoserver")
    username = os.getenv("SWI-GEOSERVER-USERNAME", "admin")
    password = os.getenv("SWI-GEOSERVER-PWD", "geoserver")

    url = f"{geoserver_url}/gwc/rest/seed/{workspace}:{layer}.json"
    logger.debug(f"Constructed URL for GWC truncate: {url}")

    payload = {
        "seedRequest": {
            "name": f"{workspace}:{layer}",
            "type": "truncate",
            "gridSetId": "EPSG:4326",
            "zoomStart": 0,
            "zoomStop": 20,
            "threadCount": 1
        }
    }
    logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")

    logger.info(f"Attempting to truncate GWC for layer: {workspace}:{layer}")
    headers = {"Content-type": "application/json"}
    auth = HTTPBasicAuth(username, password)

    try:
        logger.debug(f"Sending POST request to {url} with auth for user: {username}")
        response = requests.post(
            url,
            data=json.dumps(payload),
            headers=headers,
            auth=auth
        )

        logger.info(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {response.headers}")
        logger.debug(f"Response text: {response.text}")

        if response.status_code == 200:
            logger.info("GWC truncate request successful.")
            return response.status_code
        else:
            logger.error(
                f"GWC truncate request failed. "
                f"Status: {response.status_code}, "
                f"Reason: {response.reason}, "
                f"Response: {response.text}"
            )
            return response.status_code
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed with exception: {e}", exc_info=True)
        raise
    
def trigger_reload():
    """
    Sends a GET request to the SWI-DEEGREE-URL/config/update endpoint using the SWI_DEEGREE_REST_API_KEY
    as a token parameter. The URL and API key are read from environment variables.

    Returns:
        int: The HTTP status code of the response, or -1 if an error occurs.
    """
    swi_degree_url = os.getenv("SWI-DEEGREE-URL")
    swi_degree_rest_api_key = os.getenv("SWI_DEEGREE_REST_API_KEY")


    if not swi_degree_url or not swi_degree_rest_api_key:
        logger.error("Environment variables SWI-DEEGREE-URL and SWI_DEEGREE_REST_API_KEY must be set.")
        return -1

    url = f"{swi_degree_url}/deegree-webservices/config/update"
    params = {
        "token": swi_degree_rest_api_key
    }

    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            logger.success("Successfully triggered the update of Deegree3")
        else:
            logger.warning(f"Error, reponse code {response.status_code}")
        return response.status_code
    except Exception as e:
        logger.error(f"An error occurred while making the request: {e}")
        return -1


def update_theme_wms_xml(xml_file_path, pubdate, fetched_date):
    """
    Updates the pubdate and fetched date in the abstract of the seaice theme in the theme-wms.xml file.

    Args:
        xml_file_path (str): Path to the theme-wms.xml file.
        pubdate (str): The publication date to insert (e.g., "2025-09-07").
        fetched_date (str): The fetched date to insert (e.g., "2025-09-07").
        logger (logging.Logger): Logger instance for logging messages.
    """
    # Register the namespaces to handle them in XPath-like searches
    namespaces = {
        'ns': 'http://www.deegree.org/themes/standard',
        'd': 'http://www.deegree.org/metadata/description',
        's': 'http://www.deegree.org/metadata/spatial'
    }

    try:
        # Parse the XML file
        tree = ET.parse(xml_file_path)
        root = tree.getroot()

        pubdate_str = pubdate.strftime("%Y-%m-%d")
        fetched_date_str = fetched_date.strftime("%Y-%m-%d %H:%M:%S")

        # Find the abstract element for the seaice theme
        for theme in root.findall('.//ns:Theme[ns:Identifier="icechart"]', namespaces):
            abstract = theme.find('d:Abstract', namespaces)
            if abstract is not None:
                # Update the abstract text with the new dates
                abstract.text = f"Latest Ice Chart from cryo.met.no published on {pubdate_str} and fetched on {fetched_date_str}"
                tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
                logger.success(f"Successfully updated {xml_file_path} with pubdate={pubdate_str} and fetched_date={fetched_date_str}")
            else:
                logger.warning(f"Abstract element not found for seaice theme in {xml_file_path}")
    except ET.ParseError as e:
        logger.error(f"Failed to parse {xml_file_path}: {e}")
        return -1
    except IOError as e:
        logger.error(f"Failed to write to {xml_file_path}: {e}")
        return -1
    except Exception as e:
        logger.error(f"An unexpected error occurred while updating {xml_file_path}: {e}")
        return -1
    return 200

def main():
    try:
        # os.makedirs(EXPORT_PATH, exist_ok=True)
        icechart_gdf, pubdate = clip_land_area(get_latest_icechart(), get_land_contour())
        output_path = os.path.join(EXPORT_PATH, f"{os.getenv('SWI-SEAICE-LAYER-FILE-NAME','latest')}.shp")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        icechart_gdf.to_file(output_path, driver='ESRI Shapefile')
        logger.success(f"Clipped ice chart saved to {output_path}")

        # status_code = trigger_truncate_gwc()

        xml_file_path = os.path.join(EXPORT_PATH,os.getenv('SWI-SEAICE-UPDATE-THEME-DEEGREE','themes/theme_wms.xml'))
        status_code_1 = update_theme_wms_xml(xml_file_path, pubdate, datetime.now())

        status_code_2 = trigger_reload()

        if status_code_1 == 200 and status_code_2==200:
            # Determine if pubdate is today (weekday) or latest Friday (weekend)
            today = datetime.now().date()
            if today.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                latest_friday = today - timedelta(days=today.weekday() - 4)  # 4 = Friday
                target_date = latest_friday
            else:
                target_date = today

            if pubdate.date() == target_date:
                endpoint = os.getenv('SWI-SEAICE-MONITORING-ENDPOINT')
                if endpoint:
                    response = requests.get(endpoint)
                    logger.info(f"GET request to {endpoint} returned status code: {response.status_code}")
                else:
                    logger.warning("SWI-SEAICE-MONITORING-ENDPOINT environment variable not set")

        shutil.rmtree(PATH_ICECHART_DATA, ignore_errors=True)

    except Exception as e:
        logger.error(f"Failed to save clipped data: {e}")
        raise

if __name__ == "__main__":
    main()
