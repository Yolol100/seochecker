# Algemene SEO-richtlijnen voor content, media en publicatiestatus

Deze reference bevat herbruikbare regels voor contentproductie, interne linking, taxonomie, afbeeldingen en publicatiecontrole. De regels zijn generiek en mogen niet worden vertaald naar vaste keyword-, link- of categoriequota.

## 1. Afbeeldingen en media

### Bestandsnaam

- Gebruik een korte, beschrijvende bestandsnaam die de zichtbare inhoud of het onderwerp begrijpelijk maakt.
- Gebruik geen generieke exportnaam wanneer een duidelijke inhoudelijke naam beschikbaar is.
- Maak van een bestandsnaam geen keywordlijst.
- Voeg geen merk-, product- of medicijnidentiteit toe wanneer de afbeelding dat niet aantoonbaar toont.

### Alt-tekst

- Beschrijf primair wat daadwerkelijk zichtbaar en functioneel relevant is.
- Gebruik een belangrijke zoekterm alleen wanneer die natuurlijk samenvalt met wat zichtbaar is en de context van de afbeelding.
- Verzin geen object, merk, product, persoon, diagnose, behandeling of andere eigenschap die niet uit de afbeelding of geverifieerde context blijkt.
- Vermijd keyword stuffing en herhaling van omringende tekst.
- Voor puur decoratieve afbeeldingen kan een lege alt-waarde correcter zijn dan geforceerde SEO-tekst.

### Titel, bijschrift en beschrijving

- Behandel mediatitel, bijschrift en beschrijving als afzonderlijke velden met een eigen functie.
- Een bijschrift moet de gebruiker extra context geven; voeg het niet alleen toe voor een SEO-plugincheck.
- Een beschrijving mag context geven, maar mag niet suggereren dat een generiek stockbeeld een specifiek product of geneesmiddel afbeeldt wanneer dat niet is geverifieerd.
- Controleer altijd welke metadata daadwerkelijk in de gerenderde pagina terechtkomt. Een gevuld CMS-veld is geen bewijs dat zoekmachines of gebruikers die tekst te zien krijgen.

### Preferred/featured image

- Controleer na publicatie welke afbeelding daadwerkelijk als featured/preferred image wordt gebruikt.
- Controleer waar relevant ook `og:image` en afbeeldingsinformatie in structured data.
- Een correct ingevulde mediabibliotheek bewijst niet dat de juiste afbeelding live aan de juiste URL is gekoppeld.

## 2. Veilige automatische mediakoppeling

Automatisering die media aan content koppelt moet fail-closed werken.

- Identificeer het doel bij voorkeur met een stabiele unieke identifier, zoals post-ID of exacte canonical slug.
- Gebruik geen fuzzy titelzoekopdracht als primaire write-route wanneer meerdere vergelijkbare pagina's kunnen bestaan.
- Als geen exact doel wordt gevonden: niet schrijven, niet gokken, fout loggen of terugrapporteren.
- Controleer vóór de write dat het doel het verwachte contenttype heeft.
- Koppel pas daarna attachment-parent, metadata of featured image.
- Een automatische write is pas `complete` na een post-write controle op de uiteindelijke live of staging-output.

## 3. Interne linking voor contentclusters

- Maak eerst een bron -> doel linkmatrix.
- Forceer geen all-to-all linking binnen een artikelreeks.
- Link siblings alleen wanneer de onderwerpen of gebruikersvragen werkelijk op elkaar aansluiten.
- Gebruik hubs of categorie-/onderwerppagina's wanneer die een nuttige navigatiefunctie hebben.
- Link niet naar dezelfde URL als de bronpagina.
- Gebruik korte, beschrijvende anchors die grammaticaal in de zin passen.
- Vermijd `klik hier`, kunstmatige exact-match anchors en een vast linkquotum.
- Verifieer doel-URL, statuscode en redirectgedrag wanneer live toegang beschikbaar is.

## 4. Taxonomie en categorieën

- Maak geen nieuwe categorie puur omdat één nieuw artikel een onderwerp behandelt.
- Gebruik een bestaande passende categorie wanneer die de navigatie en contentarchitectuur logisch ondersteunt.
- Maak een aparte categorie of hub pas wanneer die een zelfstandige gebruikers- of beheerfunctie heeft en voldoende unieke inhoud kan bundelen.
- Gebruik geen willekeurige minimumaantallen artikelen als Google-regel.
- Voorkom dunne, vrijwel lege categorie-archieven en meerdere bijna identieke taxonomieën zonder duidelijke functie.

## 5. Publicatiestatus en evidence-transitie

Een statuswijziging verandert welke evidence nog geldig is.

Voorbeeld:

`draft -> staging -> reported_live -> production_verified`

Regels:

- Een eerdere draft- of stagingcontrole bewijst niet dat dezelfde content correct live staat.
- Wanneer iemand meldt dat content live staat, mag dat als `reported_live` worden vastgelegd.
- Claim `production_verified` alleen na passende live observatie van de relevante URL's.
- Hercontroleer minimaal wijzigingsrelevante onderdelen zoals HTTP-status, final URL, robots/indexability, canonical, sitemap, rendered metadata, links en media.
- Oude evidence blijft nuttig als historie, maar mag niet stil als actuele live evidence worden hergebruikt.

## 6. Pluginchecks

- Yoast, Rank Math en vergelijkbare plugins zijn redactionele hulpmiddelen, geen Google-score.
- Controleer versie en analysetaal wanneer exacte plugin-compliance onderdeel van de opdracht is.
- Maak van keyword-density-, transition-word-, passive-voice- of vergelijkbare plugindrempels geen algemene rankingregels.
- Los een pluginmelding niet op met irrelevante tekst, links of keywordherhaling.

## 7. Evidencegrens

- CMS-configuratie of een importbestand bewijst wat bedoeld of ingesteld is, niet noodzakelijk wat live wordt gerenderd.
- Een code-snippet bewijst implementatie-intentie, niet dat de juiste write daadwerkelijk heeft plaatsgevonden.
- Een succesvolle upload bewijst niet dat de juiste afbeelding aan de juiste pagina gekoppeld is.
- Een live HTTP/read-only controle bewijst de waargenomen output op dat moment, maar niet automatisch ranking, indexatie, verkeer of conversie.
- Gebruik Search Console voor Google's owned index-/Search-performance-evidence wanneer beschikbaar.
