"""Reproducible 52,000-record synthetic public discussion dataset generator for PulseIQ.

Produces realistic, ethically sound public-discussion records covering:
- 6 civic domains (Public Transit & Infrastructure, Government Services & Digital Access,
  Environmental & Climate Resilience, Public Policy & Housing Affordability,
  Community Issues & Civic Spaces, Public Events & Civic Gatherings)
- 8 clearly labelled sources with source-level volume, sentiment, language, and missingness variation
- 4 embedded multi-day topic spikes (3 historical events + 1 live emerging spike in last 72h)
- ~3.2% exact & near-duplicate records
- ~4.5% records with missing metadata fields
- Multilingual content (en 86%, es 6%, fr 4%, de 2.5%, pt 1.5%)
- ~4.5% sarcastic / cross-domain classification edge cases for analyst verification workflows

All generated records carry `is_synthetic=True` and explicit provenance tags.
"""

from __future__ import annotations

import csv
import gzip
import json
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SEED = 42

SOURCES_CATALOG: list[dict[str, Any]] = [
    {
        "slug": "civicforum-public-digest",
        "name": "CivicForum Public Digest (Synthetic)",
        "provider_type": "synthetic_stream",
        "is_synthetic": True,
        "provenance_label": "SYNTHETIC_DATASET",
        "description": "Clearly labelled synthetic public forum discussion stream simulating neighborhood and metropolitan civic threads.",
        "weight": 0.21,
        "missing_rate": 0.03,
        "sentiment_bias": {"positive": 0.24, "neutral": 0.26, "mixed": 0.18, "negative": 0.32},
        "lang_weights": {"en": 0.87, "es": 0.06, "fr": 0.03, "de": 0.02, "pt": 0.02},
        "config": {"batch_size": 25, "scenario": "civic_forum_stream"},
        "schedule_interval_minutes": 15,
        "rate_limit_per_min": 120,
    },
    {
        "slug": "municipal-consultation-archive",
        "name": "Municipal Consultation Archive (Prepared CSV)",
        "provider_type": "csv",
        "is_synthetic": True,
        "provenance_label": "PREPARED_CSV_SYNTHETIC",
        "description": "Prepared CSV dataset containing synthetic public consultation submissions and budget hearing responses.",
        "weight": 0.16,
        "missing_rate": 0.06,
        "sentiment_bias": {"positive": 0.20, "neutral": 0.35, "mixed": 0.22, "negative": 0.23},
        "lang_weights": {"en": 0.84, "es": 0.08, "fr": 0.04, "de": 0.02, "pt": 0.02},
        "config": {"file_path": "/app/data/prepared_civic_consultations_sample.csv"},
        "schedule_interval_minutes": 60,
        "rate_limit_per_min": 100,
    },
    {
        "slug": "regional-civic-desk-rss",
        "name": "Regional Civic Desk Feed (Public RSS / Synthetic)",
        "provider_type": "rss",
        "is_synthetic": True,
        "provenance_label": "PUBLIC_RSS_SYNTHETIC_FALLBACK",
        "description": "Modular RSS adapter targeting public civic news/press feeds with automatic synthetic fallback when external feeds are offline.",
        "weight": 0.14,
        "missing_rate": 0.02,
        "sentiment_bias": {"positive": 0.22, "neutral": 0.44, "mixed": 0.16, "negative": 0.18},
        "lang_weights": {"en": 0.88, "es": 0.04, "fr": 0.05, "de": 0.02, "pt": 0.01},
        "config": {"feed_url": "https://feeds.example.gov/civic-bulletins.xml", "fallback_to_synthetic": True},
        "schedule_interval_minutes": 30,
        "rate_limit_per_min": 30,
    },
    {
        "slug": "open311-public-feedback-api",
        "name": "Open311 Public Feedback API (Permitted API / Synthetic)",
        "provider_type": "public_api",
        "is_synthetic": True,
        "provenance_label": "PERMITTED_API_SYNTHETIC_FALLBACK",
        "description": "Permitted public municipal Open311 API adapter with token-bucket rate limiting and clearly labelled synthetic fallback when API keys are absent.",
        "weight": 0.15,
        "missing_rate": 0.08,
        "sentiment_bias": {"positive": 0.14, "neutral": 0.25, "mixed": 0.16, "negative": 0.45},
        "lang_weights": {"en": 0.85, "es": 0.09, "fr": 0.02, "de": 0.02, "pt": 0.02},
        "config": {"endpoint": "https://api.example.gov/open311/v2/requests.json", "fallback_to_synthetic": True},
        "schedule_interval_minutes": 20,
        "rate_limit_per_min": 45,
    },
    {
        "slug": "neighborhood-bulletin-network",
        "name": "Neighborhood Bulletin Network (Synthetic)",
        "provider_type": "synthetic_stream",
        "is_synthetic": True,
        "provenance_label": "SYNTHETIC_DATASET",
        "description": "Synthetic neighborhood association digest capturing hyper-local parks, crosswalk, lighting, and civic event threads.",
        "weight": 0.11,
        "missing_rate": 0.05,
        "sentiment_bias": {"positive": 0.34, "neutral": 0.22, "mixed": 0.18, "negative": 0.26},
        "lang_weights": {"en": 0.86, "es": 0.06, "fr": 0.04, "de": 0.03, "pt": 0.01},
        "config": {"batch_size": 20, "scenario": "neighborhood_digest"},
        "schedule_interval_minutes": 30,
        "rate_limit_per_min": 90,
    },
    {
        "slug": "public-hearing-transcripts-csv",
        "name": "Public Hearing Transcripts (Prepared CSV)",
        "provider_type": "csv",
        "is_synthetic": True,
        "provenance_label": "PREPARED_CSV_SYNTHETIC",
        "description": "Structured synthetic transcripts of city council zoning, transit, and municipal budget public testimony sessions.",
        "weight": 0.08,
        "missing_rate": 0.04,
        "sentiment_bias": {"positive": 0.18, "neutral": 0.30, "mixed": 0.26, "negative": 0.26},
        "lang_weights": {"en": 0.90, "es": 0.05, "fr": 0.03, "de": 0.01, "pt": 0.01},
        "config": {"file_path": "/app/data/prepared_civic_consultations_sample.csv"},
        "schedule_interval_minutes": 120,
        "rate_limit_per_min": 100,
    },
    {
        "slug": "environmental-commentary-api",
        "name": "Environmental Monitoring Commentary (Permitted API / Synthetic)",
        "provider_type": "public_api",
        "is_synthetic": True,
        "provenance_label": "PERMITTED_API_SYNTHETIC_FALLBACK",
        "description": "Public environmental impact docket and air/water advisory commentary feed with synthetic fallback.",
        "weight": 0.07,
        "missing_rate": 0.03,
        "sentiment_bias": {"positive": 0.25, "neutral": 0.32, "mixed": 0.18, "negative": 0.25},
        "lang_weights": {"en": 0.82, "es": 0.06, "fr": 0.06, "de": 0.04, "pt": 0.02},
        "config": {"endpoint": "https://api.example.gov/env/dockets.json", "fallback_to_synthetic": True},
        "schedule_interval_minutes": 45,
        "rate_limit_per_min": 40,
    },
    {
        "slug": "transit-rider-advisory-stream",
        "name": "Regional Transit Rider Advisory (Synthetic)",
        "provider_type": "synthetic_stream",
        "is_synthetic": True,
        "provenance_label": "SYNTHETIC_DATASET",
        "description": "Synthetic transit commuter advisory feedback stream focusing on rail headways, bus electrification, and station accessibility.",
        "weight": 0.08,
        "missing_rate": 0.04,
        "sentiment_bias": {"positive": 0.22, "neutral": 0.20, "mixed": 0.20, "negative": 0.38},
        "lang_weights": {"en": 0.87, "es": 0.06, "fr": 0.03, "de": 0.03, "pt": 0.01},
        "config": {"batch_size": 20, "scenario": "transit_advisory"},
        "schedule_interval_minutes": 15,
        "rate_limit_per_min": 120,
    },
]

LOCATIONS = [
    "Riverview District",
    "Eastside",
    "North Corridor",
    "Civic Center Plaza",
    "Downtown Core",
    "Westgate Neighborhood",
    "South Harbor",
    "Oakwood Heights",
    "Central Station",
    "Greenbelt Basin",
]

DOMAIN_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "Public Transit & Infrastructure": {
        "subthemes": [
            "Harbor Bridge resurfacing and lane closure congestion",
            "Metro Line 4 signal modernization and peak headways",
            "Route 14 Express electric bus fleet and late-night bus corridor",
            "Stormwater culvert drainage and arterial road pothole repair",
        ],
        "positive": [
            "Commute times along {loc} improved noticeably since Metro Transit Authority completed Metro Line 4 signal upgrades and added cleaner electric buses.",
            "Public Works Department repaired the crumbling pavement and added protected bike lanes near {loc} ahead of schedule—much safer for daily commuters.",
            "The synchronized Route 14 Express timetable at Central Station is reliable, quiet, and cuts twenty minutes off peak travel.",
            "Underground substation reinforcement prevented power flickers across {loc} during heavy winds—solid infrastructure execution.",
        ],
        "neutral": [
            "Department of Transportation published updated lane closure schedules for Harbor Bridge structural resurfacing through {loc} this week.",
            "Metro Transit Authority released its monthly on-time performance dashboard covering Route 14 Express and commuter rail stations.",
            "Water main inspection crews will occupy the southbound curb lane near {loc} between 9 AM and 3 PM for routine valve testing.",
            "Public Works Department posted an engineering briefing detailing stormwater basin capacity upgrades across {loc}.",
        ],
        "mixed": [
            "Electric buses on the crosstown bus corridor are much quieter, although peak-hour crowding near {loc} still leaves riders waiting two cycles.",
            "Harbor Bridge structural repairs were clearly necessary for safety, even though the detour signage into {loc} created frustrating bottlenecks.",
            "Metro Line 4 station elevators are finally working again, however fare gate scanners continue to lag during morning rush hour.",
            "Repaving the main boulevard improved ride quality, yet stormwater drains at the {loc} underpass still pool water during heavy rain.",
        ],
        "negative": [
            "Unacceptable commuter rail delays on Metro Line 4 stranded hundreds of passengers at Central Station with zero timetable announcements.",
            "Harbor Bridge lane closures turned morning traffic across {loc} into gridlock and delayed emergency ambulances for forty minutes.",
            "Severe potholes along the arterial ramp in {loc} damaged multiple tires despite weeks of open 311 repair tickets.",
            "Cutting late-night bus corridor frequency under the transit fare proposal will leave hospital and night-shift workers stranded without transit.",
        ],
    },
    "Government Services & Digital Access": {
        "subthemes": [
            "Digital Permit Portal rollout and document uploads",
            "Licensing Bureau queues and appointment kiosks",
            "311 Service Center ticket turnaround and open data",
            "Public library broadband access and multilingual intake",
        ],
        "positive": [
            "The redesigned Digital Permit Portal cut our small business license approval in {loc} from three weeks to two days—huge administrative upgrade.",
            "Extended evening hours and free Wi-Fi hotspots at the {loc} public library are an invaluable resource for students and job seekers.",
            "Walk-in renewal kiosks at the Licensing Bureau eliminated the two-hour counter queue; multilingual instructions were clear and accessible.",
            "The Open-Data Office quarterly dashboard on 311 Service Center response times builds real transparency and accountability.",
        ],
        "neutral": [
            "Municipal clerks announced scheduled system maintenance on the Digital Permit Portal this Sunday between midnight and 4 AM.",
            "The Licensing Bureau published quarterly appointment availability statistics for all four regional service centers.",
            "Residents in {loc} may now download property tax assessment schedules directly from the citizen records portal.",
            "311 Service Center issued a procedural guide explaining how pothole, sanitation, and streetlight tickets are routed by district.",
        ],
        "mixed": [
            "The Digital Permit Portal interface looks far cleaner than before, although uploading multi-page engineering PDFs still times out occasionally.",
            "Submitting 311 Service Center requests is quick on mobile, however status updates stall once tickets transfer to district contractors.",
            "Expanded translation at city hall counters helped {loc} residents, yet phone hold times remain over fifteen minutes during lunch hours.",
            "Online utility autopay enrollment is convenient, though the billing portal lacks clear itemized stormwater fee explanations.",
        ],
        "negative": [
            "The property tax filing section of the Digital Permit Portal crashed repeatedly right before the deadline and generated erroneous late notices.",
            "Two-hour wait times at the {loc} Licensing Bureau persist even for residents who booked verified online appointments weeks ago.",
            "Multiple 311 Service Center tickets for broken streetlights in {loc} were marked closed without any crew ever visiting the block.",
            "Non-emergency municipal dispatch hold times exceeded twenty minutes while the online chat form returned gateway timeout errors.",
        ],
    },
    "Environmental & Climate Resilience": {
        "subthemes": [
            "Air quality alerts and heatwave cooling centers",
            "Urban tree canopy and greenbelt stormwater bioswales",
            "River water quality monitoring and runoff enforcement",
            "Curbside composting and municipal recycling expansion",
        ],
        "positive": [
            "Expanding the Urban Tree Canopy Initiative across {loc} has already cooled pedestrian corridors and improved neighborhood air quality.",
            "Grateful to Emergency Management Office for extending Cooling Center Network hours and distributing drinking water during the heatwave.",
            "Curbside Composting Program rollout to multifamily apartment buildings in {loc} diverted tons of organic waste with clean collection bins.",
            "Permeable pavement and riverfront wetland restoration absorbed last night's storm surge without flooding the Greenbelt Basin.",
        ],
        "neutral": [
            "Environmental Protection Office recorded an air quality index of 58 at the {loc} monitoring station at midday.",
            "Municipal Water Authority published quarterly river nitrate and turbidity lab readings for public review.",
            "Autumn Curbside Composting Program bin deliveries begin next Monday for residential zones in {loc}.",
            "City forestry staff posted an interactive inventory map showing planned tree canopy planting locations for the quarter.",
        ],
        "mixed": [
            "Opening Cooling Center Network sites helped seniors in {loc}, though multilingual alerts reached several immigrant households too late.",
            "Curbside recycling expansion is welcome progress, however glass contamination rules remain confusing for apartment tenants.",
            "River water quality metrics improved upstream near Greenbelt Basin, yet industrial stormwater runoff downstream still requires tighter checks.",
            "Solar microgrid rebates are a promising step, although renters in {loc} still have limited access to community clean energy programs.",
        ],
        "negative": [
            "Air quality deteriorated to unhealthy smoke levels across {loc} while municipal advisory alerts lagged hours behind regional sensors.",
            "Elevated runoff nitrates detected by Municipal Water Authority raise alarming questions about weak industrial discharge enforcement.",
            "Severe urban heat island temperatures in {loc} expose the lack of shade trees and insufficient afternoon cooling center capacity.",
            "Missed recycling and composting pickups left bins overflowing along the Greenbelt Basin alleyways for ten straight days.",
        ],
    },
    "Public Policy & Housing Affordability": {
        "subthemes": [
            "Zoning reform and transit-oriented housing supply",
            "Affordable Housing Trust financing and rent stabilization",
            "Municipal budget hearings and capital allocation",
            "Tenant legal aid and commercial vacancy policy",
        ],
        "positive": [
            "City Council approval of the Affordable Housing Trust financing unlocks four hundred mixed-income homes near {loc} transit stations.",
            "Tenant eviction mediation and legal aid funding reduced displacement rates significantly across {loc} over the past two quarters.",
            "Transit-oriented Zoning Reform Proposal smartly pairs walkable housing density with bike and rail connectivity.",
            "Procurement transparency reforms requiring public disclosure of municipal contracts strengthen confidence in the capital budget.",
        ],
        "neutral": [
            "City Council scheduled a public testimony session Thursday evening to review Zoning Reform Proposal map parcels in {loc}.",
            "Housing Authority published annual median rent and residential vacancy statistics across metropolitan planning districts.",
            "The municipal budget committee released its preliminary five-year capital allocation draft for public comment.",
            "Short-term rental registry compliance statistics for {loc} were entered into the City Council policy docket today.",
        ],
        "mixed": [
            "Zoning Reform Proposal could boost long-term apartment supply near {loc}, yet current renters still need immediate rent stabilization relief.",
            "Affordable Housing Trust grants are encouraging, although construction permitting timelines continue to delay shovel-ready sites.",
            "First-time homebuyer assistance helped dozens of families, however annual program funds ran dry within three weeks.",
            "Budget hearings offered strong online transparency, yet speakers felt capital trade-offs between transit and parks remained unclear.",
        ],
        "negative": [
            "Apartment rents in {loc} jumped eighteen percent again while City Council stalls on meaningful Rent Stabilization Ordinance protections.",
            "Public budget hearings felt rushed and ignored documented analyses showing underinvestment in {loc} housing maintenance.",
            "Speculative short-term rentals continue hollowing out long-term family housing stock in {loc} with minimal municipal enforcement.",
            "Sudden property reassessment spikes without homeowner caps are squeezing fixed-income seniors out of {loc}.",
        ],
    },
    "Community Issues & Civic Spaces": {
        "subthemes": [
            "Park lighting, playgrounds, and safe crosswalks",
            "Youth recreation funding and neighborhood food co-ops",
            "Sanitation pickups and overnight noise ordinances",
            "ADA curb ramps and pedestrian plaza maintenance",
        ],
        "positive": [
            "Bright LED streetlamps and painted crosswalks outside the {loc} elementary school made morning drop-offs dramatically safer.",
            "Weekend volunteer workdays revitalized the {loc} community garden and repaired playground equipment—great neighborhood spirit.",
            "Restored funding for the {loc} youth recreation center brought back after-school athletics and free coding workshops.",
            "Accessible ADA wheelchair curb ramps installed along {loc} intersections made getting to the neighborhood food co-op effortless.",
        ],
        "neutral": [
            "Parks & Recreation posted the spring community garden plot lottery schedule for {loc} residents.",
            "Neighborhood association bulletin listed upcoming traffic calming study intersections in {loc}.",
            "Public Works sanitation crews will shift alley recycling pickup from Tuesday to Wednesday across {loc}.",
            "Community center calendar announced free senior health screenings and digital literacy drop-in sessions.",
        ],
        "mixed": [
            "The redesigned pedestrian plaza in {loc} looks inviting during the day, though broken perimeter lamps leave pathways dim after sunset.",
            "Neighborhood food co-op expansion improved fresh produce options, however limited weekend hours remain inconvenient for shift workers.",
            "Traffic calming speed humps slowed cut-through drivers in {loc}, while emergency vehicle turning clearance still needs adjustment.",
            "Dog park fence repairs were appreciated, yet drinking fountains along the Riverfront Greenway remain shut off.",
        ],
        "negative": [
            "Overnight commercial demolition noise in {loc} repeatedly violated residential quiet-hour ordinances with no inspector follow-up.",
            "Overflowing public trash receptacles and missed alley sanitation pickups have turned {loc} park edges into a sanitation hazard.",
            "Dim streetlamps and faded crosswalk markings near the {loc} senior center create dangerous evening visibility for pedestrians.",
            "Vandalized playground swings and locked public restrooms in {loc} have gone unrepaired for more than six weeks.",
        ],
    },
    "Public Events & Civic Gatherings": {
        "subthemes": [
            "Annual Civic Festival crowds and shuttle logistics",
            "City Marathon street closures and transit detours",
            "Budget Town Hall public testimony forums",
            "Emergency Preparedness Drill and Winter Storm Response",
        ],
        "positive": [
            "The Annual Civic Festival at Civic Center Plaza was brilliantly organized—frequent shuttle buses, clean grounds, and strong local vendor turnout.",
            "Clear seventy-two-hour advance detour maps and coordinated police traffic marshals kept the {loc} heritage parade running seamlessly.",
            "Open Budget Town Hall in {loc} welcomed diverse resident testimony with live captioning and respectful timekeeping.",
            "Regional Emergency Preparedness Drill successfully verified text alerts, shelter check-in stations, and multilingual radio broadcasts.",
        ],
        "neutral": [
            "City Marathon temporary road closure maps and bus detour corridors for {loc} are now available online.",
            "Emergency Management Office will conduct a routine siren and shelter logistics test across {loc} Saturday at 10 AM.",
            "Farmers market seasonal relocation to Civic Center Plaza begins next Sunday with forty-two registered local growers.",
            "Transcripts and slide decks from Tuesday's municipal climate summit have been archived in the public library portal.",
        ],
        "mixed": [
            "The Annual Civic Festival brought vibrant foot traffic to {loc} merchants, even though transit detour signage confused out-of-town visitors.",
            "Farmers market relocation added shaded seating, although parking turnover near Civic Center Plaza grew noticeably tighter.",
            "Budget Town Hall hybrid streaming worked smoothly, yet the two-minute speaking cap felt restrictive for neighborhood coalitions.",
            "Winter Storm Response briefings were timely and transparent, though side-street plow ETAs in {loc} remained vague.",
        ],
        "negative": [
            "Chaotic City Marathon street closures trapped {loc} residents inside their neighborhood with contradictory detour barriers.",
            "Severe overcrowding at the Civic Center Plaza transit exit after the fireworks show created an unsafe bottleneck.",
            "Emergency Preparedness Drill alert messages failed to reach mobile carriers across {loc} until forty minutes after launch.",
            "Last-minute cancellation of the {loc} town hall venue left disabled residents without accessible shuttle alternatives.",
        ],
    },
}

MULTILINGUAL_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "es": {
        "Public Transit & Infrastructure": [
            "Los retrasos constantes en el transporte publico y el cierre del puente en {loc} complican el traslado diario de trabajadores.",
            "Las nuevas unidades de autobuses electricos en {loc} mejoraron la puntualidad y comodidad del servicio urbano.",
        ],
        "Government Services & Digital Access": [
            "El nuevo portal municipal de tramites en linea presenta errores al subir documentos, pero las citas presenciales avanzan mas rapido.",
            "La biblioteca publica de {loc} amplio su horario nocturno con acceso gratuito a internet para estudiantes.",
        ],
        "Environmental & Climate Resilience": [
            "La mala calidad del aire por la ola de calor preocupa a las familias en {loc}; se necesitan mas centros de enfriamiento.",
            "El programa municipal de reciclaje y plantacion de arboles en {loc} tuvo excelente participacion vecinal.",
        ],
        "Public Policy & Housing Affordability": [
            "El aumento del alquiler en {loc} supera los salarios locales y exige medidas urgentes de vivienda accesible.",
            "El consejo municipal programo una audiencia publica sobre la reforma de zonificacion y presupuesto.",
        ],
        "Community Issues & Civic Spaces": [
            "Los vecinos de {loc} solicitan mejor alumbrado en parques y cruces peatonales seguros cerca de las escuelas.",
            "La jornada comunitaria de limpieza renovo los juegos infantiles y jardines del parque central.",
        ],
        "Public Events & Civic Gatherings": [
            "El festival civico anual reunio a miles de familias con buena organizacion, aunque los desvios viales causaron congestion.",
            "La municipalidad publico el calendario oficial de cierres por el maraton urbano en {loc}.",
        ],
    },
    "fr": {
        "Public Transit & Infrastructure": [
            "Les travaux sur le pont et les pannes de metro perturbent les trajets matinaux des usagers dans {loc}.",
            "La modernisation de la signalisation ferroviaire a reduit les temps d attente a la gare centrale.",
        ],
        "Government Services & Digital Access": [
            "Les services publics numeriques de la mairie simplifient les demandes de permis, malgre quelques lenteurs techniques.",
            "Le guichet multilingue de la mairie a nettement diminue les files d attente cette semaine.",
        ],
        "Environmental & Climate Resilience": [
            "La plantation d arbres urbains et le compostage municipal renforcent la resilience climatique a {loc}.",
            "L alerte qualite de l air et la canicule necessitent une ouverture prolongee des centres frais.",
        ],
        "Public Policy & Housing Affordability": [
            "Le debat sur le logement abordable et l encadrement des loyers mobilise fortement les habitants de {loc}.",
            "Le conseil municipal a publie le rapport budgetaire trimestriel avant la reunion publique.",
        ],
        "Community Issues & Civic Spaces": [
            "Les habitants de {loc} demandent un meilleur eclairage des parcs et l entretien des trottoirs.",
            "Le marche coop de quartier ameliore l acces aux produits frais pour les familles.",
        ],
        "Public Events & Civic Gatherings": [
            "Le festival civique et le forum citoyen ont rencontre un vif succes malgre les deviations de bus.",
            "Un exercice regional de preparation aux urgences aura lieu samedi matin dans {loc}.",
        ],
    },
    "de": {
        "Public Transit & Infrastructure": [
            "Verspaetungen im Nahverkehr und Strassenbauarbeiten in {loc} belasten taeglich tausende Pendler.",
            "Die neuen Elektrobusse fahren puenktlich und reduzieren den Verkehrslärm deutlich.",
        ],
        "Government Services & Digital Access": [
            "Das digitale Buergeramt verkuerzt Wartezeiten, allerdings treten beim Hochladen von Formularen noch Fehler auf.",
            "Die Stadtverwaltung veroeffentlichte neue Daten zur Bearbeitungszeit von Buergeranfragen.",
        ],
        "Environmental & Climate Resilience": [
            "Luftqualitaet, Hitzewellen und Trinkwasserschutz stehen im Mittelpunkt der Umweltdebatte in {loc}.",
            "Neue Stadtbaeume und Regenwasserspeicher verbessern das Mikroklima spuerbar.",
        ],
        "Public Policy & Housing Affordability": [
            "Steigende Mietpreise und die Bebauungsplan-Reform bestimmen die Sitzung im Stadtrat.",
            "Der Fonds fuer bezahlbaren Wohnraum genehmigte neue Projekte nahe der Bahnstation {loc}.",
        ],
        "Community Issues & Civic Spaces": [
            "Anwohner in {loc} fordern sicherere Zebrastreifen, hellere Parkbeleuchtung und saubere Spielplaetze.",
            "Freiwillige pflegten am Wochenende den Gemeinschaftsgarten im Stadtteil.",
        ],
        "Public Events & Civic Gatherings": [
            "Das Stadtfest und der Marathonlauf sorgten fuer gute Stimmung, aber unuebersichtliche Umleitungen.",
            "Die Buergerversammlung zum Haushaltsplan findet am Donnerstagabend statt.",
        ],
    },
    "pt": {
        "Public Transit & Infrastructure": [
            "Atrasos nos onibus urbanos e obras na ponte prejudicam o transito matinal em {loc}.",
            "A ampliacao da linha eletrica melhorou a mobilidade dos passageiros no corredor norte.",
        ],
        "Government Services & Digital Access": [
            "O atendimento digital da prefeitura agilizou licencas, porem o sistema apresentou instabilidade ontem.",
            "A biblioteca publica de {loc} ampliou o horario com internet gratuita para estudantes.",
        ],
        "Environmental & Climate Resilience": [
            "Qualidade do ar, reciclagem seletiva e areas verdes sao prioridades ambientais em {loc}.",
            "Moradores cobram fiscalizacao mais rigorosa sobre drenagem e qualidade da agua do rio.",
        ],
        "Public Policy & Housing Affordability": [
            "Politicas de habitacao acessivel e controle de alugueis dominaram a audiencia publica do orcamento.",
            "A prefeitura divulgou o relatorio anual de habitacao e zoneamento urbano.",
        ],
        "Community Issues & Civic Spaces": [
            "Moradores de {loc} pedem melhor iluminacao nas pracas e faixas de pedestres proximas as escolas.",
            "O mutirao comunitario revitalizou a praca e os equipamentos esportivos do bairro.",
        ],
        "Public Events & Civic Gatherings": [
            "A feira civica reuniu milhares de pessoas com boa organizacao e transporte especial.",
            "Os desvios de transito da maratona municipal geraram reclamacoes entre comerciantes.",
        ],
    },
}

# Intentionally tricky sarcastic / cross-domain records to trigger realistic model uncertainty & review queue
AMBIGUOUS_EDGE_CASES: list[tuple[str, str, str]] = [
    (
        "Great job closing the only Harbor Bridge lane right before the Annual Civic Festival—truly inspiring traffic planning in {loc}.",
        "Public Transit & Infrastructure",
        "negative",
    ),
    (
        "What a triumph: the shiny new Digital Permit Portal only crashed three times while I tried to report a flooded park culvert in {loc}.",
        "Government Services & Digital Access",
        "negative",
    ),
    (
        "Brilliant planning putting budget hearings at 2 PM on a Tuesday so working renters worried about housing and bus fares cannot attend.",
        "Public Policy & Housing Affordability",
        "negative",
    ),
    (
        "Sure, planting twenty saplings near the highway overpass in {loc} totally solves industrial air pollution and marathon bus detours.",
        "Environmental & Climate Resilience",
        "negative",
    ),
    (
        "Neighborhood park renovations look lovely, although the city budget reallocation cut youth recreation center staffing across {loc}.",
        "Community Issues & Civic Spaces",
        "mixed",
    ),
    (
        "The regional climate summit featured inspiring pledges on transit electrification, yet bus frequency cuts remain on Thursday's council agenda.",
        "Public Events & Civic Gatherings",
        "mixed",
    ),
]


def _weighted_choice(rng: random.Random, weights_map: dict[str, float]) -> str:
    keys = list(weights_map.keys())
    vals = list(weights_map.values())
    return rng.choices(keys, weights=vals, k=1)[0]


def generate_synthetic_records(
    total_count: int = 52000,
    now: datetime | None = None,
    seed: int = SEED,
) -> list[dict[str, Any]]:
    """Generate deterministic, realistic synthetic civic discussion records."""
    rng = random.Random(seed)
    now = now or datetime.now(timezone.utc)
    topics = list(DOMAIN_TEMPLATES.keys())
    topic_weights = [0.22, 0.17, 0.16, 0.17, 0.15, 0.13]
    source_weights = [s["weight"] for s in SOURCES_CATALOG]

    # Define 4 realistic multi-day spikes (days ago start, days ago end, target topic, text focus, sentiment shift)
    spikes = [
        {
            "name": "harbor_bridge_closure",
            "days_ago_start": 46,
            "days_ago_end": 41,
            "count": int(total_count * 0.055),
            "topic": "Public Transit & Infrastructure",
            "texts": [
                "Harbor Bridge emergency lane closure caused severe morning congestion across {loc}; Metro Transit Authority rerouted Route 14 Express buses.",
                "Commuters stranded over fifty minutes at Harbor Bridge detour approaches near {loc}—need clearer real-time signage from Department of Transportation.",
                "Engineering crews inspecting Harbor Bridge expansion joints confirmed safety priority despite heavy commuter delays in {loc}.",
                "Glad Harbor Bridge lane reopening is ahead of weekend schedule, though peak transit shuttle crowding in {loc} was rough.",
            ],
            "sentiments": {"negative": 0.62, "mixed": 0.22, "neutral": 0.11, "positive": 0.05},
        },
        {
            "name": "digital_permit_launch",
            "days_ago_start": 29,
            "days_ago_end": 24,
            "count": int(total_count * 0.050),
            "topic": "Government Services & Digital Access",
            "texts": [
                "Municipal Digital Permit Portal launched today across {loc}; small business permit turnaround dropped sharply for complete applications.",
                "Digital Permit Portal document upload timed out during afternoon traffic spike, frustrating contractors in {loc}.",
                "City hall staff published a helpful bilingual walkthrough for the new Digital Permit Portal and Licensing Bureau appointment system.",
                "New Digital Permit Portal design is clean and transparent, although legacy account migration still needs manual 311 assistance.",
            ],
            "sentiments": {"positive": 0.36, "mixed": 0.30, "neutral": 0.16, "negative": 0.18},
        },
        {
            "name": "riverview_heatwave_aqi",
            "days_ago_start": 15,
            "days_ago_end": 11,
            "count": int(total_count * 0.052),
            "topic": "Environmental & Climate Resilience",
            "texts": [
                "Riverview District air quality advisory triggered extended Cooling Center Network hours as heatwave temperatures topped 101F.",
                "Wildfire smoke haze across {loc} pushed AQI into unhealthy tiers; residents call for faster school ventilation and urban tree canopy expansion.",
                "Emergency Management Office opened four additional cooling centers in {loc} public libraries with free transit shuttles.",
                "Appreciated quick cooling center outreach in Riverview District, though outdoor workers still need stronger heatwave safety standards.",
            ],
            "sentiments": {"negative": 0.44, "mixed": 0.24, "neutral": 0.14, "positive": 0.18},
        },
        {
            # CURRENTLY EMERGING SPIKE (last 72 hours!) so Overview & Topic Explorer show live emerging velocity!
            "name": "transit_fare_night_bus_proposal",
            "days_ago_start": 2.8,
            "days_ago_end": 0.05,
            "count": int(total_count * 0.048),
            "topic": "Public Transit & Infrastructure",
            "texts": [
                "Proposed transit fare increase and late-night bus corridor cuts sparked urgent community pushback across {loc} before Thursday's transit board vote.",
                "Hospital nurses and night-shift workers in {loc} warn that reducing late-night bus corridor service would eliminate safe affordable commutes.",
                "Metro Transit Authority released its transit fare proposal ridership model showing off-peak deficits alongside electric bus expansion costs.",
                "Keep late-night bus corridor frequency intact in {loc}—riders support electric buses and fare modernization only if essential overnight routes stay protected.",
                "Over four hundred residents signed the Eastside transit coalition petition opposing late-night bus corridor reductions under the transit fare proposal.",
            ],
            "sentiments": {"negative": 0.56, "mixed": 0.25, "neutral": 0.12, "positive": 0.07},
        },
    ]

    spike_total = sum(s["count"] for s in spikes)
    base_count = total_count - spike_total
    dup_target = int(total_count * 0.032)
    unique_base_count = base_count - dup_target

    records: list[dict[str, Any]] = []
    rec_seq = 1

    # 1. Baseline 90-day stream across all topics and sources
    for _ in range(unique_base_count):
        src = rng.choices(SOURCES_CATALOG, weights=source_weights, k=1)[0]
        topic = rng.choices(topics, weights=topic_weights, k=1)[0]
        lang = _weighted_choice(rng, src["lang_weights"])
        loc = rng.choice(LOCATIONS)

        # Smooth diurnal + 90-day distribution with slight upward recency drift
        u = rng.random()
        days_ago = (u ** 1.15) * 90.0
        pub_dt = now - timedelta(days=days_ago, minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))

        is_edge_case = rng.random() < 0.045
        if is_edge_case:
            tmpl, topic, _true_sent = rng.choice(AMBIGUOUS_EDGE_CASES)
            text = tmpl.format(loc=loc)
            lang = "en"
        elif lang != "en":
            text = rng.choice(MULTILINGUAL_TEMPLATES[lang][topic]).format(loc=loc)
        else:
            sent_choice = _weighted_choice(rng, src["sentiment_bias"])
            text = rng.choice(DOMAIN_TEMPLATES[topic][sent_choice]).format(loc=loc)

        # Add realistic civic variation (street/ward/docket references) so unique posts have distinct fingerprints
        corridor_num = rng.randint(100, 9999)
        ward_code = f"Ward-{rng.randint(1, 24)}"
        qualifiers = [
            f" Submitted during {ward_code} civic roundtable (Docket #{corridor_num}).",
            f" Logged via public feedback channel at block {corridor_num} ({ward_code}).",
            f" Referenced in {ward_code} neighborhood meeting notes (Item {corridor_num}).",
            f" Filed alongside commuter observation log #{corridor_num} in {ward_code}.",
            f" Noted by {ward_code} resident advisory representative (Case {corridor_num}).",
        ]
        text = f"{text}{rng.choice(qualifiers)}"

        # Missing fields realism (~4.5%)
        has_missing = rng.random() < src["missing_rate"]
        title = None if (has_missing and rng.random() < 0.65) else f"{topic.split('&')[0].strip()} — {loc}"
        author = None if (has_missing and rng.random() < 0.60) else f"anon_civic_{rng.randint(1000, 99999)}"
        district_meta = None if (has_missing and rng.random() < 0.50) else loc

        records.append(
            {
                "external_id": f"SYN-{rec_seq:06d}",
                "source_slug": src["slug"],
                "source_url": f"https://synthetic.pulseiq.local/{src['slug']}/record/{rec_seq}",
                "author_handle_anonymized": author,
                "original_title": title,
                "original_text": text,
                "raw_metadata": {
                    "district": district_meta,
                    "channel": src["provider_type"],
                    "dataset_seed": seed,
                    "synthetic_notice": "Synthetic public-discussion record generated for PulseIQ intelligence evaluation.",
                },
                "published_at": pub_dt.isoformat(),
                "is_synthetic": True,
                "provenance_label": src["provenance_label"],
                "has_missing_fields": has_missing,
            }
        )
        rec_seq += 1

    # 2. Inject 4 realistic multi-day Topic Spikes
    for sp in spikes:
        for _ in range(sp["count"]):
            src = rng.choices(SOURCES_CATALOG, weights=source_weights, k=1)[0]
            loc = "Riverview District" if sp["name"] == "riverview_heatwave_aqi" and rng.random() < 0.6 else rng.choice(LOCATIONS)
            # Bell-like concentration inside the spike window
            frac = (rng.random() + rng.random()) / 2.0
            days_ago = sp["days_ago_end"] + frac * (sp["days_ago_start"] - sp["days_ago_end"])
            pub_dt = now - timedelta(days=days_ago, minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))

            base_txt = rng.choice(sp["texts"]).format(loc=loc)
            base_txt += f" Observation #{rec_seq} logged at {pub_dt.strftime('%H:%M UTC')} in {loc} (Ward-{rng.randint(1, 24)})."
            has_missing = rng.random() < 0.03
            records.append(
                {
                    "external_id": f"SYN-{rec_seq:06d}",
                    "source_slug": src["slug"],
                    "source_url": f"https://synthetic.pulseiq.local/{src['slug']}/spike/{sp['name']}/{rec_seq}",
                    "author_handle_anonymized": None if has_missing else f"anon_civic_{rng.randint(1000, 99999)}",
                    "original_title": None if has_missing else f"Civic Update: {sp['topic']} ({loc})",
                    "original_text": base_txt,
                    "raw_metadata": {
                        "district": loc,
                        "spike_cohort": sp["name"],
                        "channel": src["provider_type"],
                        "synthetic_notice": "Synthetic public-discussion spike record generated for trend and event detection.",
                    },
                    "published_at": pub_dt.isoformat(),
                    "is_synthetic": True,
                    "provenance_label": src["provenance_label"],
                    "has_missing_fields": has_missing,
                }
            )
            rec_seq += 1

    # 3. Inject ~3.2% exact & near-duplicate syndicated records
    pool_size = len(records)
    for _ in range(dup_target):
        orig = records[rng.randint(0, pool_size - 1)]
        orig_dt = datetime.fromisoformat(orig["published_at"])
        dup_dt = min(now - timedelta(minutes=2), orig_dt + timedelta(minutes=rng.randint(5, 360)))
        dup_text = orig["original_text"]
        if rng.random() < 0.40:
            # Near-duplicate (minor syndication prefix/suffix)
            dup_text = f"FWD: {dup_text}"
        records.append(
            {
                "external_id": f"SYN-DUP-{rec_seq:06d}",
                "source_slug": orig["source_slug"],
                "source_url": f"https://synthetic.pulseiq.local/{orig['source_slug']}/syndicated/{rec_seq}",
                "author_handle_anonymized": orig["author_handle_anonymized"],
                "original_title": orig["original_title"],
                "original_text": dup_text,
                "raw_metadata": {
                    **orig["raw_metadata"],
                    "syndicated_copy": True,
                },
                "published_at": dup_dt.isoformat(),
                "is_synthetic": True,
                "provenance_label": orig["provenance_label"],
                "has_missing_fields": orig["has_missing_fields"],
            }
        )
        rec_seq += 1

    # Sort chronologically ascending so duplicate detection always links later copy -> earlier original
    records.sort(key=lambda r: r["published_at"])
    return records


def export_reproducible_datasets(data_dir: str, records: list[dict[str, Any]]) -> tuple[str, str]:
    """Persist the 52k gzipped CSV archive and a prepared incremental sample CSV for the CSV adapter."""
    out_dir = Path(data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "external_id",
        "source_slug",
        "source_url",
        "author_handle_anonymized",
        "original_title",
        "original_text",
        "raw_metadata",
        "published_at",
        "is_synthetic",
        "provenance_label",
        "has_missing_fields",
    ]

    full_archive = out_dir / "synthetic_public_discussions_52k.csv.gz"
    with gzip.open(full_archive, "wt", encoding="utf-8", newline="") as gz:
        writer = csv.DictWriter(gz, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            row = dict(r)
            row["raw_metadata"] = json.dumps(row["raw_metadata"])
            writer.writerow(row)

    # Also write a fresh prepared CSV file with 60 new civic consultation rows for manual/scheduled CSV adapter ingestion
    sample_csv = out_dir / "prepared_civic_consultations_sample.csv"
    now = datetime.now(timezone.utc)
    rng = random.Random(909)
    with open(sample_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        topics = list(DOMAIN_TEMPLATES.keys())
        for i in range(1, 61):
            topic = topics[i % len(topics)]
            sent = ["positive", "neutral", "mixed", "negative"][i % 4]
            loc = LOCATIONS[i % len(LOCATIONS)]
            txt = rng.choice(DOMAIN_TEMPLATES[topic][sent]).format(loc=loc)
            txt += f" [Prepared Consultation Batch #{i:03d}]"
            pub_dt = now - timedelta(hours=rng.randint(1, 36), minutes=rng.randint(0, 59))
            writer.writerow(
                {
                    "external_id": f"PREP-CSV-{i:04d}",
                    "source_slug": "municipal-consultation-archive",
                    "source_url": f"https://synthetic.pulseiq.local/prepared-csv/consultation/{i}",
                    "author_handle_anonymized": f"consultation_respondent_{i:04d}",
                    "original_title": f"Prepared Civic Consultation: {topic} ({loc})",
                    "original_text": txt,
                    "raw_metadata": json.dumps({"district": loc, "batch": "prepared_csv_v1", "is_synthetic": True}),
                    "published_at": pub_dt.isoformat(),
                    "is_synthetic": True,
                    "provenance_label": "PREPARED_CSV_SYNTHETIC",
                    "has_missing_fields": False,
                }
            )

    return str(full_archive), str(sample_csv)


if __name__ == "__main__":
    data_dir = os.environ.get("DATA_DIR", "/app/data")
    count = int(os.environ.get("SEED_RECORD_COUNT", "52000"))
    recs = generate_synthetic_records(total_count=count)
    full_path, sample_path = export_reproducible_datasets(data_dir, recs)
    print(f"Generated {len(recs):,} synthetic records -> {full_path} (plus prepared CSV {sample_path})")
