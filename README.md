# ⚜️ ResuResQ

> **Luxury-Tier Retrieval-Augmented Generation (RAG) for Talent Acquisition.**

ResuResQ is a high-performance, AI-driven resume screening engine designed to bridge the gap between semantic candidate capabilities and stringent technical requirements. Engineered with a premium "Gold & White" aesthetic, the platform abstracts the complexity of vector mathematics into a seamless, lightning-fast recruiter experience. 

Built with scalability and precision in mind, ResuResQ parses, embeds, and ranks candidate profiles using state-of-the-art NLP models, ensuring that the best talent is never lost in keyword-filtering black holes.

---

## 🏗️ System Architecture & Data Pipelines

### 1. Data Ingestion & Processing Pipeline
This offline "Full Burn" process converts raw PDFs into highly-optimized hybrid search indices.

```text
=====================================================================================
                    resumeRES-Q : DATA INGESTION PIPELINE
=====================================================================================

[ 📂 data/raw_resumes_clean/ ]  <-- 650 PDF Resumes
              |
              v
+-----------------------------------+
| 1. PARSER (resume_parser.py)      |  • Tool: pdfplumber
|-----------------------------------|  • Logic: Rule-based Regex 
| Extract: Name, Skills, Exp, Proj  |  • LLM Fallback: DISABLED (Deterministic)
+-----------------------------------+
              |
              v
+-----------------------------------+
| 2. CHUNKER (section_chunker.py)   |  • Target: 8 - 16 chunks/resume
|-----------------------------------|  • Result: ~14.2 chunks/resume
| Split by logical bullets/sections |  • Word Cap: 400 words per chunk
| Aggressive Mode: Triggered        |  • Total Chunks Generated: 9,229
+-----------------------------------+
              |
              v
+-----------------------------------+
| 3. EMBEDDER (embedder.py)         |  • Model: all-MiniLM-L6-v2
|-----------------------------------|  • Dimensions: 384
| Vectorize semantic meaning        |  • Batch Size: 32 (Hardware optimized)
| via sentence-transformers         |  • Compute Time: ~46.5 seconds
+-----------------------------------+
              |
       .------+------. (Dual Indexing)
       |             |
       v             v
+--------------+ +--------------+
|   ChromaDB   | |  BM25 Index  |
| (Semantic)   | |  (Keyword)   |
|--------------| |--------------|
| data/chroma/ | | data/bm25/   |
| Count: 9,229 | | Count: 9,229 |
+--------------+ +--------------+
```

### 2. Azure Cloud Architecture
How the deployed application handles a user's search request in real-time.

```text
=====================================================================================
                      resumeRES-Q : AZURE CLOUD ARCHITECTURE
=====================================================================================

                         [ 👤 Recruiter / User ]
                                    |
                                    | (HTTPS: resuresq.app)
                                    v
+===================================================================================+
|                              MICROSOFT AZURE CLOUD                                |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | GitHub Actions CI/CD pipeline pushes images to Azure Container Registry     |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  [ 🖥️ FRONTEND SERVICE ]                            [ ⚙️ BACKEND SERVICE ]        |
|  Container: React + Vite + Nginx                  Container: FastAPI + Uvicorn    |
|  Port: 80 / 443                                   Port: 8000                      |
|  -------------------------------                  ------------------------------  |
|  • SearchHeader (UI)             ==== POST ====>  • @app.post("/api/search")      |
|  • CandidateCard (UI)            <=== JSON ====   • CORS: resuresq.app allowed    |
|  • ThemeContext (Dark/Light)                      • search_service.py (Engine)    |
|                                                                |                  |
+================================================================|==================+
                                                                 |
                   .---------------------------------------------'
                   |
                   v
+-----------------------------------+
| 🧠 HYBRID SEARCH ENGINE (RRF)     |
|-----------------------------------|
| 1. Query: "Java Developer"        |
| 2. Embed Query (all-MiniLM-L6-v2) |
+-----------------------------------+
          |                 |
          v                 v
   [ ChromaDB ]         [ BM25 ]
   Semantic Top 50      Keyword Top 50
          \                 /
           \               /
            v             v
+-----------------------------------+
| 🧮 RECIPROCAL RANK FUSION (RRF)   |
|-----------------------------------|
| Formula: 1 / (k + rank), k=60     |
| Aggregates by candidate_id        |
| Extracts top 3 Highlights         |
+-----------------------------------+
                   |
                   v
          Returns Top N JSON
    (Ranked Candidates + Evidence)
```

---

## 🛠️ Technology Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | React (Vite), Tailwind CSS | Lightning-fast rendering with a luxury "Gold & White" UI. |
| **Backend** | FastAPI (Python), Uvicorn | High-throughput, asynchronous API bridging the ML models. |
| **Embedding Engine**| `sentence-transformers` | Generating 384-dimensional dense vectors (`all-MiniLM-L6-v2`). |
| **Vector Database** | ChromaDB & rank_bm25 | Hybrid retrieval combining semantic search and lexical matching. |
| **Infrastructure** | Azure Container Apps, ACR | Serverless container orchestration with 1 min-replica for 0 cold-starts. |
| **Networking** | Cloudflare WAF, Azure SSL | Custom domain routing (Name.com) with enterprise-grade edge security. |

---

## 🧮 Mathematical Grounding

### Cosine Similarity
At the core of the semantic retrieval engine, ResuResQ calculates the orientation between the recruiter's search query vector ($A$) and the candidate's resume chunk vector ($B$). Candidates are ranked based on the Cosine Similarity formula:

$$ S_c = \frac{A \cdot B}{\|A\| \|B\|} $$

By measuring the cosine of the angle between these high-dimensional vectors, the system guarantees that conceptually similar phrases (e.g., "Machine Learning" and "Predictive Modeling") yield high match scores, even if the exact keywords differ.

### Reciprocal Rank Fusion (RRF)
To perfectly balance Exact Keyword matches (BM25) against Semantic Meaning (ChromaDB), the engine aggregates candidate ranks using RRF:

$$ \text{Score}(d) = \sum_{r \in R} \frac{1}{k + r(d)} $$

*(Where $k=60$ acts as the smoothing constant, ensuring top-tier candidates in both lists receive exponential priority boosts).*

---

## 🚀 Deployment & CI/CD

The application is deployed via a fully automated **GitHub Actions** pipeline targeting **Azure Container Apps**.

### Workflow Highlights
* **Free Disk Space Optimization**: Because ML models and build environments are heavy, the CI pipeline utilizes a pre-build cleanup step to free up runner disk space, ensuring that large Docker contexts don't fail mid-build.
* **Azure Container Registry (ACR)**: Docker images are tagged and pushed securely to `[REGISTRY_URL]`.
* **Zero Cold Starts**: Azure Container Apps is configured with `minReplicas: 1` to ensure the massive NLP models remain loaded in memory, providing instant API responses to the frontend.

### Network Topology
Traffic is routed from the custom domain (managed via Name.com) through **Cloudflare's WAF** to filter out malicious payloads. The traffic securely terminates at the Azure Environment IP (`[AZURE_ENVIRONMENT_IP]`), where Azure Managed SSL encrypts the handshake between the client and the FastAPI containers.

---

## 🗺️ Feature Roadmap (The Backburner)

Continuous iteration is critical. The following features are actively in development:

- [ ] **Full Resume Mapping**: Implementing an integrated PDF viewer that maps the retrieved semantic chunks directly to their visual coordinates on the original document.
- [ ] **High-Precision Match Score Overhaul**: Recalibrating the RRF and Cosine normalization logic to completely eliminate the "0% match" anomaly on partial matches.
- [ ] **Luxury UI Enhancements**: Pushing the frontend aesthetic further with deep dark-gold typography, textured white-paper backgrounds, and running gradient border animations on candidate cards.
- [ ] **Professional Footer & Explainer Page**: Adding a dedicated technical breakdown page and a polished footer to showcase the architecture to technical recruiters and engineers.

---
*Engineered by a Top-Tier Enthusiast*
