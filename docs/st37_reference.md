# AER ST37 guide review

Reference: user-supplied `ST37_ReferenceGuide.pdf`, June 2026 edition, four pages. SHA-256: `2c00ed79d0c4fee94e92be0727b7d8a1af9675c045203c730deddbc868255c2d`. Text was read from all four pages; page 1 was also rendered to verify the duplicated coordinate label. The PDF is reference material, not a source-data sample or permission to enable an ingestion entry. It is not redistributed in Git.

## Documented layers and grain

| Page | Name printed in the guide | Documented meaning / useful fields |
|---|---|---|
| 1 | `ST37_Botton_Hole_NAD83_10TM_AEP_Forest` | Bottom-hole wells; `Well_UWI`, `Well_Licence_Number`, `Well_Name`, `Licensee`, `Licence_Status` and dates/depths. The printed name uses “Botton”; inspect the file's actual name. |
| 2 | `ST37_Production_String_NAD83_10TM_AEP_Forest` | Production strings; `Prod_String_UWI`, `Well_UWI`, `Well_Licence_Number`, field/pool codes, fluid/mode/type/structure, confidentiality and licence attributes. This layer is not monthly production volumes. |
| 3 | `ST37_Surface_Hole_NAD83_10TM_AEP_Forest` | Surface holes; `Well_Licence_Number`, `Licensee`, `Licence_Status`, `Licence_Surface_Location_Label`, `SH_Actual_Latitude`, `SH_Actual_Longitude`, dates/elevation. The listed attributes do not include a UWI. |
| 4 | `ST37_Well_Geometry_NAD83_10TM_AEP_Forest` | Geometry connecting surface and bottom holes; `Well_Licence_Number`, `UWI_Label`, `Well_Geometry_Source`, depth/elevation/length attributes. It is not the default point location for surface-site screening. |

For this reclamation/site-proximity project, the proposed location grain is the surface hole. Confirm its suitability and uniqueness in actual records before finalizing the source configuration. Bottom-hole or production-string positions answer different spatial questions; they must not be silently substituted for surface locations.

## Candidate surface-hole mapping

The following comes from the guide, not an inspected geodatabase:

| Internal field | Candidate source field | Required verification |
|---|---|---|
| `source_well_id` | `Well_Licence_Number` | Establish surface-hole record grain and uniqueness; retain as text. |
| `licensee_name` | `Licensee` | Licensee is not automatically operator or producer. |
| `lsd_text` | `Licence_Surface_Location_Label` | Preserve the publisher's legal-location label. |
| `status` | `Licence_Status` | This is licence status, not an inferred operational/production status. |
| `uwi_if_available` | No listed field | Keep unavailable unless a separately inspected, defensible crosswalk supplies it. Never substitute a licence number for UWI. |

The names suggest NAD83 / 10-TM AEP Forest, but the actual layer CRS must be read and compared with verified source metadata before assigning EPSG:3400. Latitude/longitude columns do not establish their datum on their own. The guide's bottom-hole attribute table repeats `BH_Latitude` twice; it does not justify inventing a longitude column. The PDF alone does not prove actual field types, geometry type, unique keys, source extent, current availability or use terms.

## Production linking and input size

Keep well licence, well UWI, production-string UWI and Petrinex well/facility IDs distinct. The user has excluded Petrinex and monthly volumes from the current scope, so no production crosswalk or additional Petrinex report is required. If production is reconsidered later, one-to-many events and current versus historical links require explicit treatment; a facility link alone cannot allocate volumes to surface sites.

The user's screenshot lists **Geodatabase ZIP, 1.23 GB**, and **Excel ZIP, 170 MB**. Those are screenshot observations, not independently verified archive sizes/contents. The geodatabase is the preferred candidate spatial package. Excel workbooks are not currently a direct input format; a verified CSV conversion with coordinates/CRS is a separate route. Do not assume the two packages contain the same tables.

The 1.23 GB ZIP exceeds the normal 512 MiB acquisition/inspection cap, and its expanded contents may exceed normal ZIP ingestion limits. The new [regional preparation](regional_extracts.md) command inspects the original directly, reads a capped spatial subset from ZIP/FileGDB, and writes a small zipped GeoPackage with original checksums and scope metadata. Normal app/import limits remain unchanged. The publisher download and two hashing passes still touch the original bytes; changing the study area does not reduce the download itself. Actual layer schema, expanded archive behavior and performance still need validation on the real release.

No actual ST37 records were loaded in this review. See [manual download instructions](download_inputs.md), [runtime input configuration](data_access.md) and [source verification](source_verification.md).
