from app.commands import register_preview_blueprint
from datetime import timedelta
import json
import os
import re
import time

from dotenv import load_dotenv
import flask
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
from google.oauth2 import id_token
from google.auth.transport import requests as googrequests
import pymongo
from werkzeug.utils import secure_filename

import bootstrap
from commands import insert_rainfall_site, delete_mongo_record
from deploy import build_site, create_netlify_site, create_site_zip
import mongo
from song_dir import get_song_directory, create_song_directory, delete_song_directory

load_dotenv()
GOOGLE_CLIENT_ID = os.environ['RAINFALL_CLIENT_ID']
NETLIFY_CLIENT_ID = os.environ['RAINFALL_NETLIFY_CLIENT_ID']
NETLIFY_CLIENT_SECRET = os.environ['RAINFALL_NETLIFY_CLIENT_SECRET']
SITE_URL = os.environ['RAINFALL_SITE_URL']
MONGO_URI = os.environ['RAINFALL_MONGO_URI']

app = flask.Flask(__name__)
app.config.update({
    'SESSION_TYPE': 'mongodb',
    'SESSION_MONGODB': pymongo.MongoClient(MONGO_URI, connect=False),
    'SESSION_COOKIE_SECURE': False,
    'SESSION_USE_SIGNER': True,
    'SECRET_KEY': os.environ['FLASK_SECRET'],
    'PERMANENT_SESSION_LIFETIME': timedelta(days=90),
})
Session(app)
csrf = CSRFProtect(app)
app.debug = True

ALLOWED_EXTENSIONS = set(['mp3'])

bootstrap.register_sites(MONGO_URI, app)

@app.route('/')
def index():
  if flask.session.get('user_id'):
    return flask.redirect('/edit')

  return flask.render_template('index.html', SITE_URL=SITE_URL)


@app.route('/oauth2')
def oauth2():
  return flask.render_template('capture_token.html', SITE_URL=SITE_URL)


@app.route('/capture_token')
def capture_token():
  user_id = flask.session.get('user_id')
  if user_id:
    access_token = flask.request.args.get('access_token')
    if access_token:
      mongo.get_rainfalldb().users.update_one(
          {'user_id': user_id},
          {'$set': {
              'netlify_access_token': access_token,
          }},
          upsert=True)

  return ('', 204)


@app.route('/has_netlify')
def has_netlify():
  user_id = flask.session.get('user_id')
  if not user_id:
    return flask.jsonify({'has_netlify': False})

  user = mongo.get_rainfalldb().users.find_one({'user_id': user_id})
  if not user:
    return flask.jsonify({'has_netlify': False})

  return flask.jsonify({'has_netlify': bool(user.get('netlify_access_token'))})


@app.route('/tokensignin', methods=['POST'])
def tokensignin():
  token = flask.request.form['id_token']
  try:
    idinfo = id_token.verify_oauth2_token(token, googrequests.Request(),
                                          GOOGLE_CLIENT_ID)

    if idinfo['iss'] not in ('accounts.google.com',
                             'https://accounts.google.com'):
      raise ValueError('Wrong issuer.')

    if idinfo['aud'] != GOOGLE_CLIENT_ID:
      raise ValueError('Wrong client.')

    user_id = idinfo['sub']

    mongo.get_rainfalldb().users.update_one({'user_id': user_id}, {
        '$set': {
            'user_id': user_id,
            'email': idinfo['email'],
            'name': idinfo['name'],
            'picture': idinfo['picture'],
        }
    },
                                 upsert=True)
    flask.session['user_id'] = user_id
    return ('', 204)
  except ValueError as e:
    print(e)
    # Invalid token
    return ('Sign in error', 403)


@app.route('/signout')
def signout():
  del flask.session['user_id']
  return flask.redirect('/')


@app.route('/edit')
def edit():
  user_id = flask.session.get('user_id')
  if not user_id:
    return flask.redirect('/')

  user = mongo.get_rainfalldb().users.find_one({'user_id': user_id})
  netlify_token = user and user.get('netlify_access_token')

  site = mongo.get_rainfalldb().sites.find_one({'user_id': user_id})
  if not site:
    return flask.redirect('/new')

  initial_state = {
      'netlify_client_id': NETLIFY_CLIENT_ID,
      'has_connected_netlify': bool(netlify_token),
  }

  return flask.render_template('edit.html',
                               SITE_URL=SITE_URL,
                               site=site,
                               initial_state=json.dumps(initial_state))


@app.route('/publish', methods=['POST'])
def publish():
  user_id = flask.session.get('user_id')
  if not user_id:
    return ('Not Authorized', 403)

  user = mongo.get_rainfalldb().users.find_one({'user_id': user_id})
  netlify_token = user and user.get('netlify_access_token')
  if not netlify_token:
    return ('Bad Request', 400)

  site = mongo.get_rainfalldb().sites.find_one({'user_id': user_id})
  if not site:
    return ('Bad Request', 400)

  build_site(site['site_id'])
  create_site_zip(site['site_id'])
  netlify_site_id = create_netlify_site(site['site_id'], netlify_token)

  mongo.get_rainfalldb().users.update_one({'user_id': user_id},
                               {'$set': {
                                   'netlify_site_id': netlify_site_id,
                               }},
                               upsert=True)

  return ('No Content', 204)


@app.route('/update', methods=['POST'])
def update():
  user_id = flask.session.get('user_id')
  if not user_id:
    return flask.redirect('/')

  site = mongo.get_rainfalldb().sites.find_one({'user_id': user_id})
  if not site:
    return flask.redirect('/new')

  header = flask.request.form.get('header')
  footer = flask.request.form.get('footer')

  if header is not None or footer is not None:
    mongo.get_rainfalldb().sites.update({
        'site_id': site['site_id'],
    }, {'$set': {
        'header': header,
        'footer': footer,
    }})

  return flask.redirect('/edit#site')


def allowed_file(filename):
  return '.' in filename and \
         filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_slug(filename):
  base = filename.split('.', 1)[0]
  filename = re.sub('\W', '_', base)
  return re.sub('--+', '', filename)


def process_tags(raw_tags):
  tags = []
  chunks = re.split('[ ,]', raw_tags)
  for chunk in chunks:
    if chunk.startswith('#'):
      tags.append(chunk.replace('#', ''))
  return tags


@app.route('/upload', methods=['POST'])
def upload():
  user_id = flask.session.get('user_id')
  if not user_id:
    return ('Not Authorized', 403)

  site = mongo.get_rainfalldb().sites.find_one({'user_id': user_id})
  if not site:
    return ('No site', 404)

  name = flask.request.form.get('name')
  if not name:
    return flask.jsonify({'errors': ['Name is required']})

  song = flask.request.files['song']
  if song and allowed_file(song.filename):
    slug = get_slug(secure_filename(name))
    path = os.path.join(get_song_directory(site['site_id']), slug + '.mp3')
    song.save(path)
  else:
    return flask.jsonify({'errors': ['Song is required and must be an mp3']})

  description = flask.request.form.get('description', '')
  raw_tags = flask.request.form.get('tags', '')
  tags = process_tags(raw_tags)

  song_document = {
      'name': name,
      'slug': slug,
      'description': description,
      'tags': tags,
      'date_created': time.time(),
  }

  mongo.get_rainfalldb().sites.update({
      'site_id': site['site_id'],
  }, {
      '$addToSet': {
          'songs': song_document
      },
  })

  return ('', 204)


@app.route('/new')
def new():
  user_id = flask.session.get('user_id')
  if not user_id:
    return flask.redirect('/')

  user = mongo.get_rainfalldb().users.find_one({'user_id': user_id})
  if not user:
    return flask.redirect('/')

  site = mongo.get_rainfalldb().sites.find_one({'user_id': user_id})
  if site:
    return flask.redirect('/edit')

  return flask.render_template('new.html', SITE_URL=SITE_URL, user=user)


def sanitize(name):
  name = re.sub('[^a-zA-Z0-9]', '-', name)
  name = re.sub('-+', '-', name)
  return name


@app.route('/create', methods=['POST'])
def create():
  user_id = flask.session.get('user_id')
  if not user_id:
    return flask.redirect('/')

  user = mongo.get_rainfalldb().users.find_one({'user_id': user_id})
  if not user:
    return flask.redirect('/')

  terms = flask.request.form.get('terms-check')
  if not terms:
    return flask.render_template('new.html', user=user, errors=['terms'])

  name = user['email']
  name = sanitize(name)

  create_song_directory(name)
  insert_rainfall_site(user_id, name)
  register_preview_blueprint(app, name)
  return flask.redirect('/edit')


@app.route('/destroy', methods=['POST'])
def destroy():
  user_id = flask.session.get('user_id')
  if not user_id:
    return ('Bad Request', 400)

  user = mongo.get_rainfalldb().users.find_one({'user_id': user_id})
  if not user:
    return ('Bad Request', 400)

  del flask.session['user_id']
  name = sanitize(user['email'])

  delete_song_directory(name)
  delete_mongo_record(name)

  result = mongo.get_rainfalldb().sites.delete_one({'user_id': user_id})
  if result.deleted_count < 1:
    raise Exception(user_id)
  result = mongo.get_rainfalldb().users.delete_one({'user_id': user_id})
  if result.deleted_count < 1:
    raise Exception(user_id)

  return flask.redirect('/')