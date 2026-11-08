# Supplied environmental dataset reference

Source: user-uploaded `Alberta_Environmental_Datasets_Reference_v2.docx`, received 8 November 2026. The source text below is retained as reference material. Publisher/CRS/licence statements have not yet been independently rechecked at acquisition time. The document contains no download URLs, ArcGIS service URLs or layer IDs; those remain to be verified during live-source implementation.

Alberta Oil Well Environmental Screening Project

Dataset and CRS Reference

AIDA 1145 Data Engineering + AIDA 2362 GIS. This document records candidate public datasets for the educational Alberta oil-well environmental screening project. Dataset metadata should be checked again when each source is actually downloaded or queried.

## 1. AER ST37 - List of Wells in Alberta

Publisher: Alberta Energy Regulator (AER)

Project use: Core Alberta well locations and identifiers; useful well attributes will be confirmed after download.

Freshness: ST37 spatial data is listed as updated monthly. Other AER well products include weekly General Well Data and a daily well-licence list.

Licence/use: AER copyright and information-product terms apply. Do not describe this source as Open Government Licence data unless the exact product terms confirm that.

Access: AER spatial-data download, including shapefile products.

CRS: TO VERIFY FROM THE ACTUAL ST37 SHAPEFILE .PRJ/METADATA. We should not infer its CRS from other AER guidance.

Important limits: Verify fields, record count, update date, CRS, completeness and permitted use when acquired.

## 2. Alberta Base Water Feature

Publisher: Government of Alberta

Project use: Distance from wells to lakes, rivers, streams, reservoirs and other selected surface-water features.

Freshness: Live provincial ArcGIS service; component source vintages can vary.

Licence/use: Open Government Licence - Alberta.

Access: ArcGIS REST MapServer; suitable service layers can be queried programmatically.

CRS: EPSG:3400 - NAD83 / Alberta 10-TM (AEP Forest). Units are metres.

Important limits: Compiled from multiple sources/scales; choose appropriate analytical layers.

## 3. Parks and Protected Areas of Alberta

Publisher: Government of Alberta / Alberta Parks

Project use: Distance to or intersection with protected areas.

Freshness: Live provincial ArcGIS FeatureServer; record the access date and dataset metadata when acquired.

Licence/use: Public Government of Alberta GIS service; capture the exact resource-use/licence statement for final documentation.

Access: ArcGIS REST FeatureServer.

CRS: EPSG:3400 - NAD83 / Alberta 10-TM (AEP Forest). Units are metres.

Important limits: GIS boundaries are not the controlling legal descriptions.

## 4. Critical Habitat for Species at Risk - National Dataset

Publisher: Environment and Climate Change Canada / Canadian Wildlife Service

Project use: Distance to or intersection with federally identified critical habitat.

Freshness: Open Government record modified August 4, 2026; maintained as needed.

Licence/use: Open Government Licence - Canada.

Access: Federal open-data download and spatial web services.

CRS: EPSG:3978 - NAD83 / Canada Atlas Lambert.

Important limits: Some sensitive locations are generalized; authoritative recovery documents take precedence. Reproject before metre-based comparison with EPSG:3400 layers.

## 5. Alberta Merged Wetland Inventory

Publisher: Government of Alberta

Project use: Possible wetland proximity/type screening factor.

Freshness: Represents source wetland inventories from approximately 1998-2015.

Licence/use: Service metadata references an older Informatics Branch digital-data licence. Confirm redistribution terms before using it in the web application.

Access: ArcGIS REST MapServer.

CRS: EPSG:3400 - NAD83 / Alberta 10-TM (AEP Forest). Units are metres.

Important limits: Older and generalized merged inventory; source years, methods and accuracy vary.

## 6. Environmentally Significant Areas of Alberta (2014)

Publisher: Government of Alberta

Project use: Optional comparison/validation layer against an existing environmental-significance assessment.

Freshness: 2014 assessment; treat as historical/comparison evidence rather than current conditions.

Licence/use: Confirm exact distribution/use terms from final source metadata before redistribution.

Access: ArcGIS REST MapServer.

CRS: EPSG:3400 - NAD83 / Alberta 10-TM (AEP Forest). Units are metres.

Important limits: Not intended as a regulatory determination and may omit significant areas due to inventory limitations.

## 7. OpenStreetMap

Publisher: OpenStreetMap contributors / OpenStreetMap Foundation

Project use: Interactive basemap for the locally hosted web application. It is not the source of the AER well or government environmental analysis data.

Freshness: Continuously/community maintained; currency varies by place and feature.

Licence/use: Open Database License (ODbL); OpenStreetMap contributor attribution is required.

Access: Web mapping tiles/services subject to applicable usage policies.

CRS: Web map display normally uses EPSG:3857 (Web Mercator).

Important limits: Use EPSG:3857 for display, not for authoritative environmental distance calculations.

## Recommended CRS strategy

- Use a projected CRS measured in metres for spatial analysis and distance calculations.

- EPSG:3400 is a strong candidate for the common Alberta analysis CRS because the Alberta water, parks/protected areas, wetland and ESA services checked for this reference publish in EPSG:3400.

- Transform the federal Critical Habitat data from EPSG:3978 to the selected common analysis CRS before calculating distances or buffers.

- Use OpenStreetMap/Web Mercator (EPSG:3857) for web-map display, not as the authoritative distance-calculation CRS.

- Confirm the AER ST37 CRS directly from its downloaded .prj file before transforming or analyzing the well locations.

## Recommended first-version dataset stack

Start with AER wells, Alberta surface water, Alberta parks/protected areas, and federal critical habitat. Investigate wetlands as a possible additional factor after confirming licence suitability and accepting the age of the inventory. Keep the 2014 ESA layer as an optional comparison/validation dataset.

## Training-project disclaimer

This project is for education and training. Proximity and screening results are not professional environmental-risk determinations and must not be used for operational, regulatory, engineering, reclamation, field, or environmental decisions.
