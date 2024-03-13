import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import plexapi.exceptions
from plexapi.server import PlexServer
from plexapi.library import LibrarySection
from plexapi.collection import Collection
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

        #TODO clean/ensure http:// at start of ip address
        print(self.plex_ip[:8])


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
                    f'{"PLEX_SERVER_PUBLIC_IP" if self.using_public_ip else "PLEX_SERVER_IP"} '
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
        collections_to_update: dict[str, list[Collection]] = {}
        for library in plex_libraries.items():
            collections_to_update[library[0]] = []
            for collection_title in [*self.collections_config[library[0]].keys()]:
                try:
                    collection: Collection = library[1].collection(collection_title)
                    collections_to_update[library[0]].append(collection)
                except plexapi.exceptions.NotFound: # as e:
                    # print(e)

                    # Add items according to config list
                    print(f'Creating "{collection_title}" collection in {library[0]} library...')
                    collection_items: list[Movie | Show] = []
                    if ("items" in self.collections_config[library[0]][collection_title] and
                        self.collections_config[library[0]][collection_title]["items"]):
                        for item in self.collections_config[library[0]][collection_title]["items"]:
                            try:
                                # print(item.split(' tmdb-'))
                                collection_items.append(library[1].get(item.split(' tmdb-')[0]))
                                # collection_items.append(library[1].getGuid(item)) #TODO test Drácula vs Dracula vs Countess Dracula
                                # print(item)
                                # print(library[1].getGuid(f"tmdb://{item.split('tmdb-')[-1]}"))
                                # collection_items.append(library[1].getGuid(f"{item.split(' tmdb-')[-1]}"))
                            except plexapi.exceptions.NotFound:
                                print(f'Item "{item}" not found in {library[0]} library.')
                        if len(collection_items) > 0:
                            collection: Collection = library[1].createCollection(
                                title=collection_title,
                                items=collection_items
                            )
                            # Set sort title
                            if ("titleSort" in self.collections_config[library[0]][collection_title] and
                                self.collections_config[library[0]][collection_title]["titleSort"]):
                                collection.editSortTitle(
                                    sortTitle=self.collections_config[library[0]][collection_title]["titleSort"]
                                )
                            # Add labels according to config list
                            if ("labels" in self.collections_config[library[0]][collection_title] and
                                self.collections_config[library[0]][collection_title]["labels"]):
                                collection.addLabel(
                                    labels=self.collections_config[library[0]][collection_title]["labels"]
                                )
                            # Upload and set poster
                            if ("poster" in self.collections_config[library[0]][collection_title] and
                                self.collections_config[library[0]][collection_title]["poster"]):
                                collection.uploadPoster(
                                    filepath=self.collections_config[library[0]][collection_title]["poster"]
                                )
                            # Set collection mode
                            if ("mode" in self.collections_config[library[0]][collection_title] and
                                self.collections_config[library[0]][collection_title]["mode"]):
                                collection.modeUpdate(
                                    mode=self.collections_config[library[0]][collection_title]["mode"]
                                )
                            # Set collection order
                            if ("sort" in self.collections_config[library[0]][collection_title] and
                                self.collections_config[library[0]][collection_title]["sort"]):
                                collection.sortUpdate(
                                    sort=self.collections_config[library[0]][collection_title]["sort"]
                                )
                        else:
                            print(
                                f'\033[31mCollection "{collection_title}" for '
                                f'"{library[0]}" library has no items in config. '
                                'Unable to create collection.\033[0m'
                            )
                    else:
                        print(
                            f'\033[31mCollection "{collection_title}" for '
                            f'"{library[0]}" library has no items in config. '
                            'Unable to create collection.\033[0m'
                        )
        return collections_to_update

    def edit_collections(
        self,
        plex_libraries: dict[str, LibrarySection],
        collections_to_update: dict[str, list[Collection]]
    ):
        """
        Edit existing collections from config lists.

        Args:
            plex_libraries (dict[str, LibrarySection]): {library name: Plex library object}
            collections_to_update (dict[str, list[Collection]]): Collections to update
        """
        for lib in collections_to_update.items():
            for coll_update in lib[1]:
                print(f'Syncing "{coll_update.title}" in "{lib[0]}" library to config.')
                # Add/remove items according to config list
                if ("items" in self.collections_config[lib[0]][coll_update.title] and
                    self.collections_config[lib[0]][coll_update.title]["items"]):
                    new_items = []
                    for s in self.collections_config[lib[0]][coll_update.title]["items"]:
                        if (s.split(' tmdb-')[0].encode('utf-8') not in
                            map(lambda x: x.title.encode('utf-8'), coll_update.items())):
                            print(f'Adding {s} to "{coll_update.title}" collection...')
                            new_items.append(plex_libraries[lib[0]].get(s.split(' tmdb-')[0]))
                            # new_items.append(plex_libraries[lib[0]].getGuid(f"tmdb://{s.split('tmdb-')[-1]}")) #TODO
                    if len(new_items) > 0:
                        coll_update.addItems(items=new_items)
                    remove_items = []
                    for s in map(lambda x: x.title, coll_update.items()):
                        if (s.split(' tmdb-')[0].encode('utf-8') not in
                            map(
                                lambda x: x.split(' tmdb-')[0].encode('utf-8'),
                                self.collections_config[lib[0]][coll_update.title]["items"]
                            )
                        ):
                            print(f'Removing {s} from "{coll_update.title}" collection...')
                            # library.get(title) doesn't always return the
                            # actual item with exact title (eg Horror-of-Dracula for Drácula),
                            # so find match in full search
                            remove_items.append(
                                next(x for x in plex_libraries[lib[0]].search(title=s.split(' tmdb-')[0])
                                     if x.title == s.split(' tmdb-')[0])
                            )
                    if len(remove_items) > 0:
                        coll_update.removeItems(items=remove_items)
                # Update sort title
                if ("titleSort" in self.collections_config[lib[0]][coll_update.title] and
                    self.collections_config[lib[0]][coll_update.title]["titleSort"]):
                    coll_update.editSortTitle(
                        sortTitle=self.collections_config[lib[0]][coll_update.title]["titleSort"]
                    )
                # Add/remove labels according to config list
                if ("labels" in self.collections_config[lib[0]][coll_update.title] and
                    self.collections_config[lib[0]][coll_update.title]["labels"]):
                    new_labels = []
                    for s in self.collections_config[lib[0]][coll_update.title]["labels"]:
                        if s not in map(lambda x: x.tag, coll_update.labels):
                            print(f'Adding {s} label to "{coll_update.title}" collection...')
                            new_labels.append(s)
                    if len(new_labels) > 0:
                        coll_update.addLabel(labels=new_labels)
                    remove_labels = []
                    for s in map(lambda x: x.tag, coll_update.labels):
                        if s not in self.collections_config[lib[0]][coll_update.title]["labels"]:
                            print(f'Removing {s} label from "{coll_update.title}" collection...')
                            remove_labels.append(s)
                    if len(remove_labels) > 0:
                        coll_update.removeLabel(labels=remove_labels)
                # Update poster
                if ("poster" in self.collections_config[lib[0]][coll_update.title] and
                    self.collections_config[lib[0]][coll_update.title]["poster"]):
                    coll_update.uploadPoster(
                        filepath=self.collections_config[lib[0]][coll_update.title]["poster"]
                    )
                # Update collection mode
                if ("mode" in self.collections_config[lib[0]][coll_update.title] and
                    self.collections_config[lib[0]][coll_update.title]["mode"]):
                    coll_update.modeUpdate(mode=self.collections_config[lib[0]][coll_update.title]["mode"])
                # Update collection order
                if ("sort" in self.collections_config[lib[0]][coll_update.title] and
                    self.collections_config[lib[0]][coll_update.title]["sort"]):
                    coll_update.sortUpdate(sort=self.collections_config[lib[0]][coll_update.title]["sort"])

    def dump_collections(self, plex_libraries: dict[str, LibrarySection]):
        """
        Dump existing collections to YAML files.

        Args:
            plex_libraries (dict[str, LibrarySection]): {library name: Plex library object}
        """
        for library in plex_libraries.items():
            library_collections: list[Collection] = library[1].collections()
            lib_dicts: dict[
                str, dict[
                    str, dict[
                        str, str | list[str]
                    ]
                ]
            ] = {}
            lib_dicts['collections'] = {}
            for c in library_collections:
                lib_dicts['collections'][c.title] = {}
                lib_dicts['collections'][c.title]['titleSort'] = c.titleSort
                lib_dicts['collections'][c.title]['labels'] = [*map(lambda x: x.tag, c.labels)]
                # lib_dicts['collections'][c.title]['poster'] = c.posterUrl
                lib_dicts['collections'][c.title]['mode'] = c.collectionMode
                lib_dicts['collections'][c.title]['sort'] = c.collectionSort
                lib_dicts['collections'][c.title]['items'] = [*map(lambda x: x.title, c.items())]
            print(lib_dicts)

            # test_dict = {
            #     'collections': {
            #         'collection1': {
            #             'titleSort': 'titleSort',
            #             'labels': [
            #                 'label1',
            #                 'label2',
            #                 'label3'
            #             ],
            #             'poster': 'poster',
            #             'mode': 'mode',
            #             'sort': 'sort',
            #             'items': [
            #                 'item1',
            #                 'item2',
            #             ]
            #         },
            #         'collection2': {}
            #     }
            # }
            os.makedirs("./config_dump2", exist_ok=True)
            config_file = Path(f'./config_dump2/{library[0].replace(" ", "_")}_collections.yml')
            # config_file.mkdir(parents=True, exist_ok=True)
            with open(config_file.as_posix(), "w", encoding="utf-8") as f:
                yaml.dump(lib_dicts, f)
        return config_file.parent.resolve()


def main(edit_collections: bool = False, dump_collections: bool = False) -> None:
    """
    Function to run script logic.
    """
    pcm = PlexCollectionMaker()

    plex_libraries = pcm.get_libraries()

    print("Found Plex libraries: ", end="")
    print(*plex_libraries.keys(), sep=", ")
    print("Found collection configs:")
    for lib in plex_libraries.items():
        print(f"  {lib[0]}: ", end="")
        print(*pcm.collections_config[lib[0]].keys(), sep=", ")
    print()

    if edit_collections:
        collections_to_update = pcm.make_collections(plex_libraries=plex_libraries)

        pcm.edit_collections(
            plex_libraries=plex_libraries,
            collections_to_update=collections_to_update
        )

        print("Collections updated.")

    if dump_collections:
        print("Dumping existing collections to file...")
        stem = pcm.dump_collections(plex_libraries=plex_libraries)
        print(f'Complete. YAML files at "{stem}".')


if __name__ == "__main__":
    main(
        edit_collections=True,
        dump_collections=False
    )
