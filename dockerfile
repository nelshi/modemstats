FROM python:3.7-alpine
COPY . /data
WORKDIR /data
RUN pip3 install -r requirements.txt
ENTRYPOINT ["python3"]
CMD ["modemstats.py"]