# Offline map dependencies

Leaflet 1.9.4 (BSD-2-Clause) and jQuery 3.7.1 (MIT) are vendored with their upstream licenses. `manifest.json` records source URLs and SHA-256 hashes for the downloaded bytes. Downloads used HTTPS with TLS verification enabled.

`src/ui/map.py` embeds these assets as data URIs, so the Streamlit component and exported map HTML can render geometry and popups offline without third-party CDN calls. The app uses custom DivIcon markers and no image-based layer controls. Leaflet's unused image URLs therefore need no extra downloads. Optional OpenStreetMap tiles still require Internet access, attribution and compliance with tile usage policies.

When updating these dependencies, use upstream package distribution files, retain the licenses, update the hashes and rerun both browser and offline export checks. These are frontend library assets, not environmental datasets.
