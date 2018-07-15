FROM resin/raspberrypi3-python:3.6

EXPOSE 5000
WORKDIR /app

COPY ./dist /app/dist
RUN pip3 install /app/dist/*
RUN pip3 show brewblox-service

ENTRYPOINT ["python3", "-m", "brewblox_service"]
