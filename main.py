import os
import sys

from dotenv import load_dotenv
import plexapi.exceptions
from plexapi.server import PlexServer
from plexapi.library import LibrarySection
from plexapi.collection import Collection
from plexapi.media import Poster
from plexapi.video import Movie, Show
import requests
import yaml


load_dotenv(override=True)  # Take environment variables from .env

class PlexCollectionMaker:
    """
    Create collections in Plex libraries from a text file list of shows or movies.
    """
    def __init__(self):
        self.load_config()
        self.plex_setup()

    def load_config(self) -> None:
        """
        Load environment variables from .env and library configuration from config.yml.
        """
        self.using_public_ip = False
        try:
            self.plex_token = os.environ["PLEX_TOKEN"]
        except KeyError:
            sys.exit('Cannot find "PLEX_TOKEN" in .env file. Please consult the README.')

        try:
            self.plex_ip = os.environ["PLEX_SERVER_IP"]
        except KeyError:
            # Fallback to public ip
            try:
                self.plex_ip = os.environ["PLEX_SERVER_PUBLIC_IP"]
                self.using_public_ip = True
            except KeyError:
                sys.exit("Cannot find IP address in .env file. Please consult the README.")
        try:
            if not self.using_public_ip:
                self.plex_pub_ip = os.environ["PLEX_SERVER_PUBLIC_IP"]
            else:
                self.plex_pub_ip = None
        except KeyError:
            # Only local ip given
            self.plex_pub_ip = None

        with open("./config.yml", encoding="utf-8") as config_file:
            try:
                config_yaml = yaml.safe_load(config_file)
            except yaml.YAMLError as err:
                print(err)
        self.libraries = [*config_yaml['libraries']]

        self.collections_config = {}
        for lib in config_yaml['libraries']:
            for coll_file in config_yaml['libraries'][lib]['collection_files']:
                with open(coll_file['file'], encoding="utf-8") as collection_config_file:
                    try:
                        colls = yaml.safe_load(collection_config_file)
                        self.collections_config[lib] = colls['collections']
                    except yaml.YAMLError as err:
                        print(err)

    def plex_setup(self) -> None:
        """
        Load PlexAPI config and connect to server.
        """
        try:
            self.plex = PlexServer(self.plex_ip, self.plex_token)
        except requests.exceptions.InvalidURL:
            sys.exit("Invalid IP address. Please check the server IP addresses in .env, and consult the README.")
        except requests.exceptions.RequestException:
            if self.plex_pub_ip:
                try:
                    self.plex = PlexServer(self.plex_pub_ip, self.plex_token)
                except requests.exceptions.RequestException:
                    sys.exit(
                        "Unable to connect to Plex server. Please check the server "
                        "IP addresses in .env, and consult the README."
                    )
                except plexapi.exceptions.Unauthorized:
                    sys.exit(
                        'Invalid Plex token. Please check the "PLEX_TOKEN" in .env, and consult the README.'
                    )
            else:
                sys.exit(
                    "Unable to connect to Plex server. Please check the "
                    f"{"PLEX_SERVER_PUBLIC_IP" if self.using_public_ip else "PLEX_SERVER_IP"} "
                    "in .env, and consult the README."
                )
        except plexapi.exceptions.Unauthorized:
            sys.exit(
                'Invalid Plex token. Please check the "PLEX_TOKEN" in .env, and consult the README.'
            )

    def get_libraries(self) -> dict[str, LibrarySection]:
        """
        Return accessible Plex libraries.

        Returns:
            dict[str, LibrarySection]: {library name: Plex library object}
        """
        plex_libraries: dict[str, LibrarySection] = {}
        for library in self.libraries:
            try:
                plex_libraries[library] = self.plex.library.section(library)
            except plexapi.exceptions.NotFound:
                sys.exit(
                    f'Library named "{library}" not found. Please check the config.yml, and consult the README.'
                )

        return plex_libraries

def main() -> None:
    """
    Function to run script logic.
    """
    pcm = PlexCollectionMaker()

    plex_libraries = pcm.get_libraries()

    # print()
    # print(plex_libraries['Movies'].title)
    # print(plex_libraries["Movies"].recentlyAdded(5))

    print("Found Plex libraries: ", end="")
    print(*plex_libraries.keys(), sep=", ")
    print("Found collection configs:")
    for lib in plex_libraries:
        print(f"  {lib}: ", end="")
        print(*pcm.collections_config[lib].keys(), sep=", ")

    print()
    for lib in plex_libraries:
        print(pcm.collections_config[lib])

    print()
    print(plex_libraries["TV Shows"].collections())
    print()
    print()

    # bbcearth: Collection = plex_libraries["TV Shows"].collection("BBC Earth")
    # print(bbcearth.posters())
    # bbcearthposter: Poster = bbcearth.posters()[0]
    # bbcearth.setPoster(bbcearthposter)


    #TODO remove "TV Shows", loop over all libraries, refactor into function
    #TODO add rest of collection attrs (sorting, poster, sort name, etc)
    # Create a regular collection
    # movies = plex.library.section("Movies")
    tv = plex_libraries["TV Shows"]
    tv_coll_titles = [*pcm.collections_config["TV Shows"].keys()]
    print(tv_coll_titles)
    for c in tv_coll_titles:
        shows: list[Show] = []
        for s in pcm.collections_config["TV Shows"][c]['shows']:
            try:
                shows.append(tv.get(s))
            except plexapi.exceptions.NotFound:
                print(f'show "{s}" not found')
        try:
            collection = None
            tv.collection(c)
        except plexapi.exceptions.NotFound:
            collection: Collection = tv.createCollection(
                title=c,
                items=shows
            )
        print(collection)
    print(shows)

    # print('naruto: ', tv.collection('Naruto'))
    # print('star wars: ', tv.collection('StarWars'))




if __name__ == "__main__":
    main()
