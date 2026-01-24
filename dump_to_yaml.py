import os
from pathlib import Path
from typing import Union, cast

from plexapi.library import LibrarySection
from plexapi.collection import Collection
from plexapi.video import Movie, Show
from plexapi.media import Field, Label
from tqdm import tqdm
import yaml


def dump_collections(plex_libraries: dict[str, LibrarySection]) -> Path:
    """
    Dump existing collections to YAML files.

    Args:
        plex_libraries (dict[str, LibrarySection]): {library name: Plex library object}

    Returns:
        Path: Output directory where YAML files are saved.
    """
    for library in plex_libraries.items():
        library_collections = cast(list[Collection], library[1].collections())
        collections_dict: dict[
            str, dict[  # "Collections", title/header
                str, dict[  # each named collection
                    str, Union[str, list[str]]  # that collection's fields
                ]
            ]
        ] = {}
        # # lib_dicts = {
        # #     'collections': {
        # #         'collection1': {
        # #             'items': [
        # #                 'item1',
        # #                 'item2',
        # #             ],
        # #             'labels': [
        # #                 'label1',
        # #                 'label2',
        # #                 'label3'
        # #             ],
        # #             'poster': 'poster',
        # #             'mode': 'mode',
        # #             'sort': 'sort',
        # #             'titleSort': 'titleSort',
        # #         },
        # #         'collection2': {}
        # #     }
        # # }

        mode_dict = {
            -1: "default",
            0: "hide",
            1: "hideItems",
            2: "showItems"
        }
        sort_dict = {
            0: "release",
            1: "alpha",
            2: "custom"
        }
        collections_dict["collections"] = {}
        for c in tqdm(
            library_collections,
            total=len(library_collections),
            ascii=" ░▒█",
            ncols=100,
            desc=library[0],
            unit="collection"
        ):
            # API typing
            c.title = cast(str, c.title)

            collections_dict["collections"][c.title] = {}
            fields: list[str] = [x.name for x in cast(list[Field], c.fields)]
            collections_dict["collections"][c.title]["smart"] = str(cast(bool, c.smart))
            if "titleSort" in fields:
                collections_dict["collections"][c.title]["titleSort"] = cast(str, c.titleSort)
            if "label" in fields:
                collections_dict["collections"][c.title]["labels"] = [x.tag for x in cast(list[Label], c.labels)]
            if "contentRating" in fields:
                collections_dict["collections"][c.title]["contentRating"] = cast(str, c.contentRating)
            if "summary" in fields:
                collections_dict["collections"][c.title]["summary"] = cast(str, c.summary)
            # collections_dict['collections'][c.title]['poster'] = c.posterUrl
            collections_dict["collections"][c.title]["mode"] = mode_dict[cast(int, c.collectionMode)]
            collections_dict["collections"][c.title]["sort"] = sort_dict[cast(int, c.collectionSort)]
            collections_dict["collections"][c.title]["items"] = [
                f"{x.title} {x.guid}" for x in cast(list[Union[Movie, Show]], c.items())
            ]

        os.makedirs("./config_dump", exist_ok=True)
        config_file = Path(f'./config_dump/{library[0].replace(" ", "_")}_collections.yml')
        with open(config_file.as_posix(), "w", encoding="utf-8") as f:
            yaml.dump(collections_dict, f)
    return config_file.parent.resolve()

def dump_libraries(plex_libraries: dict[str, LibrarySection], all_fields: bool = False) -> Path:
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
            # # lib_dict: dict[
            # #     str, dict[  # library name title/header
            # #         str, dict[  # each named video
            # #             str, Union[str, list[str]]]]  # that video's fields
            # # ] = {}
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
            # #             'label': [
            # #                 'label1',
            # #                 'label2'
            # #             ],
            # #             'collection': [
            # #                 'collection1',
            # #                 'collection2',
            # #             ]
            # #         },
            # #         'title2 guid2': {}
            # #     }
            # # }

            # lib_dict: dict[str, dict[str, dict[str, Union[str, list[str]]]]] = {}
            lib_dict = {}
            lib_dict[library[0]] = {}
            for item in tqdm(
                library[1].all(),
                total=library[1].totalSize,
                ascii=" ░▒█",
                ncols=100,
                desc=library[0],
                unit=library[1].type
            ):
                item = cast(Union[Movie, Show], item)
                title = f"{item.title} {item.guid}"
                lib_dict[library[0]][title] = {}

                used_fields = [
                    "titleSort",
                    "originalTitle",
                    "contentRating",
                    "year",
                    "studio",
                    "originallyAvailableAt",
                    "summary"
                ]
                used_multi_fields = ["genre", "label", "collection"]

                for field in cast(list[Field], item.fields):
                    field.name = cast(str, field.name)
                    if field.name in used_fields:
                        lib_dict[library[0]][title][field.name] = getattr(item, field.name)
                    if field.name in used_multi_fields:
                        lib_dict[library[0]][title][field.name] = [x.tag for x in getattr(item, field.name+"s")]

        else: # Just a list of movie/show titles and guids
            lib_dict = {}
            # # lib_dict: dict[str, list[str]]
            # # lib_dicts = {
            # #     'library': [
            # #         'title1 guid1',
            # #         'title2 guid2'
            # #     ]
            # # }
            lib_dict[library[0]] = [
                f"{x.title} {x.guid}" for x in tqdm(
                    cast(list[Union[Movie, Show]], library[1].all()),
                    total=library[1].totalSize,
                    ascii=" ░▒█",
                    ncols=100,
                    desc=library[0],
                    unit=library[1].type
                )
            ]

        os.makedirs("./library_dump", exist_ok=True)
        library_dump_file = Path(
            f'./library_dump/{library[0].replace(" ", "_")}{"_(all_fields)" if all_fields else ""}.yml'
        )
        with open(library_dump_file.as_posix(), "w", encoding="utf-8") as f:
            yaml.dump(lib_dict, f)
    return library_dump_file.parent.resolve()


if __name__ == "__main__":
    import argparse
    from plex_connection import PlexConnection

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a", "--all-fields", action="store_true", help="include all fields when dumping libraries"
    )
    args = parser.parse_args()

    print("Loading Plex config...")
    plex = PlexConnection()
    plex_libs = plex.get_libraries()

    print("Found Plex libraries: ", end="")
    print(*plex_libs.keys(), sep=", ")

    print("\nDumping existing collections to file...")
    stem = dump_collections(plex_libraries=plex_libs)
    print(f'Complete. YAML files at "{stem}".')

    print("\nDumping existing library items to file...")
    stem = dump_libraries(plex_libraries=plex_libs, all_fields=args.all_fields)
    print(f'Complete. YAML files at "{stem}".')
