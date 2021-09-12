from datetime import datetime
import os
import subprocess
import time

import flask

import mongo


def create_venv(name):
  try:
    output = subprocess.check_output([
        'sudo', '-u', 'www-data', '/usr/bin/python3',
        '/app/create_venv.py', name
    ],
                                     stderr=subprocess.STDOUT)
  except Exception as e:
    raise ValueError(e.output)
  return True

def clone_repo(name):
  start_char = name[0]
  subprocess.check_call([
      'sudo',
      '-u',
      'www-data',
      'mkdir',
      '-p',
      '/var/data/%s' % start_char,
  ])
  path = '/var/data/%s/%s/' % (start_char, name)
  subprocess.check_call([
      'sudo',
      '-u',
      'www-data',
      'git',
      'clone',
      'https://github.com/audiodude/rainfall-template.git',
      path,
  ])
  return True


def insert_mongo_record(name):
  start_char = name[0]
  mongo_config = {
      "name":
          "%s.ini" % name,
      "config":
          '''[uwsgi]
virtualenv = /var/data/%(start_char)s/%(name)s/venv
uid = www-data
gid = www-data
wsgi-file = /var/data/%(start_char)s/%(name)s/sitebuilder.py
plugin = python
callable = app
env = RAINFALL_SITE_ID=%(name)s
env = CHECK_REFERER=1
''' % {
              'start_char': start_char,
              'name': name
          },
      "ts":
          time.gmtime(),
      "socket":
          "/var/run/uwsgi/%s.socket" % name,
      "enabled":
          1
  }

  mongo.get_emperordb().vassals.insert_one(mongo_config)


def delete_mongo_record(name):
  mongo.get_emperordb().vassals.delete_one({'name': '%s.ini' % name})


def update_nginx(name):
  config = flask.render_template('nginx.txt', name=name)
  config_path = '/etc/nginx/sites-available/%s' % name
  enabled_path = '/etc/nginx/sites-enabled/%s' % name
  with open(config_path, 'w') as f:
    f.write(config)

  if os.path.isfile(enabled_path):
    os.unlink(enabled_path)
  os.symlink(config_path, enabled_path)
  try:
    subprocess.check_output(['sudo', 'service', 'nginx', 'reload'],
                            stderr=subprocess.STDOUT)
  except Exception as e:
    raise ValueError(e.output)


def insert_rainfall_site(user_id, name):
  year_text = datetime.now().year
  mongo.get_rainfalldb().sites.update_one({'user_id': user_id}, {
      '$set': {
          'user_id': user_id,
          'site_id': name,
          'header': 'Songs and Sounds by [Rainfall](https://rainfall.dev)',
          'footer': 'Copyright %s, All Rights Reserved' % year_text,
      }
  },
                               upsert=True)
