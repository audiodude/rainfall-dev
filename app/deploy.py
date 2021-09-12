import os
import subprocess

import requests

def build_site(site_id):
  start_char = site_id[0]
  base_path = '/var/data/%s/%s' % (start_char, site_id)
  try:
    subprocess.check_call([
        'sudo', '-u', 'www-data',
        'RAINFALL_SITE_ID=%s' % site_id,
        '%s/venv/bin/python3' % base_path,
        '%s/sitebuilder.py' % base_path, 'build'
    ],
                          stderr=subprocess.STDOUT)
  except Exception as e:
    raise ValueError(e.output)

def create_site_zip(site_id):
  start_char = site_id[0]
  base_path = '/var/data/%s/%s' % (start_char, site_id)
  zip_path = '%s/site.zip' % base_path
  if os.path.isfile(zip_path):
    os.unlink(zip_path)
  try:
    subprocess.check_call([
        'sudo', '-u', 'www-data', 'zip', zip_path, '-r',
        '%s/build' % base_path
    ])
  except Exception as e:
    raise ValueError(e.output)


def create_netlify_site(site_id, access_token):
  start_char = site_id[0]
  zip_path = '/var/data/%s/%s/site.zip' % (start_char, site_id)
  with open(zip_path, 'rb') as f:
    data = f.read()
  res = requests.post(url='https://api.netlify.com/api/v1/sites',
                      data=data,
                      headers={
                          'Content-Type': 'application/zip',
                          'Authorization': 'Bearer %s' % access_token,
                      })
  return res.json()['id']