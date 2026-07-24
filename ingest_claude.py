
import chromadb
from chromadb.utils import embedding_functions

local_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

chroma_client = chromadb.PersistentClient(path=r"koala_git\koala_vector_db_claude")

collection = chroma_client.get_or_create_collection(
    name="koala_government_data",
    embedding_function=local_ef,
    metadata={"hnsw:space": "cosine"}
)

RAW_DOCUMENTS = [
    {
        "id": "epbc_policy_001",
        "title": "National Recovery Plan for the Koala 2022-2032 - Section 4",
        "text": "The removal of Primary Koala Feed Trees, specifically Eucalyptus tereticornis (Forest Red Gum) and Eucalyptus robusta (Swamp Mahogany), constitutes a Key Threatening Process under Section 18 of the EPBC Act. Any proposed land rezoning or residential development within a 5km radius of a mapped biological corridor must maintain a mandatory 100-meter riparian buffer zone and incorporate nocturnal fauna underpasses to mitigate vehicle strike mortality.",
        "source_type": "policy_legal",
        "authority": "DCCEEW Government Verified"
    },
    {
        "id": "epbc_policy_002",
        "title": "NSW SEPP Koala Habitat Protection Guidelines",
        "text": "Core koala habitat is defined as an area of land with a resident population of koalas, evidenced by breeding females or recent sightings. Developers must submit an approved Koala Plan of Management (KPoM) before clearing permits are granted. Habitat offsets must be legally secured in perpetuity before canopy clearing commences.",
        "source_type": "policy_legal",
        "authority": "NSW State Government"
    },
    {
        "id": "bio_fact_001",
        "title": "Phascolarctos cinereus - Dietary Symbiosis and Digestion",
        "text": "Koalas survive exclusively on eucalyptus leaves, which are fibrous, low in nutrition, and highly toxic to most mammals. They possess a specialized 2-meter-long cecum containing millions of symbiotic bacteria that break down toxic phenolic compounds and tannins. Because digestion requires immense energy, koalas sleep between 18 to 22 hours per day.",
        "source_type": "general_biology",
        "authority": "Peer-Reviewed Ecological Study"
    },
    {
        "id": "bio_fact_002",
        "title": "Koala Anatomical Adaptations for Canopy Life",
        "text": "The koala's front paws feature two opposable thumbs and three fingers, allowing a powerful mechanical grip on smooth eucalyptus branches. As an umbrella species, protecting koala canopy directly preserves micro-habitats for Greater Gliders, Swift Parrots, and native honeyeaters.",
        "source_type": "general_biology",
        "authority": "National Koala Monitoring Program"
    }
]

def ingest_data():
    print("Beginning EPBC & Biological Data Ingestion...")
    for doc in RAW_DOCUMENTS:
        print(f"Indexing: {doc['title']}...")
        collection.upsert(
            ids=[doc["id"]],
            documents=[doc["text"]],
            metadatas=[{
                "title": doc["title"],
                "source_type": doc["source_type"],
                "authority": doc["authority"]
            }]
        )
    print("Ingestion Complete! Vector DB is ready.")

if __name__ == "__main__":
    ingest_data()