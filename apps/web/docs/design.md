# DeepSight interface

The visual reference is `linoxbt/cassandra`: its parchment backgrounds, Newsreader display type, Inter body type, JetBrains Mono labels, oxblood actions, and fine editorial rules. DeepSight retains its own identity, astronomy content, routes, and research workflows. The orbital mark and schematic transit illustration are native SVG.

`app/globals.css` defines the shared visual system. Paper is the default; the optional observation palette is persisted locally. Fonts are bundled locally through Fontsource. The navigation drawer includes every research tool and supports keyboard focus containment, Escape, and focus restoration.

The landing illustration is explicitly schematic. The claims board uses API records and supports filtering and search, with distinct loading, failure, empty, and no-match states. Scientific status remains separate from protocol evidence outcomes.

Validate with `npm run build` and `npm run test:browser`. Browser tests mock API responses, so they check UI behavior without submitting transactions or contacting astronomy archives.
