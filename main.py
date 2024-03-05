import sys
import os
# import json

import requests
# from bs4 import BeautifulSoup
from plexapi.server import PlexServer
import plexapi.exceptions
from plexapi.library import LibrarySection
# import time
# import re
from dotenv import load_dotenv


load_dotenv()  # take environment variables from .env.

def plex_setup() -> tuple[LibrarySection, LibrarySection]:
    """
    Load PlexAPI config.

    Returns:
        (tv, movies): tv and movie LibrarySection objects
    """
    # if os.path.exists("config.json"):
    try:
        # config = json.load(open("config.json", encoding="utf-8"))
        # base_url = config["base_url"]
        plex_ip = os.environ["PLEX_SERVER_IP"]
        # token = config["token"]
        plex_token = os.environ["PLEX_TOKEN"]
        # tv_library = config["tv_library"]
        tv_library = os.environ["PLEX_TV_LIBRARY"]
        # movie_library = config["movie_library"]
        movie_library = os.environ["PLEX_MOVIE_LIBRARY"]
    except KeyError:
        sys.exit("Error with .env file. Please consult the readme.md.")
    try:
        plex = PlexServer(plex_ip, plex_token)
    except requests.exceptions.RequestException:
        sys.exit(
            'Unable to connect to Plex server. Please check the "base_url" in config.json, and consult the readme.md.'
        )
    except plexapi.exceptions.Unauthorized:
        sys.exit(
            'Invalid Plex token. Please check the "token" in config.json, and consult the readme.md.'
        )
    try:
        tv = plex.library.section(tv_library)
    except plexapi.exceptions.NotFound:
        sys.exit(
            f'TV library named "{tv_library}" not found. Please check the "tv_library" in config.json, '
            'and consult the readme.md.'
        )
    try:
        movies = plex.library.section(movie_library)
    except plexapi.exceptions.NotFound:
        sys.exit(
            f'Movie library named "{movie_library}" not found. Please check the "movie_library" in config.json, '
            'and consult the readme.md.'
        )
    return tv, movies

    # sys.exit("No config.json file found. Please consult the readme.md.")


if __name__ == "__main__":
    plex_setup()
