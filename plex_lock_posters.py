#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Lock Movie and TV Show posters in Plex libraries.

Author: averageyogi
Requires: plexapi, dotenv, tqdm
"""

from typing import Union

from plexapi.library import LibrarySection
from plexapi.video import Movie, Show
from tqdm import tqdm


def lock_posters(plex_libraries: dict[str, LibrarySection]) -> None:
    """
    Lock all posters and background art.

    Args:
        plex_libraries (dict[str, LibrarySection]): {library name: Plex library object}
    """
    for library in plex_libraries.items():
        item: Union[Movie, Show]
        for item in tqdm(
            library[1].all(),
            total=library[1].totalSize,
            ascii=" ░▒█",
            ncols=100,
            desc=library[0],
            unit=library[1].type
        ):
            item.lockPoster()
            item.lockArt()


if __name__ == "__main__":
    from plex_connection import PlexConnection

    print("Loading Plex config...")
    plex = PlexConnection()
    plex_libs = plex.get_libraries()

    print("Locking posters and background art...")
    lock_posters(plex_libraries=plex_libs)
    print("Art locked.")
