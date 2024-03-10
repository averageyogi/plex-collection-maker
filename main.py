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

    def make_collections(self, plex_libraries: dict[str, LibrarySection]) -> dict[str, list[Collection]]:
        """
        Create new regular collections from config lists.

        Args:
            plex_libraries (dict[str, LibrarySection]): {library name: Plex library object}
        
        Returns:
            dict[str, list[Collection]]: {library name: list[Collection]} Preexisting collections to check for updates.
        """
        #TODO add rest of collection attrs (sorting, poster, sort name, etc)

        # print()
        collections_to_update: dict[str, list[Collection]] = {}
        for library in plex_libraries.items():
            lib_collection_titles = [*self.collections_config[library[0]].keys()]
            # print(lib_coll_titles)
            collections_to_update[library[0]] = []
            for c in lib_collection_titles:

                try:
                    collection: Collection = library[1].collection(c)
                    collections_to_update[library[0]].append(collection)
                    # print(collections_to_update)
                except plexapi.exceptions.NotFound as err:
                    print(err)

                    coll_items: list[Show] = []
                    # print(self.collections_config[library[0]][c])
                    for s in self.collections_config[library[0]][c]["items"]:
                        try:
                            coll_items.append(library[1].get(s))
                        except plexapi.exceptions.NotFound:
                            print(f'Item "{s}" not found.')
                    collection: Collection = library[1].createCollection(
                        title=c,
                        items=coll_items
                    )
                    collection.uploadPoster(filepath=self.collections_config[library[0]][c]["poster"])

                # print(collection)

        return collections_to_update

    def edit_collections(
        self,
        plex_libraries: dict[str, LibrarySection],
        collections_to_update: dict[str, list[Collection]]
    ):

        # collections_to_update['TV Shows'][0].uploadPoster(filepath="./testing.jpg")
        # collections_to_update['TV Shows'][0].batchEdits()
        # collections_to_update['TV Shows'][0]

        print()
        print('edit colls')
        for lib in collections_to_update.items():
            for coll_update in lib[1]:
                print(lib[0], coll_update)
                print(coll_update.items())
                # print(coll_update.title)
                new_items = []
                for s in self.collections_config[lib[0]][coll_update.title]["items"]:
                    if s not in map(lambda x: x.title, coll_update.items()):
                        print(f'Adding {s} to "{coll_update.title}" collection.')
                        new_items.append(plex_libraries[lib[0]].get(s))
                if len(new_items) > 0:
                    coll_update.addItems(new_items)


        #                 try:
        #                     coll_items.append(library[1].get(s))
        #                 except plexapi.exceptions.NotFound:
        #                     print(f'Item "{s}" not found.')
        #             collection: Collection = library[1].createCollection(
        #                 title=c,
        #                 items=coll_items
        #             )
        #             collection.uploadPoster(filepath=self.collections_config[library[0]][c]["poster"])




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
    for lib in plex_libraries.items():
        # print('plex lib object', lib[1])
        print(f"  {lib[0]}: ", end="")
        print(*pcm.collections_config[lib[0]].keys(), sep=", ")

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

    # print('naruto: ', tv.collection('Naruto'))
    # print('star wars: ', tv.collection('StarWars'))



    collections_to_update = pcm.make_collections(plex_libraries=plex_libraries)

    print(collections_to_update)

    #TODO Or update existing collection
    pcm.edit_collections(
        plex_libraries=plex_libraries,
        collections_to_update=collections_to_update
    )





if __name__ == "__main__":
    main()
