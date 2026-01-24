import os
import sys

from dotenv import load_dotenv
import plexapi.exceptions
from plexapi.server import PlexServer
from plexapi.library import LibrarySection
import requests
import yaml


load_dotenv(override=True)  # Take environment variables from .env

class PlexConnection:
    """Connect to Plex libraries."""
    def __init__(self, edit_collections: bool = False):
        """
        Connect to Plex libraries.

        Args:
            edit_collections (bool, optional): If true, load collection config files. If false, skip loading any
                collection configs.
        """
        # print('init')
        self.load_config(edit_collections)
        self.plex_setup()

    def load_config(self, edit_collections: bool) -> None:
        """
        Load environment variables from .env and library configuration from config.yml.

        Args:
            edit_collections (bool, optional): If true, load collection config files. If false, skip loading any
                collection configs.
        """
        # print('starting load_config')
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
            # print(self.plex_ip, self.plex_pub_ip)
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
        self.config_libraries: list[str] = [*config_yaml["libraries"]]

        self.collections_config = {}
        if edit_collections:
            for lib in config_yaml["libraries"]:
                for coll_file in config_yaml["libraries"][lib]["collection_files"]:
                    with open(coll_file["file"], "r", encoding="utf-8") as collection_config_file:
                        try:
                            colls = yaml.safe_load(collection_config_file)
                            if self.collections_config.get(lib):
                                self.collections_config[lib].update(colls["collections"])
                            else:
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

    def print_plex_libraries(self):
        """
        Print libraries found on connected Plex server.
        """
        print("library.sections()  ", sects := self.plex.library.sections())
        # for s in sects:
        #     if isinstance(s, MovieSection):
        #         s:MovieSection
        #         print(s, "  ", s.collections())


    def get_libraries(self) -> dict[str, LibrarySection]:
        """
        Return accessible Plex libraries libraries in config file found on
        connected Plex server.

        Returns:
            dict[str,LibrarySection]: {library name: Plex library object}
        """
        plex_libraries_dict: dict[str, LibrarySection] = {}
        for library in self.config_libraries:
            try:
                plex_libraries_dict[library] = self.plex.library.section(library)
            except plexapi.exceptions.NotFound:
                sys.exit(f'Library named "{library}" not found. Please check the config.yml, and consult the README.')
        return plex_libraries_dict

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

if __name__ == "__main__":
    print("Loading Plex config...")
    pc = PlexConnection(edit_collections=False)

    plex_libraries = pc.get_libraries()

    print("Found Plex libraries: ", end="")
    print(*plex_libraries.keys(), sep=", ")

    pc.print_plex_libraries()
