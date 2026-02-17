# Sea Ice Map Caching Container

This container is designed to fetch the latest sea ice chart from the Norwegian Meteorological Institute ([cryo.met.no](https://cryo.met.no/en/latest-ice-charts)).

---

## Environment Variables

To establish a connection with Deegree3 and control container behavior, the following environment variables can be configured:

| Variable                            | Description                                                                                     |
|-------------------------------------|-------------------------------------------------------------------------------------------------|
| `SWI-SEAICE-LAYER-FILE-NAME`        | Name of the output shapefile (default: `latest`)                                                |
| `SWI-SEAICE-LAYER-LEGEND-FILE-NAME` | Name of the output legend file (default: `/metadata/met_icechart/legend.html`)                  |
| `SWI-SEAICE-MONITORING-ENDPOINT`    | URL of the endpoint to notify upon successful processing                                        |
| `DOCKER-CRON`                       | If set, the container will run the script once and then wait for manual commands (e.g., `run-cron`) |

---

## Output

The generated shapefile will be saved in `/swi/export`. Ensure this directory is mapped to the corresponding storage location on MapProxy.

---

## Usage

### Default Mode
Run the container once and exit after processing:
```bash
docker run -it --rm \
  -v ./tests/metadata:/swi/metadata \
  -v ./tests/data/latest_seaice:/swi/export/latest_seaice \
  swi-test-seaice
```

### Interactive Mode (with `DOCKER-CRON`)
Run the container, process the data once, and keep it open for manual re-runs using the `run-cron` alias:
```bash
docker run -it --rm \
  -e DOCKER-CRON=1 \
  -v ./tests/metadata:/swi/metadata \
  -v ./tests/data/latest_seaice:/swi/export/latest_seaice \
  swi-test-seaice
```
- After the initial run, you can manually trigger the script again by typing `run-cron` in the container's shell.
