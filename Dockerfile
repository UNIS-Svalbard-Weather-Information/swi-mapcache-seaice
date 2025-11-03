FROM python:3.13.9-slim

RUN mkdir /swi

WORKDIR /swi

COPY requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY icechart_caching.py ./run.py
COPY mapnik_map_file.xml ./mapnik_map_file.xml

CMD ["python", "/swi/run.py"]
