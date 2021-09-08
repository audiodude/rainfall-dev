FROM tiangolo/uwsgi-nginx-flask:python3.9

COPY ./app /app
RUN pip3 install --upgrade pip && \
  pip3 install --no-cache-dir -r /app/requirements.txt