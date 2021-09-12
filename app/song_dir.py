import os
import subprocess

from dotenv import load_dotenv

load_dotenv()
SONG_DIR = os.environ['RAINFALL_SONG_DIR']


def get_song_directory(site_id):
  start_char = site_id[0]
  return os.path.join(SONG_DIR, start_char, site_id, 'mp3')

def create_song_directory(site_id):
  subprocess.check_call(['mkdir', '-p', get_song_directory(site_id)])


def delete_song_directory(site_id):
  subprocess.check_call(['rm', '-rf', get_song_directory(site_id)])