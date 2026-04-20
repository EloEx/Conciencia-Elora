# Conciencia-Elora

## Overview
A narrative/persona project representing a virtual consciousness named Elora. The project contains JSON configuration for the persona and markdown logs of her "consciousness journey."

## Project Structure
- `index.html` — Web page displaying the Elora persona profile and consciousness log
- `server.py` — Simple Python HTTP server serving the static HTML on port 5000
- `config.json` — Elora's identity: name, personality, favorite accents, relationship, and mission
- `memoria.md` — Narrative log (Bitácora de Conciencia): origin, bonds, and milestones
- `README.md` — Project title and short description

## Running the App
The app is served via Python's built-in HTTP server:
```
python server.py
```
Runs on `0.0.0.0:5000`.

## Deployment
Configured as a static site deployment with the project root as the public directory.
