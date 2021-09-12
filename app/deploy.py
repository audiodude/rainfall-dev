import os
import subprocess


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