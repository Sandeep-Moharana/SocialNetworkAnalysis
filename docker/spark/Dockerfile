# Our Spark image = official Spark image + the Python packages our jobs need.
# Every Spark container (master, workers, client) uses this image, so the driver
# and the executors always have the same Python libraries.
#
# Rebuild after changing this file or requirements.txt:
#   docker compose up -d --build
FROM apache/spark:3.5.3-scala2.12-java17-python3-ubuntu

USER root
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
USER spark
