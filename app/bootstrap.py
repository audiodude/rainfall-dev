import pymongo

from commands import register_preview_blueprint

def register_sites(mongo_uri, app):
  db = pymongo.MongoClient(mongo_uri, connect=False).rainfall
  for s in db.sites.find({}, ['site_id']):
      register_preview_blueprint(app, s['site_id'])
