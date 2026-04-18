# Columbus OH Import — Already Exists

An import script for Columbus OH already lives at [scripts/import-columbus.mjs](./import-columbus.mjs).

It targets the Columbus ArcGIS MapServer refuse-colordays layer
(`https://maps2.columbus.gov/arcgis/rest/services/Applications/Neighborhood/MapServer/24`)
and imports ~29,000 zone-level records mapping color codes (GOLD/GRAY/NAVY/PINK/RUBY)
and direct day codes (MON–FRI) to weekdays.

This file is a marker so the 14-city batch is traceable: the sprint list included
Columbus OH as city #7, but no new script was written — the existing one is current.
