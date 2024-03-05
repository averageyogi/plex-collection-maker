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

class PlexCollectionMaker:
    """
    Create collections in Plex libraries from a text file list of shows or movies.
    """
    def __init__(self):
        self.load_config()

    def load_config(self) -> None:
        """
        Load environment variables from .env config.
        """
        self.using_public_ip = False
        try:
            self.plex_token = os.environ["PLEX_TOKEN"]
            self.tv_library = os.environ["PLEX_TV_LIBRARY"]
            self.movie_library = os.environ["PLEX_MOVIE_LIBRARY"]
        except KeyError:
            sys.exit("Error with .env file. Please consult the README.")
        try:
            self.plex_ip = os.environ["PLEX_SERVER_IP"]
        except KeyError:
            # Fallback to public ip
            try:
                self.plex_ip = os.environ["PLEX_SERVER_PUBLIC_IP"]
                self.using_public_ip = True
            except KeyError:
                sys.exit("Error with .env file. Please consult the README.")
        try:
            if not self.using_public_ip:
                self.plex_pub_ip = os.environ["PLEX_SERVER_PUBLIC_IP"]
            else:
                self.plex_pub_ip = None
        except KeyError:
            # Only local ip given
            self.plex_pub_ip = None

    def plex_setup(self) -> tuple[LibrarySection, LibrarySection]:
        """
        Load PlexAPI config.

        Returns:
            (tv, movies): tv and movie LibrarySection objects
        """
        try:
            plex = PlexServer(self.plex_ip, self.plex_token)
        except requests.exceptions.InvalidURL:
            sys.exit('Invalid IP address. Please check the server IP addresses in .env, and consult the README.')
        except requests.exceptions.RequestException:
            if self.plex_pub_ip:
                try:
                    plex = PlexServer(self.plex_pub_ip, self.plex_token)
                except requests.exceptions.RequestException:
                    sys.exit(
                        'Unable to connect to Plex server. Please check the server '
                        'IP addresses in .env, and consult the README.'
                    )
                except plexapi.exceptions.Unauthorized:
                    sys.exit(
                        'Invalid Plex token. Please check the "PLEX_TOKEN" in .env, and consult the README.'
                    )
            else:
                sys.exit(
                    'Unable to connect to Plex server. Please check the '
                    f'{"PLEX_SERVER_PUBLIC_IP" if self.using_public_ip else "PLEX_SERVER_IP"} '
                    'in .env, and consult the README.'
                )
        except plexapi.exceptions.Unauthorized:
            sys.exit(
                'Invalid Plex token. Please check the "PLEX_TOKEN" in .env, and consult the README.'
            )

        try:
            tv: LibrarySection = plex.library.section(self.tv_library)
        except plexapi.exceptions.NotFound:
            sys.exit(
                f'TV library named "{self.tv_library}" not found. Please check the "PLEX_TV_LIBRARY" in .env, '
                'and consult the README.'
            )
        try:
            movies: LibrarySection = plex.library.section(self.movie_library)
        except plexapi.exceptions.NotFound:
            sys.exit(
                f'Movie library named "{self.movie_library}" not found. Please check the "PLEX_MOVIE_LIBRARY" '
                'in .env, and consult the README.'
            )

        return tv, movies


if __name__ == "__main__":
    pcm = PlexCollectionMaker()

    tv, movies = pcm.plex_setup()
    print(tv.recentlyAdded(5))
    print(movies.recentlyAdded(5))
