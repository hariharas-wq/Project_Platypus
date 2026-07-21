"""
build_evidence.py  --  Project Platypus / Team 56
------------------------------------------------------
Builds evidence.json: the verified fact base each ambassador is
grounded in. AI only phrases arguments; the FACTS come from here.

Sources:
  - GBIF Occurrence API (live global sighting counts)
  - IUCN Red List assessments (hand-verified figures, tier-tagged)

Run once before starting the server:
    py build_evidence.py
"""

import json
import sys
import requests

GBIF_MATCH = "https://api.gbif.org/v1/species/match"
GBIF_COUNT = "https://api.gbif.org/v1/occurrence/search"

# --- Species we resolve GBIF occurrence counts for -------------------
GBIF_SPECIES = {
    "great_white_shark": "Carcharodon carcharias",
    "australian_sea_lion": "Neophoca cinerea",
}


def gbif_occurrence_count(scientific_name: str) -> int:
    """Resolve a name to its GBIF taxonKey, then count georeferenced records."""
    try:
        m = requests.get(GBIF_MATCH, params={"name": scientific_name}, timeout=30)
        m.raise_for_status()
        key = m.json().get("usageKey")
        if not key:
            print(f"  ! no taxonKey for {scientific_name}")
            return 0
        c = requests.get(
            GBIF_COUNT,
            params={"taxonKey": key, "hasCoordinate": "true", "limit": 0},
            timeout=30,
        )
        c.raise_for_status()
        return int(c.json().get("count", 0))
    except Exception as e:
        print(f"  ! GBIF error for {scientific_name}: {e}")
        return 0


def build():
    print("Building evidence base...")
    occ = {}
    for slug, name in GBIF_SPECIES.items():
        n = gbif_occurrence_count(name)
        occ[slug] = n
        print(f"  {name}: {n:,} georeferenced sightings")

    evidence = {
        "great_white_shark": {
            "display_name": "Great White Shark",
            "scientific_name": "Carcharodon carcharias",
            "constituency_type": "species",
            "data_status": "data-rich",
            "facts": [
                {
                    "claim": "Listed as Vulnerable on the IUCN Red List.",
                    "source": "IUCN Red List assessment (Carcharodon carcharias)",
                    "tier": 1,
                    "confidence": "high",
                },
                {
                    "claim": "Global population inferred to have declined 30-49% over "
                             "three generations (approx. 159 years).",
                    "source": "IUCN Red List assessment",
                    "tier": 1,
                    "confidence": "high",
                },
                {
                    "claim": "Generation length is approximately 53 years.",
                    "source": "IUCN Red List assessment",
                    "tier": 1,
                    "confidence": "high",
                },
                {
                    "claim": f"{occ.get('great_white_shark', 0):,} georeferenced "
                             "occurrence records held in GBIF.",
                    "source": "GBIF Occurrence API (live)",
                    "tier": 2,
                    "confidence": "high",
                },
                {
                    "claim": "Slow to mature and low fecundity, so populations recover "
                             "slowly from losses to nets and drumlines.",
                    "source": "IUCN Red List assessment (life-history)",
                    "tier": 1,
                    "confidence": "medium",
                },
            ],
        },
        "australian_sea_lion": {
            "display_name": "Australian Sea Lion",
            "scientific_name": "Neophoca cinerea",
            "constituency_type": "species",
            "data_status": "data-rich",
            "facts": [
                {
                    "claim": "Listed as Endangered on the IUCN Red List.",
                    "source": "IUCN Red List assessment (Neophoca cinerea)",
                    "tier": 1,
                    "confidence": "high",
                },
                {
                    "claim": "Endemic to southern and western Australian waters.",
                    "source": "IUCN Red List assessment",
                    "tier": 1,
                    "confidence": "high",
                },
                {
                    "claim": "Highly site-faithful breeding, so localised bycatch can "
                             "wipe out whole sub-colonies.",
                    "source": "IUCN Red List assessment (ecology)",
                    "tier": 1,
                    "confidence": "medium",
                },
                {
                    "claim": f"{occ.get('australian_sea_lion', 0):,} georeferenced "
                             "occurrence records held in GBIF.",
                    "source": "GBIF Occurrence API (live)",
                    "tier": 2,
                    "confidence": "high",
                },
            ],
        },
        "beach_users": {
            "display_name": "Beach Users",
            "scientific_name": None,
            "constituency_type": "community",
            "data_status": "data-poor",
            "facts": [
                {
                    "claim": "Represents swimmers, surfers and coastal tourism who "
                             "value both safety and a living ocean.",
                    "source": "Constituency definition (no primary dataset)",
                    "tier": 4,
                    "confidence": "low",
                },
                {
                    "claim": "Shark-control programs are often justified on public-safety "
                             "grounds, but effectiveness evidence is contested.",
                    "source": "General policy record (no single primary source)",
                    "tier": 3,
                    "confidence": "low",
                },
            ],
        },
    }

    with open("evidence.json", "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)
    print("Wrote evidence.json")


if __name__ == "__main__":
    build()
