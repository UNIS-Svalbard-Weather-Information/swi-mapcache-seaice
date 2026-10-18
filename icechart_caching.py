import json
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime, timedelta

import geopandas as gpd
import numpy as np
import requests
from loguru import logger
from shapely.geometry import box

os.environ["SHAPE_RESTORE_SHX"] = "YES"

S250_ZIP_URL = "https://next.api.npolar.no/dataset/a23acc28-288b-49ba-ac6d-025d1fdee246/attachment/663eeae6-67ae-4c7f-a4ff-3d1fc8930efb/_blob"
ICECHART_URL = "https://cryo.met.no/sites/cryo/files/latest/NIS_arctic_latest_pl_a.zip"
PATH_LANDCONTOUR_DATA = "./data/landcontour/"
PATH_ICECHART_DATA = "./data/icechart/"
ZIP_FILE_PATH = os.path.join(PATH_LANDCONTOUR_DATA, "S250_Land_f.zip")
EXPORT_PATH = "./export/latest_seaice"
MAPPROXY_RELOAD = "./export/reload.trigger"

ICE_CLASSES = [
    {
        "id": "fast-ice",
        "label": "Fast Ice (10/10ths)",
        "fill": "#696969",
        "border": "#3d3d3d",
    },
    {
        "id": "very-close-drift-ice",
        "label": "Very Close Drift Ice (9-10/10ths)",
        "fill": "#cc0000",
        "border": "#800000",
    },
    {
        "id": "close-drift-ice",
        "label": "Close Drift Ice (7-9/10ths)",
        "fill": "#ff8c00",
        "border": "#cc5500",
    },
    {
        "id": "open-drift-ice",
        "label": "Open Drift Ice (4-7/10ths)",
        "fill": "#ffd700",
        "border": "#cc9900",
    },
    {
        "id": "very-open-drift-ice",
        "label": "Very Open Drift Ice (1-4/10ths)",
        "fill": "#98fb98",
        "border": "#4cae4c",
    },
]
ICE_CHART_LINK = {
    "label": "View on Met Norway Ice Service",
    "url": "https://cryo.met.no/en/latest-ice-charts",
}
LEGEND_SWATCH_HTML = """  <div style="display: flex; align-items: flex-start; gap: 0.75rem">
    <div
      style="
        width: 1.25rem;
        height: 1.25rem;
        flex-shrink: 0;
        background-color: {fill};
        border: 1px solid {border};
        border-radius: 2px;
      "
    ></div>
    <span style="font-size: 0.875rem">{label}</span>
  </div>
"""


def _safe_extractall(zip_ref, target_dir):
    """Extract all members, rejecting any path that would escape target_dir (zip-slip guard)."""
    dest = os.path.realpath(target_dir)
    for member in zip_ref.namelist():
        resolved = os.path.realpath(os.path.join(dest, member))
        if resolved != dest and not resolved.startswith(dest + os.sep):
            raise ValueError(f"Blocked unsafe path in archive (zip slip): {member}")
    zip_ref.extractall(target_dir)


def get_land_contour():
    os.makedirs(PATH_LANDCONTOUR_DATA, exist_ok=True)
    target_shapefile = os.path.join(PATH_LANDCONTOUR_DATA, "S250_SHP/S250_Land_f.shp")
    if not os.path.isfile(target_shapefile):
        logger.info("Downloading land contour data...")
        try:
            response = requests.get(S250_ZIP_URL, stream=True)
            response.raise_for_status()
            with open(ZIP_FILE_PATH, "wb") as file:
                file.writelines(response.iter_content(chunk_size=1024))
            logger.info("Download completed. Extracting files...")
            with zipfile.ZipFile(ZIP_FILE_PATH, "r") as zip_ref:
                _safe_extractall(zip_ref, PATH_LANDCONTOUR_DATA)
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
            file.writelines(response.iter_content(chunk_size=1024))
        logger.info("Download complete. Extracting files...")
        with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
            _safe_extractall(zip_ref, PATH_ICECHART_DATA)
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


def clip_land_area(
    icechart_shape_path, landcontour_shape_path, bbox_to_clip=(7.5, 74.0, 36.0, 81.0)
):
    logger.info("Starting clipping process...")
    try:
        logger.info("Loading ice chart shapefile...")
        icechart_gdf = gpd.read_file(icechart_shape_path)
        logger.info("Loading land contour shapefile...")
        landcontour_gdf = gpd.read_file(landcontour_shape_path)
        if icechart_gdf.crs != landcontour_gdf.crs:
            landcontour_gdf = landcontour_gdf.to_crs(icechart_gdf.crs)
        logger.info("Removing open water and ice free")
        icechart_gdf = icechart_gdf[
            ~icechart_gdf["NIS_CLASS"].isin(["Open Water", "Ice Free"])
        ]
        logger.info("Creating bounding box polygon...")
        bbox_polygon = box(*bbox_to_clip)
        bbox_gdf = gpd.GeoDataFrame(geometry=[bbox_polygon], crs=icechart_gdf.crs)
        logger.info("Clipping ice chart to bounding box...")
        icechart_gdf = gpd.clip(icechart_gdf, bbox_gdf)
        logger.info("Clipping ice chart to land contour...")
        icechart_gdf = gpd.overlay(icechart_gdf, landcontour_gdf, how="difference")
        logger.success("Clipping completed successfully!")
        logger.info("Updating publication date")
        xml_file_path = icechart_shape_path.replace(".shp", ".xml")
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
        logger.error(
            "Environment variables SWI-DEEGREE-URL and SWI_DEEGREE_REST_API_KEY must be set."
        )
        return -1

    url = f"{swi_degree_url}/deegree-webservices/config/update"
    params = {"token": swi_degree_rest_api_key}

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
        "ns": "http://www.deegree.org/themes/standard",
        "d": "http://www.deegree.org/metadata/description",
        "s": "http://www.deegree.org/metadata/spatial",
    }

    try:
        # Parse the XML file
        tree = ET.parse(xml_file_path)
        root = tree.getroot()

        pubdate_str = pubdate.strftime("%Y-%m-%d")
        fetched_date_str = fetched_date.strftime("%Y-%m-%d %H:%M:%S")

        # Find the abstract element for the seaice theme
        for theme in root.findall('.//ns:Theme[ns:Identifier="icechart"]', namespaces):
            abstract = theme.find("d:Abstract", namespaces)
            if abstract is not None:
                # Update the abstract text with the new dates
                abstract.text = f"Latest Ice Chart from cryo.met.no published on {pubdate_str} and fetched on {fetched_date_str}"
                tree.write(xml_file_path, encoding="utf-8", xml_declaration=True)
                logger.success(
                    f"Successfully updated {xml_file_path} with pubdate={pubdate_str} and fetched_date={fetched_date_str}"
                )
            else:
                logger.warning(
                    f"Abstract element not found for seaice theme in {xml_file_path}"
                )
    except ET.ParseError as e:
        logger.error(f"Failed to parse {xml_file_path}: {e}")
        return -1
    except OSError as e:
        logger.error(f"Failed to write to {xml_file_path}: {e}")
        return -1
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while updating {xml_file_path}: {e}"
        )
        return -1
    return 200


def create_legend_html(export_path, fetched_date, pubdate):
    swatches = "".join(
        LEGEND_SWATCH_HTML.format(**ice_class) for ice_class in ICE_CLASSES
    )
    legend_html = f"""
<div
  style="
    background-color: #fef3c7;
    color: #92400e;
    padding: 1rem;
    border-radius: 0.375rem;
    margin-bottom: 1rem;
    font-size: 0.875rem;
    border-left: 4px solid #f59e0b;
  "
  id="updateWarning"
>
  <strong>Notice:</strong> This layer was updated on
  <strong><span id="updateTime"></span></strong>. Discrepancies may appear for
  <strong>15 minutes</strong> after the update while the cache updates.
</div>
<div
  style="
    font-size: 0.875rem;
    color: #6b7280;
    padding-top: 1rem;
    padding-bottom: 1rem;
  "
>
  This layer was updated on
  <strong><span id="updateTimeInfo"></span></strong> based on the ice chart
  published by the <strong>Norwegian Meteorological Institute</strong> ice
  service on <strong><span id="publishedTime"></span></strong>.
</div>
<script>
  // Set the update and published times (ISO format, parsed as UTC)
  const updateTime = new Date("{fetched_date.strftime("%Y-%m-%dT%H:%M:%S")}Z");
  const publishedTime = new Date("{pubdate.strftime("%Y-%m-%dT%H:%M:%S")}Z");
  const warningDuration = 15 * 60 * 1000; // 15 minutes in milliseconds
  const endTime = new Date(updateTime.getTime() + warningDuration);

  // Format time for display using the user's local time zone
  function formatTime(date) {{
    return date.toLocaleString('en-US', {{
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false // Use 24-hour format
    }});
  }}

  // Update the DOM with the formatted times
  document.getElementById("updateTime").textContent = formatTime(updateTime);
  document.getElementById("updateTimeInfo").textContent = formatTime(updateTime);
  document.getElementById("publishedTime").textContent = formatTime(publishedTime);

  // Check if the warning should be visible
  function checkWarningVisibility() {{
    const now = new Date();
    const warningElement = document.getElementById("updateWarning");
    if (now >= endTime) {{
      warningElement.style.display = "none";
    }}
  }}

  // Check visibility every minute and immediately on page load
  setInterval(checkWarningVisibility, 60000);
  checkWarningVisibility();
</script>
<div style="display: flex; flex-direction: column; gap: 0.75rem">
{swatches}  <div
    style="display: flex; align-items: center; gap: 0.5rem; margin-top: 1rem"
  >
    <a
      href="https://cryo.met.no/en/latest-ice-charts"
      target="_blank"
      rel="noopener noreferrer"
      style="font-size: 0.75rem; color: #3b82f6; text-decoration: none"
    >
      View on Met Norway Ice Service &rarr;
    </a>
  </div>
</div>
"""
    try:
        with open(export_path, "w", encoding="utf-8") as file:
            file.write(legend_html)
        logger.success(f"Legend HTML created at {export_path}")
    except Exception as e:
        logger.error(f"Failed to create legend HTML: {e}")
        raise


def create_legend_json(export_path, fetched_date, pubdate):
    """Write the legend as JSON (schema version 1) next to legend.html.

    fetched_date and pubdate are naive UTC datetimes, as for create_legend_html.
    """
    iso = "%Y-%m-%dT%H:%M:%SZ"
    legend = {
        "version": 1,
        "title": "Sea ice",
        "updated": fetched_date.strftime(iso),
        "published": pubdate.strftime(iso),
        "items": [
            {**ice_class, "opacity": 1, "description": None}
            for ice_class in ICE_CLASSES
        ],
        "links": [ICE_CHART_LINK],
    }
    directory = os.path.dirname(export_path) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        # Write to a temp file and rename, so MapProxy never serves a partial file.
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(legend, file, ensure_ascii=False, indent=2)
        os.chmod(tmp, 0o644)
        os.replace(tmp, export_path)
        logger.success(f"Legend JSON created at {export_path}")
    except Exception as e:
        logger.error(f"Failed to create legend JSON: {e}")
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main():
    try:
        # os.makedirs(EXPORT_PATH, exist_ok=True)
        icechart_gdf, pubdate = clip_land_area(
            get_latest_icechart(), get_land_contour()
        )
        output_path = os.path.join(
            EXPORT_PATH, f"{os.getenv('SWI-SEAICE-LAYER-FILE-NAME', 'latest')}.shp"
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        icechart_gdf.to_file(output_path, driver="ESRI Shapefile")
        shutil.copy("mapnik_map_file.xml", output_path.replace(".shp", ".xml"))
        logger.success(f"Clipped ice chart saved to {output_path}")

        legendpath = os.getenv(
            "SWI-SEAICE-LAYER-LEGEND-FILE-NAME", "./metadata/met_icechart/legend.html"
        )
        os.makedirs(os.path.dirname(legendpath), exist_ok=True)
        legend_pubdate = pubdate + timedelta(hours=15)
        create_legend_html(legendpath, datetime.now(), legend_pubdate)
        create_legend_json(
            os.path.splitext(legendpath)[0] + ".json",
            datetime.now(UTC).replace(tzinfo=None),
            legend_pubdate,
        )

        # xml_file_path = os.path.join(EXPORT_PATH,os.getenv('SWI-SEAICE-UPDATE-THEME-DEEGREE','themes/theme_wms.xml'))
        # status_code_1 = update_theme_wms_xml(xml_file_path, pubdate, datetime.now())

        # status_code_2 = trigger_reload()

        # if status_code_1 == 200 and status_code_2==200 and True:
        # Determine if pubdate is today (weekday) or latest Friday (weekend)
        today = datetime.now().date()
        if today.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            latest_friday = today - timedelta(days=today.weekday() - 4)  # 4 = Friday
            target_date = latest_friday
        else:
            target_date = today

        if pubdate.date() == target_date:
            endpoint = os.getenv("SWI_SEAICE_MONITORING_ENDPOINT")
            if endpoint:
                response = requests.get(endpoint)
                logger.info(
                    f"GET request to {endpoint} returned status code: {response.status_code}"
                )
            else:
                logger.warning(
                    "SWI-SEAICE-MONITORING-ENDPOINT environment variable not set"
                )

        with open(MAPPROXY_RELOAD, "ab"):
            os.utime(MAPPROXY_RELOAD, None)
            logger.info(f"Touching {MAPPROXY_RELOAD}")

        shutil.rmtree(PATH_ICECHART_DATA, ignore_errors=True)

    except Exception as e:
        logger.error(f"Failed to save clipped data: {e}")
        raise


if __name__ == "__main__":
    main()
