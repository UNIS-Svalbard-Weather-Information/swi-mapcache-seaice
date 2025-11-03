# Sea Ice Map Caching Container

This container is designed to fetch the latest sea ice chart from the Norwegian Meteorological Institute (https://cryo.met.no/en/latest-ice-charts)

### Environment Variables

    To establish a connection with Deegree3, the following environment variables must be configured:

| Variable                            | Description                                                                    |
| ----------------------------------- | ------------------------------------------------------------------------------ |
| `SWI-SEAICE-LAYER-FILE-NAME`        | Name of the output shapefile (default: `latest`)                               |
| `SWI-SEAICE-LAYER-LEGEND-FILE-NAME` | Name of the output legend file (default: `/metadata/met_icechart/legend.html`) |
| `SWI-SEAICE-MONITORING-ENDPOINT`    | URL of the endpoint to request to informe of the successful processing         |

### Output

The generated shapefile will be saved in `/swi/export`. Ensure this directory is mapped to the corresponding storage location on MapProxy.

Example Command :

```bash
docker run -it --rm -v ./tests/metadata:/swi/metadata -v ./tests/data/latest_seaice:/swi/export swi-test-seaice
```
