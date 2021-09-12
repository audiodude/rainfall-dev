import os

from dotenv import load_dotenv
import flask
import pymongo

load_dotenv()
MONGO_URI = os.environ['RAINFALL_MONGO_URI']


def has_mongo():
  return hasattr(flask.g, 'mongo')


def get_mongo():
  if not has_mongo():
    setattr(flask.g, 'mongo', pymongo.MongoClient(MONGO_URI, connect=False))
  return getattr(flask.g, 'mongo')


def get_rainfalldb():
  return get_mongo().rainfall


def get_emperordb():
  return get_mongo().emperor
