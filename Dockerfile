# Based on tiangolo/uswgi-nginx-flask
# Copyright Sebastian Ramirez
# See LICENSE

FROM tiangolo/uwsgi-nginx:python3.9
RUN apt-get update \
  && apt-get install --no-install-recommends --no-install-suggests -y syslog-ng

# URL under which static (not modified by Python) files will be requested
# They will be served by Nginx directly, without being handled by uWSGI
ENV STATIC_URL /static
# Absolute path in where the static files wil be
ENV STATIC_PATH /app/static

# If STATIC_INDEX is 1, serve / with /static/index.html directly (or the static URL configured)
# ENV STATIC_INDEX 1
ENV STATIC_INDEX 0

# Add demo app
COPY ./app /app
WORKDIR /app

# Make /app/* available to be imported by Python globally to better support several use cases like Alembic migrations.
ENV PYTHONPATH=/app

# Override the base image supervisord.conf with one that specifies the uwsgi statup
# command we want along with our logging options.
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

COPY syslog-ng-extra.conf /etc/syslog-ng/conf.d/syslog-ng-extra.conf

# Move the base entrypoint to reuse it
RUN mv /entrypoint.sh /uwsgi-nginx-entrypoint.sh
# Copy the entrypoint that will generate Nginx additional configs
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Overwrite base image start.sh
COPY start.sh /start.sh
RUN chmod +x /start.sh

COPY ./app /app
RUN pip3 install --upgrade pip && \
  pip3 install --no-cache-dir -r /app/requirements.txt

ENTRYPOINT ["/entrypoint.sh"]

# Run the start script provided by the parent image tiangolo/uwsgi-nginx.
# It will check for an /app/prestart.sh script (e.g. for migrations)
# And then will start Supervisor, which in turn will start Nginx and uWSGI
CMD ["/start.sh"]
