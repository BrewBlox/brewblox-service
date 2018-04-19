FROM python:3.6

RUN mkdir -p /pkg
COPY ./pkg/* /pkg/

EXPOSE 5000

RUN pip3 install /pkg/* || true \
    && pip3 install brewblox-service \
    && pip3 show brewblox-service

ENTRYPOINT ["python3", "-m", "brewblox_service"]
