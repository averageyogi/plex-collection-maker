# plex-collection-maker

Create a collection in TV and Movie libraries from a text file list of shows or movies.

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

Create .env file from [.env.example](./.env.example) with Plex credentials (server IP address, api token, and library names).

Public IP is optional if you will only run script locally to the Plex server.

Your Plex token can be found **[here](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)**

## Usage

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
