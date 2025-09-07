# Sea Ice Map Caching Container

This container is designed to fetch the latest sea ice chart from the Norwegian Meteorological Institute (https://cryo.met.no/en/latest-ice-charts) and trigger a GeoWebCache cleanup using a truncate task.

### Environment Variables

To establish a connection with Deegree3, the following environment variables must be configured:

| Variable                         | Description                                                            |
| -------------------------------- | ---------------------------------------------------------------------- |
| `SWI-DEEGREE-URL`              | URL of the Deegree3 instance                                          |
| `SWI_DEEGREE_REST_API_KEY`         | Username for Deegree3 authentication                                  |
| `SWI-SEAICE-LAYER-FILE-NAME`     | Name of the output shapefile (default: `latest`)                       |
| `SWI-SEAICE-MONITORING-ENDPOINT` | URL of the endpoint to request to informe of the successful processing |

### Output

The generated shapefile will be saved in `/swi/export`. Ensure this directory is mapped to the corresponding storage location on Deegree3.
