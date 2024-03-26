# plex-collection-maker

Create a collection in TV and Movie libraries from a text file list of shows or movies. This allows you to back-up and
easily recreate standard collections in your plex library.

This is an initially manual process to build the collections,
for an automatic builder using external lists see **[PMM](https://github.com/meisnate12/Plex-Meta-Manager)**.

## Setup

<details>
<summary>Virtual environment</summary>

### Create/activate a virtual environment

```bash
# Virtualenv modules installation (Linux/Mac based systems)
python3 -m venv env
source env/bin/activate

# Virtualenv modules installation (Windows based systems)
python -m venv env
.\env\Scripts\activate

# Virtualenv modules installation (Windows based systems if using bash)
python -m venv env
source ./env/Scripts/activate
```

</details>

---
Install dependencies

```bash
pip install -r requirements.txt
```

Create .env file from [.env.example](./.env.example) with Plex credentials
(server IP address, api token, and library names).

Public IP is optional if you will only run script locally to the Plex server.

Your Plex token can be found
**[here](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)**

From the XML information of a library item (the same place the Plex token was found) you can find the Plex GUID of
that specific library item to use for accurate identification. Otherwise, you can use the provided library dumping
command to get a list of the names and GUIDs for all items in the provided libraries.

Create a config.yml file from [config.template.yml](./config.template.yml) with the paths to your individual collection
configuration files. You will have one config.yml file, but you can have as many collection config files as you want
per library. Be aware, if collections in separate files for the same library have the same name, the collection config
in the earlier file will be discarded.

## Usage

Below are examples of collection configuration files. Only the collection title header and items list are necessary to
create a collection, but there are many other options available.

These are the outputs of the dump functions and include the Plex GUID for each item. These are also not necessary, but
should ensure accurate item identification when adding to a collection. IMDB, TMDB, and TVDB GUIDs can also be used for
identification.

---
Sample movie collection config

```yaml
collections:
  Alien:
    items:
    - Alien (Director's Cut) {tmdb-348}
    - Aliens (Special Edition) {tmdb-679}
    - "Alien\xB3 (Assembly Cut) {tmdb-8077}"
    - 'Alien: Resurrection (Special Edition) {tmdb-8078}'
    mode: hide
    sort: alpha
  Halloween H20 Timeline:
    items:
    - Halloween {imdb-tt0077651}
    - Halloween II {imdb-tt0082495}
    - 'Halloween H20: 20 Years Later {imdb-tt0120694}'
    mode: hideItems
    sort: release
    titleSort: Halloween Timeline 1
  Halloween New Timeline:
    items:
    - Halloween plex://movie/5d77682854f42c001f8c2c48
    - Halloween plex://movie/5d776c8796b655001fe33dc7
    - Halloween Kills plex://movie/5e89cf50c3075b00416ee7d5
    - Halloween Ends plex://movie/5e163304ef1040003f24871a
    mode: hideItems
    sort: release
    titleSort: Halloween Timeline 2
```

---
Sample show collection config

```yaml
collections:
  BBC Earth:
    items:
    - The Blue Planet plex://show/5d9c086a2df347001e3b1e5e
    - Planet Earth plex://show/5d9c086b08fddd001f29a1df
    - Life plex://show/5d9c08662192ba001f30ef67
    - Frozen Planet plex://show/5d9c07f9e98e47001eb043cd
    - Planet Earth II plex://show/5d9c080fcb3ffa001f1b1bd2
    - Blue Planet II plex://show/5d9c08e546115600200adba2
    mode: hide
    sort: release
  Peanuts:
    items:
    - Peanuts {tvdb-78225}
    - Peanuts Motion Comics {tvdb-195611}
    - Peanuts (2014) {tvdb-297291}
    - Snoopy in Space {tvdb-367015}
    - The Snoopy Show {tvdb-389478}
    mode: hide
    sort: release
  Star Wars:
    contentRating: TV-14
    items:
    - 'Star Wars: The Clone Wars {tmdb-4194}'
    - 'Star Wars: Tales of the Jedi {tmdb-203085}'
    - 'Star Wars: The Bad Batch {tmdb-105971}'
    - Obi-Wan Kenobi {tmdb-92830}
    - 'Star Wars: Rebels {tmdb-60554}'
    - Andor {tmdb-83867}
    - The Mandalorian {tmdb-82856}
    - The Book of Boba Fett {tmdb-115036}
    - Ahsoka {tmdb-114461}
    - 'Star Wars: Resistance {tmdb-79093}'
    - 'Star Wars: Visions {tmdb-114478}'
    mode: hideItems
    sort: alpha
```

---

To make and/or sync existing collections

```bash
python main.py
```

You can also dump lists of existing collections to file, and exclude collection editing

```bash
python main.py --dump-collections --exclude-edit
```

As well as dump the entire contents of existing existing libraries to file

```bash
python main.py --dump-libraries --all-fields --exclude-edit
```
