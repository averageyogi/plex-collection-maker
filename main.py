import sys
import argparse
from typing import Union

import plexapi.exceptions
from plexapi.library import LibrarySection
from plexapi.collection import Collection
from plexapi.video import Movie, Show
from plexapi.media import Guid
from tqdm import tqdm

from plex_connection import PlexConnection
from plex_lock_posters import lock_posters
from dump_to_yaml import dump_collections as col2yaml, dump_libraries as lib2yaml


class PlexCollectionMaker:
    """Create collections in Plex libraries from a text file list of shows or movies."""
    def __init__(self, edit_collections: bool):
        """
        Create collections in Plex libraries from a text file list of shows or movies.

        Args:
            edit_collections (bool, optional): If true, load collection config files. If false, skip loading any
                collection configs.
        """
        self.pc = PlexConnection(edit_collections)

    def get_libraries(self) -> "dict[str, LibrarySection]":
        """
        Return accessible Plex libraries.

        Returns:
            dict[str, LibrarySection]: {library name: Plex library object}
        """
        plex_libraries: "dict[str, LibrarySection]" = {}
        for library in self.pc.config_libraries:
            try:
                plex_libraries[library] = self.pc.plex.library.section(library)
            except plexapi.exceptions.NotFound:
                sys.exit(f'Library named "{library}" not found. Please check the config.yml, and consult the README.')
        return plex_libraries

    def get_item_guid(
        self, title: str, lib_type: str, full: bool = False
    ) -> str:
        """
        Get available GUID from provided item string.

        Args:
            title (str): String that contains a GUID in the form {[source]-[id]}.
                Plex guid is in the form plex://[type]/[id]
            lib_type (str): either "movie" or "show" to determine available GUIDs
            full (bool, optional): If false, return only id ([type]/[id] if Plex).
                If true, return full GUID, [source]://[id] (including type if Plex).
                Defaults to False.

        Raises:
            plexapi.exceptions.UnknownType: if provided lib_type is neither "movie" or "show"

        Returns:
            str: the available GUID of the title, returns "-1" if no GUID is available
        """
        try:
            lib_sources = {
                "movie": ["tmdb", "imdb", "plex"],
                "show": ["tvdb", "tmdb", "plex"]
            }
            for source in lib_sources[lib_type]:
                if title.find(source) == -1:
                    # source not found in title
                    continue
                if source == "plex":
                    guid = title.split(sep="plex://")[-1].split()[0]
                else:
                    guid = title.split(sep=f"{{{source}-")[-1].split(sep="}")[0]

                if full:
                    return f"{source}://{guid}"
                return guid
            return "-1"
        except KeyError as exc:
            raise plexapi.exceptions.UnknownType from exc

    def make_collections(self, plex_libraries: "dict[str, LibrarySection]") -> "dict[str, list[Collection]]":
        """
        Create new regular collections from config lists.

        Args:
            plex_libraries (dict[str, LibrarySection]): {library name: Plex library object}

        Returns:
            dict[str, list[Collection]]: {library name: list[Collection]} Preexisting collections to check for updates.
        """
        collections_to_update: "dict[str, list[Collection]]" = {}
        explained_guid = False
        for library in plex_libraries.items():
            collections_to_update[library[0]] = []
            collection_title: str
            for collection_title in [*self.pc.collections_config[library[0]].keys()]:
                try:
                    collection: Collection = library[1].collection(collection_title)
                    # If the collection was found, add to list to update/sync and continue to next in config
                    collections_to_update[library[0]].append(collection)
                except plexapi.exceptions.NotFound:
                    # If the collection wasn't found in the library, add items according to config list
                    print(f'Creating "{collection_title}" collection in "{library[0]}" library...')
                    collection_items: "list[Movie | Show]" = []
                    if ("items" in self.pc.collections_config[library[0]][collection_title]
                        and self.pc.collections_config[library[0]][collection_title]["items"]
                    ):
                        config_item: str
                        for config_item in self.pc.collections_config[library[0]][collection_title]["items"]:
                            try:
                                # Find library item using plex guid, if provided
                                collection_items.append(
                                    library[1].getGuid(self.get_item_guid(config_item, library[1].type, full=True))
                                )
                            except plexapi.exceptions.NotFound:
                                try:
                                    # Fall back to item name, library.get(title) doesn't always return the
                                    # actual item with exact title (eg Horror-of-Dracula for Drácula),
                                    # so find match in full search
                                    search = next(
                                        (
                                            lib_item for lib_item in plex_libraries[library[0]].search(
                                                title=config_item.split(' plex://')[0].split(' {')[0]
                                            ) if lib_item.title == config_item.split(' plex://')[0].split(' {')[0]
                                        ),
                                        None
                                    )
                                    if search is None:
                                        raise plexapi.exceptions.NotFound from None
                                    collection_items.append(search)

                                    if not explained_guid:
                                        print(
                                            "\033[33mGUID not available, incorrect matches may occur.\033[0m "
                                            "If incorrect items added to collection, consider dumping library "
                                            "and using given title from output file."
                                        )
                                        explained_guid = True
                                except plexapi.exceptions.NotFound:
                                    print(
                                        f'\033[33mItem "{config_item.split(" plex://")[0]}" not found in '
                                        f'"{library[0]}" library.\033[0m'
                                    )
                        if len(collection_items) > 0:
                            # Create collection
                            collection: Collection = library[1].createCollection(
                                title=collection_title, items=collection_items
                            )
                            fields = [
                                ("titleSort",       collection.editSortTitle),
                                ("contentRating",   collection.editContentRating),
                                ("summary",         collection.editSummary),
                                ("labels",          collection.addLabel),
                                ("poster",          collection.uploadPoster),
                                ("mode",            collection.modeUpdate),
                                ("sort",            collection.sortUpdate)
                            ]
                            for field, edit_func in fields:
                                if (field in self.pc.collections_config[library[0]][collection_title]
                                    and self.pc.collections_config[library[0]][collection_title][field]
                                ):
                                    if field == "poster":
                                        if (self.pc.collections_config[
                                                library[0]][collection_title][field][:7] == "http://"
                                            or self.pc.collections_config[
                                                library[0]][collection_title][field][:8] == "https://"
                                        ):
                                            edit_func(
                                                url=self.pc.collections_config[library[0]][collection_title][field]
                                            )
                                        else:
                                            edit_func(
                                                filepath=self.pc.collections_config[library[0]][collection_title][field]
                                            )
                                    else:
                                        edit_func(self.pc.collections_config[library[0]][collection_title][field])
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
        self, plex_libraries: "dict[str, LibrarySection]", collections_to_update: "dict[str, list[Collection]]"
    ):
        """
        Edit existing collections from config lists.

        Args:
            plex_libraries (dict[str, LibrarySection]): {library name: Plex library object}
            collections_to_update (dict[str, list[Collection]]): Collections to update
        """
        for lib in collections_to_update.items():
            for collection_update in lib[1]:
                if collection_update.smart:
                    print(
                        f'\033[31mUnable to create or update smart collections. '
                        f'Ignoring "{collection_update.title}" collection.\033[0m'
                    )
                    continue
                print(f'Syncing "{collection_update.title}" in "{lib[0]}" library to config...')
                if ("items" in self.pc.collections_config[lib[0]][collection_update.title]
                    and self.pc.collections_config[lib[0]][collection_update.title]["items"]
                ):
                    # Add new items to collection that are in config, but not collection
                    new_items = []
                    explained_guid = False
                    config_item: str
                    for config_item in self.pc.collections_config[lib[0]][collection_update.title]["items"]:
                        if (config_item.split(" plex://")[0].split(" {")[0].encode("utf-8") not in
                            [lib_item.title.encode("utf-8") for lib_item in collection_update.items()]
                        ):
                            print(
                                f'Adding "{config_item.split(" plex://")[0].split(" {")[0]}" '
                                f'to "{collection_update.title}" collection...'
                            )
                            try:
                                # Find library item using plex guid, if provided
                                new_items.append(
                                    plex_libraries[lib[0]].getGuid(
                                        self.get_item_guid(config_item, plex_libraries[lib[0]].type, full=True)
                                    )
                                )
                            except plexapi.exceptions.NotFound:
                                try:
                                    # Fall back to item name, library.get(title) doesn't always return the
                                    # actual item with exact title (eg Horror-of-Dracula for Drácula),
                                    # so find match in full search
                                    search = next(
                                        (
                                            lib_item for lib_item in plex_libraries[lib[0]].search(
                                                title=config_item.split(' plex://')[0].split(' {')[0]
                                            ) if lib_item.title == config_item.split(' plex://')[0].split(' {')[0]
                                        ),
                                        None
                                    )
                                    if search is None:
                                        raise plexapi.exceptions.NotFound from None
                                    new_items.append(search)

                                    if not explained_guid:
                                        print(
                                            "\033[33mGUID not available, incorrect matches may occur.\033[0m "
                                            "If incorrect items added to collection, consider dumping library "
                                            "and using given title from output file."
                                        )
                                        explained_guid = True
                                except plexapi.exceptions.NotFound:
                                    print(
                                        f'\033[33mItem "{config_item.split(" plex://")[0]}" '
                                        f'not found in "{plex_libraries[lib[0]].title}" library\033[0m.'
                                    )
                    if len(new_items) > 0:
                        collection_update.addItems(items=new_items)

                    # Remove items from collection that are not in config list
                    remove_items = []
                    lib_item: Union[Movie, Show]
                    for lib_item in collection_update.items():
                        remove_item_from_coll = True
                        config_guids = []
                        config_item: str
                        for config_item in self.pc.collections_config[lib[0]][collection_update.title]["items"]:
                            # Get any guids provided for items in config
                            config_guids.append(self.get_item_guid(config_item, plex_libraries[lib[0]].type))

                            # If item in collection matches an item in the config, don't remove
                            sg: Guid
                            for sg in lib_item.guids:
                                if (config_item.find(sg.id.split("://")[-1]) != -1
                                    or sg.id.split("://")[-1] in config_guids
                                ):
                                    remove_item_from_coll = False
                            if config_item.find(lib_item.guid) != -1:
                                remove_item_from_coll = False

                        # This is back-up, if name in config doesn't match
                        # the exact title used in Plex, this check will fail
                        remove_item_from_coll = (
                            remove_item_from_coll
                            and lib_item.title.encode("utf-8") not in [
                                config_item.split(" plex://")[0].split(" {")[0].encode("utf-8")
                                for config_item in self.pc.collections_config[lib[0]][collection_update.title]["items"]
                            ]
                        )

                        if remove_item_from_coll:
                            print(f'Removing "{lib_item.title}" from "{collection_update.title}" collection...')
                            remove_items.append(plex_libraries[lib[0]].getGuid(lib_item.guid))
                    if len(remove_items) > 0:
                        collection_update.removeItems(items=remove_items)

                    fields = [
                        ("titleSort",       collection_update.editSortTitle),
                        ("contentRating",   collection_update.editContentRating),
                        ("summary",         collection_update.editSummary),
                        ("poster",          collection_update.uploadPoster),
                        ("mode",            collection_update.modeUpdate),
                        ("sort",            collection_update.sortUpdate)
                    ]
                    for field, edit_func in fields:
                        if (field in self.pc.collections_config[lib[0]][collection_update.title]
                            and self.pc.collections_config[lib[0]][collection_update.title][field]
                        ):
                            if field == "poster":
                                if (self.pc.collections_config[
                                        lib[0]][collection_update.title][field][:7] == "http://"
                                    or self.pc.collections_config[
                                        lib[0]][collection_update.title][field][:8] == "https://"
                                ):
                                    edit_func(url=self.pc.collections_config[lib[0]][collection_update.title][field])
                                else:
                                    edit_func(
                                        filepath=self.pc.collections_config[lib[0]][collection_update.title][field]
                                    )
                            else:
                                edit_func(self.pc.collections_config[lib[0]][collection_update.title][field])
                        #TODO if not in config, check locked?, confirm with user to unlock, and revert/rescan?

                    # Add/remove labels according to config list
                    if "labels" in self.pc.collections_config[lib[0]][collection_update.title]:
                        if self.pc.collections_config[lib[0]][collection_update.title]["labels"]:
                            new_labels = []
                            for config_label in self.pc.collections_config[lib[0]][collection_update.title]["labels"]:
                                if config_label not in [x.tag for x in collection_update.labels]:
                                    print(f'Adding "{config_label}" label to "{collection_update.title}" collection...')
                                    new_labels.append(config_label)
                            if len(new_labels) > 0:
                                collection_update.addLabel(labels=new_labels)
                            remove_labels = []
                            for lib_label in [x.tag for x in collection_update.labels]:
                                if lib_label not in (
                                    self.pc.collections_config[lib[0]][collection_update.title]["labels"]):
                                    print(
                                        f'Removing "{lib_label}" label from "{collection_update.title}" collection...'
                                    )
                                    remove_labels.append(lib_label)
                            if len(remove_labels) > 0:
                                collection_update.removeLabel(labels=remove_labels)
                        else:
                            # Labels section in config, but no tags listed, remove all from library collection
                            collection_update.removeLabel(
                                labels=[x.tag for x in collection_update.labels],
                                locked=False
                            )
                else:
                    print(
                        f'\033[31mNo items found in config. Removing collection "{collection_update.title}" '
                        f'from "{plex_libraries[lib[0]]}" library.\033[0m'
                    )
                    collection_update.delete()


def main(
    edit_collections: bool = False,
    dump_collections: bool = False,
    dump_libraries: bool = False,
    all_fields: bool = False,
    lock_poster_art: bool = False,
) -> None:
    """
    Function to run script logic.
    """
    print("Loading Plex config...")
    pcm = PlexCollectionMaker(edit_collections=edit_collections)

    plex_libs = pcm.get_libraries()

    print("Found Plex libraries: ", end="")
    print(*plex_libs.keys(), sep=", ")
    if edit_collections:
        print("Found collection configs:")
        for lib in plex_libs.items():
            print(f"  {lib[0]}: ", end="")
            print(*pcm.pc.collections_config[lib[0]].keys(), sep=", ")
    print()

    if edit_collections:
        collections_to_update = pcm.make_collections(plex_libraries=plex_libs)

        pcm.edit_collections(
            plex_libraries=plex_libs,
            collections_to_update=collections_to_update
        )

        print("Collections updated.")

    if dump_collections:
        print("Dumping existing collections to file...")
        output_dir = col2yaml(plex_libraries=plex_libs)
        print(f'Complete. YAML files at "{output_dir}".')

    if dump_libraries:
        print("Dumping existing library items to file...")
        output_dir = lib2yaml(plex_libraries=plex_libs, all_fields=all_fields)
        print(f'Complete. YAML files at "{output_dir}".')

    if lock_poster_art:
        print("Locking posters and background art...")
        lock_posters(plex_libraries=plex_libs)
        print("Art locked.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--exclude-edit", action="store_false", help="don't create or edit collections")
    parser.add_argument("-c", "--dump-collections", action="store_true", help="dump collections to file")
    parser.add_argument("-l", "--dump-libraries", action="store_true", help="dump libraries to file")
    parser.add_argument("-a", "--all-fields", action="store_true", help="include all fields when dumping libraries")
    parser.add_argument("-p", "--lock-posters", action="store_true", help="lock all poster and background art fields")
    args = parser.parse_args()

    main(
        edit_collections=args.exclude_edit,
        dump_collections=args.dump_collections,
        dump_libraries=args.dump_libraries,
        all_fields=args.all_fields,
        lock_poster_art=args.lock_posters,
    )
