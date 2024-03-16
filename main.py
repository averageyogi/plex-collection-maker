import os
import sys
import argparse
from pathlib import Path
from typing import Union

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

        # Ensure "http://" at start of ip address
        for ip in [self.plex_ip, self.plex_pub_ip]:
            if ip and (ip[:7] != "http://") and (ip[:8] != "https://"):
                sys.exit(
                    'Invalid IP address. Ensure IP address begins "http://". '
                    'Please check the server IP addresses in .env, and consult the README.'
                )

        with open("./config.yml", encoding="utf-8") as config_file:
            try:
                config_yaml = yaml.safe_load(config_file)
            except yaml.YAMLError as err:
                print(err)
        self.libraries = [*config_yaml["libraries"]]

        self.collections_config = {}
        for lib in config_yaml["libraries"]:
            for coll_file in config_yaml["libraries"][lib]["collection_files"]:
                with open(coll_file["file"], "r", encoding="utf-8") as collection_config_file:
                    try:
                        colls = yaml.safe_load(collection_config_file)
                        self.collections_config[lib] = colls["collections"]
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
                    sys.exit('Invalid Plex token. Please check the "PLEX_TOKEN" in .env, and consult the README.')
            else:
                sys.exit(
                    "Unable to connect to Plex server. Please check the "
                    f'{"PLEX_SERVER_PUBLIC_IP" if self.using_public_ip else "PLEX_SERVER_IP"} '
                    "in .env, and consult the README."
                )
        except plexapi.exceptions.Unauthorized:
            sys.exit('Invalid Plex token. Please check the "PLEX_TOKEN" in .env, and consult the README.')

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
                sys.exit(f'Library named "{library}" not found. Please check the config.yml, and consult the README.')
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
                explained_guid = False
                try:
                    collection: Collection = library[1].collection(collection_title)
                    collections_to_update[library[0]].append(collection)
                except plexapi.exceptions.NotFound:
                    # Add items according to config list
                    print(f'Creating "{collection_title}" collection in "{library[0]}" library...')
                    collection_items: list[Movie | Show] = []
                    if ("items" in self.collections_config[library[0]][collection_title]
                        and self.collections_config[library[0]][collection_title]["items"]
                    ):
                        for item in self.collections_config[library[0]][collection_title]["items"]:
                            try:
                                # Find library item using plex guid, if provided
                                collection_items.append(library[1].getGuid(f"plex://{item.split(' plex://')[-1]}"))
                            except plexapi.exceptions.NotFound:
                                try:
                                    # Fall back to item name, library.get(title) doesn't always return the
                                    # actual item with exact title (eg Horror-of-Dracula for Drácula)
                                    collection_items.append(library[1].get(item.split(" plex://")[0]))
                                    if not explained_guid:
                                        print(
                                            "\033[33mGUID not available, incorrect matches may occur.\033[0m "
                                            "If incorrect items added to collection, consider dumping library "
                                            "and using given title from output file."
                                        )
                                        explained_guid = True
                                except plexapi.exceptions.NotFound:
                                    print(
                                        f'\033[33mItem "{item.split(" plex://")[0]}" not found in '
                                        f'"{library[0]}" library.\033[0m'
                                    )
                        if len(collection_items) > 0:
                            collection: Collection = library[1].createCollection(
                                title=collection_title, items=collection_items
                            )
                            # Set sort title
                            if ("titleSort" in self.collections_config[library[0]][collection_title]
                                and self.collections_config[library[0]][collection_title]["titleSort"]
                            ):
                                collection.editSortTitle(
                                    sortTitle=self.collections_config[library[0]][collection_title]["titleSort"]
                                )
                            # Add labels according to config list
                            if ("labels" in self.collections_config[library[0]][collection_title]
                                and self.collections_config[library[0]][collection_title]["labels"]
                            ):
                                collection.addLabel(
                                    labels=self.collections_config[library[0]][collection_title]["labels"]
                                )
                            # Upload and set poster
                            if ("poster" in self.collections_config[library[0]][collection_title]
                                and self.collections_config[library[0]][collection_title]["poster"]
                            ):
                                collection.uploadPoster(
                                    filepath=self.collections_config[library[0]][collection_title]["poster"]
                                )
                            # Set collection mode
                            if ("mode" in self.collections_config[library[0]][collection_title]
                                and self.collections_config[library[0]][collection_title]["mode"]
                            ):
                                collection.modeUpdate(
                                    mode=self.collections_config[library[0]][collection_title]["mode"]
                                )
                            # Set collection order
                            if ("sort" in self.collections_config[library[0]][collection_title]
                                and self.collections_config[library[0]][collection_title]["sort"]
                            ):
                                collection.sortUpdate(
                                    sort=self.collections_config[library[0]][collection_title]["sort"]
                                )
                        else:
                            print(
                                "\033[31mUnable to create collection. "
                                f'Collection "{collection_title}" for '
                                f'"{library[0]}" library has no items in config.\033[0m'
                            )
                    else:
                        print(
                            "\033[31mUnable to create collection. "
                            f'Collection "{collection_title}" for '
                            f'"{library[0]}" library has no items in config.\033[0m'
                        )
        return collections_to_update

    def edit_collections(
        self, plex_libraries: dict[str, LibrarySection], collections_to_update: dict[str, list[Collection]]
    ):
        """
        Edit existing collections from config lists.

        Args:
            plex_libraries (dict[str, LibrarySection]): {library name: Plex library object}
            collections_to_update (dict[str, list[Collection]]): Collections to update
        """
        for lib in collections_to_update.items():
            for coll_update in lib[1]:
                print(f'Syncing "{coll_update.title}" in "{lib[0]}" library to config...')
                if ("items" in self.collections_config[lib[0]][coll_update.title]
                    and self.collections_config[lib[0]][coll_update.title]["items"]
                ):
                    # Add new items to collection that are in config, but not collection
                    new_items = []
                    explained_guid = False
                    s: Movie
                    for s in self.collections_config[lib[0]][coll_update.title]["items"]:
                        if (s.split(" plex://")[0].encode("utf-8") not in
                            [x.title.encode("utf-8") for x in coll_update.items()]
                        ):
                            print(f'Adding "{s.split(" plex://")[0]}" to "{coll_update.title}" collection...')
                            try:
                                # Find library item using plex guid, if provided
                                new_items.append(plex_libraries[lib[0]].getGuid(f"plex://{s.split(' plex://')[-1]}"))
                            except plexapi.exceptions.NotFound:
                                try:
                                    # Fall back to item name, library.get(title) doesn't always return the
                                    # actual item with exact title (eg Horror-of-Dracula for Drácula)
                                    new_items.append(plex_libraries[lib[0]].get(s.split(" plex://")[0]))
                                    if not explained_guid:
                                        print(
                                            "\033[33mGUID not available, incorrect matches may occur.\033[0m "
                                            "If incorrect items added to collection, consider dumping library "
                                            "and using given title from output file."
                                        )
                                        explained_guid = True
                                except plexapi.exceptions.NotFound:
                                    print(
                                        f'\033[33mItem "{s.split(" plex://")[0]}" '
                                        f'not found in "{plex_libraries[lib[0]].title}" library\033[0m.'
                                    )
                    if len(new_items) > 0:
                        coll_update.addItems(items=new_items)
                    # Remove items from collection that are not in config list
                    remove_items = []
                    for s in coll_update.items():
                        if s.title.split(" plex://")[0].encode("utf-8") not in [
                            x.split(" plex://")[0].encode("utf-8")
                            for x in self.collections_config[lib[0]][coll_update.title]["items"]
                        ]:
                            print(f'Removing "{s.title}" from "{coll_update.title}" collection...')
                            remove_items.append(plex_libraries[lib[0]].getGuid(s.guid))
                            # # library.get(title) doesn't always return the
                            # # actual item with exact title (eg Horror-of-Dracula for Drácula),
                            # # so find match in full search
                            # remove_items.append(
                            #     next(x for x in plex_libraries[lib[0]].search(title=s.split(' plex://')[0])
                            #          if x.title == s.split(' plex://')[0])
                            # )
                    if len(remove_items) > 0:
                        coll_update.removeItems(items=remove_items)
                    # Update sort title
                    if ("titleSort" in self.collections_config[lib[0]][coll_update.title]
                        and self.collections_config[lib[0]][coll_update.title]["titleSort"]
                    ):
                        coll_update.editSortTitle(
                            sortTitle=self.collections_config[lib[0]][coll_update.title]["titleSort"]
                        )
                    # Add/remove labels according to config list
                    if ("labels" in self.collections_config[lib[0]][coll_update.title]
                        and self.collections_config[lib[0]][coll_update.title]["labels"]
                    ):
                        new_labels = []
                        for s in self.collections_config[lib[0]][coll_update.title]["labels"]:
                            if s not in [x.tag for x in coll_update.labels]:
                                print(f'Adding "{s}" label to "{coll_update.title}" collection...')
                                new_labels.append(s)
                        if len(new_labels) > 0:
                            coll_update.addLabel(labels=new_labels)
                        remove_labels = []
                        for s in [x.tag for x in coll_update.labels]:
                            if s not in self.collections_config[lib[0]][coll_update.title]["labels"]:
                                print(f'Removing "{s}" label from "{coll_update.title}" collection...')
                                remove_labels.append(s)
                        if len(remove_labels) > 0:
                            coll_update.removeLabel(labels=remove_labels)
                    # Update poster
                    if ("poster" in self.collections_config[lib[0]][coll_update.title]
                        and self.collections_config[lib[0]][coll_update.title]["poster"]
                    ):
                        coll_update.uploadPoster(filepath=self.collections_config[lib[0]][coll_update.title]["poster"])
                    # Update collection mode
                    if ("mode" in self.collections_config[lib[0]][coll_update.title]
                        and self.collections_config[lib[0]][coll_update.title]["mode"]
                    ):
                        coll_update.modeUpdate(mode=self.collections_config[lib[0]][coll_update.title]["mode"])
                    # Update collection order
                    if ("sort" in self.collections_config[lib[0]][coll_update.title]
                        and self.collections_config[lib[0]][coll_update.title]["sort"]
                    ):
                        coll_update.sortUpdate(sort=self.collections_config[lib[0]][coll_update.title]["sort"])
                else:
                    print(
                        f'\033[31mNo items found in config. Removing collection "{coll_update.title}" '
                        f'from "{plex_libraries[lib[0]]}" library.\033[0m'
                    )
                    coll_update.delete()

    def dump_collections(self, plex_libraries: dict[str, LibrarySection]) -> Path:
        """
        Dump existing collections to YAML files.

        Args:
            plex_libraries (dict[str, LibrarySection]): {library name: Plex library object}

        Returns:
            Path: Output directory where YAML files are saved.
        """
        for library in plex_libraries.items():
            library_collections: list[Collection] = library[1].collections()
            lib_dicts: dict[str, dict[str, dict[str, Union[str, list[str]]]]] = {}
            # # lib_dicts = {
            # #     'collections': {
            # #         'collection1': {
            # #             'titleSort': 'titleSort',
            # #             'labels': [
            # #                 'label1',
            # #                 'label2',
            # #                 'label3'
            # #             ],
            # #             'poster': 'poster',
            # #             'mode': 'mode',
            # #             'sort': 'sort',
            # #             'items': [
            # #                 'item1',
            # #                 'item2',
            # #             ]
            # #         },
            # #         'collection2': {}
            # #     }
            # # }

            lib_dicts["collections"] = {}
            for c in library_collections:
                lib_dicts["collections"][c.title] = {}
                lib_dicts["collections"][c.title]["titleSort"] = c.titleSort
                lib_dicts["collections"][c.title]["labels"] = [x.tag for x in c.labels]
                # lib_dicts['collections'][c.title]['poster'] = c.posterUrl
                lib_dicts["collections"][c.title]["mode"] = c.collectionMode
                lib_dicts["collections"][c.title]["sort"] = c.collectionSort
                lib_dicts["collections"][c.title]["items"] = [f"{x.title} {x.guid}" for x in c.items()]

            os.makedirs("./config_dump", exist_ok=True)
            config_file = Path(f'./config_dump/{library[0].replace(" ", "_")}_collections.yml')
            with open(config_file.as_posix(), "w", encoding="utf-8") as f:
                yaml.dump(lib_dicts, f)
        return config_file.parent.resolve()

    def dump_libraries(self, plex_libraries: dict[str, LibrarySection], all_fields: bool = False) -> Path:
        """
        Dump all library items to YAML files.

        Args:
            plex_libraries (dict[str, LibrarySection]): {library name: Plex library object}
            all_fields (bool, optional): Include all locked fields for each library item.

        Returns:
            Path: Output directory where YAML files are saved.
        """
        for library in plex_libraries.items():

            if all_fields:
                lib_dict: dict[str, dict[Union[str, list[str]]]] = {}
                # # lib_dicts = {
                # #     'library': {
                # #         'title1 guid1': {
                # #             'titleSort': 'titleSort',
                # #             'originalTitle': 'originalTitle',
                # #             'contentRating': 'contentRating',
                # #             'year': 'year',
                # #             'studio': 'studio',
                # #             'originallyAvailableAt': 'originallyAvailableAt',
                # #             'summary': 'summary',
                # #             'genre': [
                # #                 'genre1',
                # #                 'genre2',
                # #                 'genre3'
                # #             ],
                # #             'labels': [
                # #                 'label1',
                # #                 'label2'
                # #             ],
                # #             'collections': [
                # #                 'collection1',
                # #                 'collection2',
                # #             ]
                # #         },
                # #         'title2 guid2': {}
                # #     }
                # # }

                lib_dict[library[0]] = {}
                item: Union[Movie, Show]
                for item in library[1].all():
                    title = f"{item.title} {item.guid}"
                    lib_dict[library[0]][title] = {}

                    fields = [x.name for x in item.fields]
                    if "titleSort" in fields:
                        lib_dict[library[0]][title]["titleSort"] = item.titleSort
                    if "originalTitle" in fields:
                        lib_dict[library[0]][title]["originalTitle"] = item.originalTitle
                    if "contentRating" in fields:
                        lib_dict[library[0]][title]["contentRating"] = item.contentRating
                    if "year" in fields:
                        lib_dict[library[0]][title]["year"] = item.year
                    if "studio" in fields:
                        lib_dict[library[0]][title]["studio"] = item.studio
                    if "originallyAvailableAt" in fields:
                        lib_dict[library[0]][title]["originallyAvailableAt"] = item.originallyAvailableAt
                    if "summary" in fields:
                        lib_dict[library[0]][title]["summary"] = item.summary
                    if "genre" in fields:
                        lib_dict[library[0]][title]["genres"] = [x.tag for x in item.genres]
                    if "label" in fields:
                        lib_dict[library[0]][title]["labels"] = [x.tag for x in item.labels]
                    if "collection" in fields:
                        lib_dict[library[0]][title]["collections"] = [x.tag for x in item.collections]

            else: # Just a list of movie/show titles and guids
                lib_dict: dict[str, list[str]] = {}
                lib_dict[library[0]] = [f"{x.title} {x.guid}" for x in library[1].all()]


            os.makedirs("./library_dump", exist_ok=True)
            library_dump_file = Path(
                f'./library_dump/{library[0].replace(" ", "_")}{"_(all_fields)" if all_fields else ""}.yml'
            )
            with open(library_dump_file.as_posix(), "w", encoding="utf-8") as f:
                yaml.dump(lib_dict, f)
        return library_dump_file.parent.resolve()


def main(
    edit_collections: bool = False,
    dump_collections: bool = False,
    dump_libraries: bool = False,
    all_fields: bool = False
) -> None:
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

        pcm.edit_collections(plex_libraries=plex_libraries, collections_to_update=collections_to_update)

        print("Collections updated.")

    if dump_collections:
        print("Dumping existing collections to file...")
        stem = pcm.dump_collections(plex_libraries=plex_libraries)
        print(f'Complete. YAML files at "{stem}".')

    if dump_libraries:
        print("Dumping existing library items to file...")
        stem = pcm.dump_libraries(plex_libraries=plex_libraries, all_fields=all_fields)
        print(f'Complete. YAML files at "{stem}".')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--exclude-edit", action="store_false", help="don't create or edit collections")
    parser.add_argument("-c", "--dump-collections", action="store_true", help="dump collections to file")
    parser.add_argument("-l", "--dump-libraries", action="store_true", help="dump libraries to file")
    parser.add_argument("-a", "--all-fields", action="store_true", help="include all fields when dumping libraries")
    args = parser.parse_args()

    main(
        edit_collections=args.exclude_edit,
        dump_collections=args.dump_collections,
        dump_libraries=args.dump_libraries,
        all_fields=args.all_fields
    )
