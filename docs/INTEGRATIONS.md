# Integrations

## Doel

De repository moet altijd bruikbaar blijven zonder externe API-credentials. GSC en Ahrefs zijn optionele evidence-adapters voor de workflow **Full SEO Diagnostic**.

## Google Search Console

### Waarom OAuth in plaats van interactieve login

GitHub Actions heeft geen menselijke browsersessie. De workflow gebruikt daarom een OAuth refresh token dat vooraf één keer wordt verkregen en daarna als encrypted GitHub Actions secret wordt opgeslagen.

### Vereisten

1. Een Google Account met toegang tot de gewenste Search Console property.
2. Een Google Cloud-project.
3. Search Console API geactiveerd in dat project.
4. Een OAuth 2.0 client.
5. Een refresh token met scope:

`https://www.googleapis.com/auth/webmasters.readonly`

6. Deze repository secrets:

- `GSC_CLIENT_ID`
- `GSC_CLIENT_SECRET`
- `GSC_REFRESH_TOKEN`

### Workflow input

`gsc_property` moet exact overeenkomen met de property in Search Console, bijvoorbeeld:

- Domain property: `sc-domain:example.com`
- URL-prefix property: `https://www.example.com/`

### Data die wordt opgehaald

- Search Analytics per datum
- target-country Search Analytics
- top queries in het target country
- top pages in het target country
- URL Inspection voor de opgegeven audit-URL

### Niet beschikbaar via deze adapter

- Handmatige acties
- Beveiligingsproblemen
- live URL-test uit de Search Console UI

Die blijven open evidence en worden expliciet in het eindrapport genoemd.

## Ahrefs

### Vereiste secret

`AHREFS_API_KEY`

De key wordt alleen vanuit GitHub Actions secrets gelezen en nooit naar een artifact geschreven.

### Endpoints

De adapter gebruikt Ahrefs API v3 Site Explorer:

- `backlinks-stats`
- `refdomains-history`
- `anchors`
- `refdomains`

### Interpretatie

- `is_spam` is een Ahrefs-classificatie.
- `first_seen` is Ahrefs discovery-time.
- Anchor/refdomain tabellen worden bewust begrensd tot maximaal 100 rijen voor brede plancompatibiliteit en kostenbeheersing.
- Een backlinkspamsignaal wordt nooit automatisch vertaald naar "Google penalty".

## Zonder API-credentials

De volledige workflow blijft technisch bruikbaar. De GSC- en/of Ahrefs-adapter schrijft dan een JSON-bestand met `status: not_configured`. Het gecombineerde rapport markeert die bewijslaag als open in plaats van data te verzinnen.

## Secret hygiene

Nooit committen:

- client secrets
- refresh tokens
- API keys
- service-account JSON
- klant-specifieke Search Console exports

Gebruik alleen repository/environment secrets of een andere secret store die GitHub Actions op runtime injecteert.
