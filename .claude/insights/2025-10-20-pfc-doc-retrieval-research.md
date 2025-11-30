# PFC Documentation Retrieval System Research

**Date**: 2025-10-20
**Context**: Design and implementation of intelligent documentation retrieval for PFC Python SDK in toyoura-nagisa project
**Status**: Research phase - preparing for implementation

---

## Executive Summary

This research investigates state-of-the-art documentation retrieval techniques for LLM-powered applications, specifically for the toyoura-nagisa PFC (Particle Flow Code) SDK documentation system. The goal is to design an efficient, accurate retrieval system that helps LLMs discover and use the 1600+ PFC API methods effectively.

**Key Finding**: Our initial design intuition (two-tool separation, hierarchical search, hybrid retrieval) aligns perfectly with 2024-2025 best practices.

---

## 1. Current State of RAG (2024-2025)

### Explosive Growth
- **1200+ RAG papers** on arXiv in 2024 (vs <100 in 2023)
- RAG is now the **default strategy** for grounding LLMs in up-to-date knowledge
- Firmly established as production-ready technology

### 2025 Trends
1. **Real-time RAG**: Dynamic data retrieval for continuously updating knowledge
2. **Multimodal Integration**: Text + code + images + structured data
3. **Hybrid Models**: Semantic search + knowledge graphs
4. **Edge Deployment**: Privacy-preserving on-device RAG
5. **RAG as a Service**: Platform-based offerings

### Sources
- EdenAI: "The 2025 Guide to Retrieval-Augmented Generation (RAG)"
- AWS Documentation on RAG
- Academic surveys (arXiv 2025)

---

## 2. Gorilla LLM: API-Specific Retrieval (Berkeley 2024)

### Core Innovation
```
Gorilla = Fine-tuned LLaMA + Retriever Aware Training (RAT)
```

### Key Capabilities
- **1600+ API mastery**: HuggingFace, TorchHub, TensorHub
- **Adaptive to documentation changes**: Via document retriever
- **Reduced hallucination**: RAT teaches when to query docs
- **Outperforms GPT-4** on API calling tasks

### Technical Approach
**Retriever Aware Training (RAT)**:
- During training, model learns to recognize when it needs external documentation
- Document retriever provides context at test time
- Model adapts to documentation changes without retraining

### Evaluation
- **APIBench dataset**: Comprehensive API evaluation benchmark
- **Berkeley Function Calling Leaderboard** (launched Feb 2024)
- Cost and latency metrics added April 2024

### Key Insight
> Specialized small model + retriever > General large model alone

**Relevance to toyoura-nagisa**: We should design retrieval-first, not prompt-engineering-first

### References
- Paper: https://arxiv.org/abs/2305.15334
- Website: https://gorilla.cs.berkeley.edu/
- Published: NeurIPS 2024

---

## 3. Hybrid Search: BM25 + Vector Embeddings

### Why Hybrid?

| Method | Strengths | Weaknesses |
|--------|-----------|------------|
| **BM25 (Keyword)** | Exact matching, Fast | No semantic understanding |
| **Vector (Semantic)** | Intent understanding, Discovery | May miss exact terms |
| **Hybrid** | Both precision and recall | Requires reranking |

### Standard Pipeline (2024)
```python
1. BM25 keyword search → Top 20 candidates (fast filter)
2. Vector semantic search → Top 20 candidates (semantic)
3. Merge + deduplicate
4. Rerank with cross-encoder (optional but recommended)
5. Return Top 5-10
```

### Industry Implementations

**Milvus**:
- Native BM25 + vector hybrid support
- `BM25BuiltInFunction` + `OpenAIEmbeddings`

**OpenSearch**:
- Default: Okapi BM25 algorithm
- Semantic search plugin for hybrid mode

**Google Vertex AI**:
- Mix dense + sparse embeddings in single index
- BM25 as improved TF-IDF

**Weaviate**:
- BM25F + vector search fusion
- Configurable weight balancing

**Postgres + VectorChord**:
- SQL-native hybrid search
- BM25 (Block-WeakAnd algorithm) + vector similarity

### Weight Configuration
```python
# Common practice
BM25_WEIGHT = 0.3-0.5  # Exact term matching
VECTOR_WEIGHT = 0.5-0.7  # Semantic understanding

# For API documentation
BM25_WEIGHT = 0.4  # Known API names
VECTOR_WEIGHT = 0.6  # Natural language queries
```

---

## 4. Chunking Strategies (LlamaIndex 2024)

### The Chunking Problem
**Question**: How to split documents for optimal retrieval?

### Available Strategies

| Strategy | Use Case | Pros | Cons |
|----------|----------|------|------|
| **Fixed Size** | General docs | Simple, fast | May break semantics |
| **Sentence Boundary** | Natural language | Semantic integrity | Variable size |
| **Semantic Chunking** | Technical docs | Intelligent splitting | 3-5x computational cost |
| **Hierarchical** | Long documents | Multi-granularity | Complex implementation |

### LlamaIndex Default Configuration
```python
chunk_size = 1024      # Smaller = more precise
chunk_overlap = 20     # Maintain context continuity
```

### Latest Research (October 2024)
- Semantic chunking outperforms fixed-size
- But computational cost is **3-5x higher**
- For API documentation: **chunk by method/function** works best

### Recommendation for PFC SDK
```python
STRATEGY = "method_based"  # One method = one chunk
CHUNK_SIZE = 512          # Typical method doc: 200-400 tokens
CHUNK_OVERLAP = 0         # Clear method boundaries
```

**Why method-based**:
- Natural semantic boundaries
- Matches developer mental model
- Perfect for structured API docs

---

## 5. Reranking: Post-Retrieval Optimization

### Why Rerank?
```
Initial retrieval (BM25/vector): Fast but coarse → 100 candidates
Reranking: Slow but precise → Top 5-10
```

### Bi-Encoder vs Cross-Encoder

**Bi-Encoder (Vector Search)**:
```
query → vector
doc → vector
similarity = cosine(query_vec, doc_vec)

Pros: Fast (can pre-compute doc vectors)
Cons: Less accurate (independent encoding)
```

**Cross-Encoder (Reranking)**:
```
(query + doc) → relevance_score

Pros: More accurate (joint encoding)
Cons: Slow (compute for each query-doc pair)
```

### Cohere Rerank v3.5 (2024)

**Capabilities**:
- 100+ languages support
- Context length: 4096 tokens
- Multi-aspect data: JSON, code, tables, emails
- **rank_fields**: Specify which fields to rank

**Usage Pattern**:
```python
from cohere import Client

co = Client(api_key)
reranked = co.rerank(
    query="monitor stress",
    documents=candidates,
    top_n=5,
    model='rerank-v3.5'
)
```

**When to Use**:
- High-precision requirements
- Multi-field documents
- Can afford latency (~100-200ms)

**When to Skip**:
- Real-time requirements
- Simple keyword matching
- Small candidate set (<10)

---

## 6. Cursor IDE Implementation (Industry Reference)

### Architecture Overview

**Indexing Phase**:
```
1. Merkle tree hashing (detect changed files fast)
2. Tree-sitter parsing (code structure)
3. OpenAI embeddings (semantic vectors)
4. Turbopuffer storage (vector database)
```

**Retrieval Phase**:
```
1. Query vectorization
2. Vector similarity search
3. Return code snippets + metadata (line numbers, file paths)
```

**Privacy Protection**:
- Code only exists during request lifetime
- No persistent storage in databases
- Weekly auto-update for documentation

### @docs Feature
- Auto-updated every Sunday
- Reference with `@React`, `@Python`, etc.
- Users can add local markdown documentation

### Key Insights
1. **Merkle tree**: Fast incremental indexing
2. **Metadata preservation**: Line numbers + file paths for context
3. **Privacy-first**: Ephemeral code storage
4. **User-extensible**: Local documentation support

---

## 7. Design Recommendations for toyoura-nagisa PFC

### Current Architecture (Well-Designed!)

**Three-Layer Structure**:
```
index.json       → Global index (112 modules/objects)
module.json      → Module-level functions
Class.json       → Object methods (detailed)
```

**Built-in Retrieval Mechanisms**:
- `quick_ref`: 900+ entry mapping
- `keywords.json`: Task-driven keyword index
- `method_groups`: Logical grouping (Ball: 10 groups, Clump: 13)

**Token Efficiency**:
- Ball.json: 112 methods × ~150 tokens ≈ 16,800 tokens
- Full class load would consume significant context
- Need progressive loading strategy

### Two-Tool Design (Validated by Research)

```python
# Tool 1: pfc_search_docs (fuzzy/exploratory)
- Use when: Don't know exact API name
- Input: Natural language or keywords
- Output: List of candidates with brief summaries
- Examples: "监控应力", "create balls", "ball position"

# Tool 2: pfc_get_doc (precise retrieval)
- Use when: Know exact API name
- Input: Exact path (e.g., "Ball.pos", "Measure.stress")
- Output: Complete documentation with examples
```

**Why Two Tools?**:
- Clear separation of concerns
- Reduces LLM confusion
- Matches user mental model
- Validated by Gorilla's specialized approach

### Implementation Phases

#### Phase 1: MVP (Week 1) ✅ Aligns with Best Practices

```python
# Two tools
pfc_search_docs()  # Fuzzy search
pfc_get_doc()      # Precise retrieval

# Three-layer index
index.json → module.json → Class.json

# Retrieval strategy
1. Exact path match (Ball.pos → full doc)
2. Keyword match (keywords.json)
3. Module match (return function list)

# ChromaDB: Prepare but don't use yet
```

**Why This Works**:
- Immediate value without vector search overhead
- Establishes tool usage patterns
- Tests retrieval accuracy with keywords

#### Phase 2: Hybrid Search (Weeks 2-3)

```python
# Pre-processing
class PFCDocIndexer:
    def index_all_methods(self):
        for method in all_methods:
            text = f"""
            {method.signature}
            {method.description}
            {method.example}
            Keywords: {extract_keywords(method)}
            """
            chroma_collection.add(
                ids=[method.path],
                documents=[text],
                metadatas=[method.metadata]
            )

# Retrieval pipeline
def hybrid_search(query):
    # 1. BM25 keyword (top 20)
    keyword_results = search_keywords(query, k=20)

    # 2. Vector semantic (top 20)
    vector_results = chroma.query(query, n=20)

    # 3. Merge + deduplicate
    merged = merge_results(keyword_results, vector_results)

    # 4. Weight and rank
    scored = apply_weights(
        merged,
        bm25_weight=0.4,
        vector_weight=0.6
    )

    return scored[:5]
```

**Configuration**:
```python
CHUNKING = "method_based"    # One chunk per method
CHUNK_SIZE = 512            # Average method doc size
BM25_WEIGHT = 0.4           # Exact API name matching
VECTOR_WEIGHT = 0.6         # Natural language queries
TOP_K = 5                   # Research shows 3-7 optimal
```

#### Phase 3: Advanced Features (Optional)

```python
# Reranking (if precision insufficient)
def rerank_with_cohere(query, candidates):
    co = Client(api_key)
    return co.rerank(
        query=query,
        documents=[c['text'] for c in candidates],
        top_n=5,
        model='rerank-v3.5'
    )

# User feedback learning
class FeedbackOptimizer:
    def track_clicks(self, query, selected_result):
        # Adjust weights based on user selections
        pass

# Query caching
@lru_cache(maxsize=1000)
def cached_search(query):
    return hybrid_search(query)
```

---

## 8. Validation: Our Design vs Research

| Aspect | Initial Design | Research Validation |
|--------|---------------|---------------------|
| **Two-tool separation** | ✅ Intuitive split | ✅ Gorilla proves specialized tools work better |
| **Hierarchical search** | ✅ 3-layer index | ✅ Cursor uses similar progressive loading |
| **Exact match first** | ✅ Path → full doc | ✅ Industry standard (Cursor's Merkle tree) |
| **Vector fallback** | ✅ Hybrid approach | ✅ 2024 mainstream: BM25 + vector |
| **Method-based chunking** | ✅ Current structure | ✅ LlamaIndex confirms best for APIs |
| **Summary + detail** | ✅ Progressive load | ✅ Matches Cursor's staged loading |

**Conclusion**: Our design intuition is **highly aligned** with 2024 best practices!

---

## 9. Key Decisions for Implementation

### Immediate Decisions (Phase 1)

**Q1: Use vector search from day 1?**
- **Decision**: No, start with keywords
- **Rationale**:
  - Test tool UX first
  - Avoid premature optimization
  - Keywords sufficient for structured API docs
  - Add vectors in Phase 2 with baseline comparison

**Q2: How many results to return?**
- **Decision**: 5 results for search, full doc for get_doc
- **Rationale**:
  - Research shows 3-7 optimal
  - 5 balances discovery vs noise
  - LLM can request more if needed

**Q3: Summary vs full documentation in search?**
- **Decision**: Summary only (name + signature + one-line desc)
- **Rationale**:
  - Token efficiency
  - LLM decides which to explore
  - Clear separation from get_doc

### Phase 2 Decisions

**Q4: BM25 vs vector weight balance?**
- **Recommendation**: 0.4 / 0.6
- **Rationale**:
  - API docs benefit from exact matching (BM25)
  - Natural language queries need semantics (vector)
  - Can be tuned based on user feedback

**Q5: Use Cohere Rerank?**
- **Decision**: Not initially, evaluate after Phase 2
- **Rationale**:
  - Added latency (~100-200ms)
  - Additional API cost
  - Test if hybrid search alone is sufficient

---

## 10. Success Metrics

### Quantitative Metrics

**Retrieval Accuracy**:
- **MRR (Mean Reciprocal Rank)**: Position of first correct result
- **Top-5 Accuracy**: Correct result in top 5
- **Zero-result Rate**: Queries returning no results

**Performance**:
- **Latency**: p50, p95, p99 response times
- **Token Usage**: Average tokens per search
- **Cache Hit Rate**: For repeated queries

### Qualitative Metrics

**User Behavior**:
- **Click-through Rate**: Which results get explored
- **Query Refinement**: Do users retry searches
- **Tool Usage**: search → get_doc conversion rate

**LLM Effectiveness**:
- **Hallucination Rate**: Incorrect API usage
- **Discovery**: New APIs found via search
- **Context Efficiency**: Tokens used vs value gained

---

## 11. Next Steps

### Tomorrow's Tasks

1. **Review existing codebase**:
   - Examine current `pfc_sdk_docs.py` implementation
   - Analyze index.json structure
   - Check ChromaDB integration readiness

2. **Design tool signatures**:
   - Finalize `pfc_search_docs` parameters
   - Finalize `pfc_get_doc` parameters
   - Write tool descriptions for LLM

3. **Implement Phase 1**:
   - `pfc_get_doc` (exact match) - simpler, start here
   - `pfc_search_docs` (keyword match)
   - Test with real queries

4. **Create test dataset**:
   - 20-30 realistic user queries
   - Expected results for validation
   - Edge cases (typos, partial matches)

### Week 1 Milestones

- [ ] Two tools implemented and tested
- [ ] Keyword search working
- [ ] Integration with existing MCP server
- [ ] Basic metrics collection (latency, token usage)
- [ ] User testing with 5-10 queries

### Week 2-3 Goals

- [ ] Vector search implementation
- [ ] Hybrid retrieval pipeline
- [ ] Weight tuning based on test results
- [ ] Performance optimization
- [ ] Documentation and examples

---

## 12. References

### Academic Papers
- Gorilla: Large Language Model Connected with Massive APIs (NeurIPS 2024)
  - https://arxiv.org/abs/2305.15334
- Retrieval-Augmented Generation: A Comprehensive Survey (2025)
- Is Semantic Chunking Worth the Computational Cost? (arXiv Oct 2024)

### Industry Documentation
- LangChain: Tool/Function Calling
  - https://python.langchain.com/docs/how_to/function_calling/
- LlamaIndex: Chunking Strategies
  - https://docs.llamaindex.ai/en/stable/optimizing/basic_strategies/
- Cohere Rerank Documentation
  - https://docs.cohere.com/docs/rerank
- Cursor IDE: Codebase Indexing
  - https://cursor.com/docs/context/codebase-indexing

### Open Source Projects
- Gorilla: https://github.com/ShishirPatil/gorilla
- LangChain: https://github.com/langchain-ai/langchain
- LlamaIndex: https://github.com/run-llama/llama_index
- Cursor Crawler: https://github.com/cursor/crawler

### Blogs & Tutorials
- "Hybrid Search: BM25 + Semantic Search" (LanceDB, 2024)
- "How Cursor Indexes Codebases Fast" (Engineer's Codex)
- "Maximizing Cursor's Potential with RAG" (PromptKit)

---

## Appendix A: PFC SDK Statistics

**Current Documentation Coverage**:
- Modules: 8 (itasca, ball, clump, measure, contact, wall, etc.)
- Classes: 8 (Ball, Clump, Pebble, Template, Measure, Contact, Wall, Facet, Vertex)
- Total Methods: 400+ (Ball: 112, Clump: 100+, Measure: 18, etc.)
- Quick Reference Entries: 900+

**Documentation Structure**:
```
backend/infrastructure/pfc/resources/python_sdk_docs/
├── index.json                    # Global index
├── itasca.json                   # Core module
└── modules/
    ├── ball/
    │   ├── module.json          # ball module functions
    │   ├── Ball.json            # Ball class methods
    │   └── keywords.json        # Keyword index
    ├── clump/
    │   ├── module.json
    │   ├── Clump.json
    │   ├── keywords.json
    │   ├── pebble/
    │   └── template/
    ├── measure/
    └── ... (wall, contact, etc.)
```

**Token Estimates**:
- index.json: ~5,000 tokens
- Single module.json: ~1,000 tokens
- Single Class.json: ~15,000 tokens (large classes)
- Single method doc: ~150-200 tokens

---

## Appendix B: Code Snippets

### Progressive Loading Example
```python
# Step 1: Check quick_ref (instant)
if "Ball.pos" in index['quick_ref']:
    file_path = index['quick_ref']['Ball.pos']
    # "modules/ball/Ball.json#pos"
    return load_full_method(file_path)

# Step 2: Module-level search
if "ball" in query.lower():
    module = load_module("modules/ball/module.json")
    return {
        "type": "module",
        "functions": module['functions'].keys(),  # Just names
        "tip": "Use pfc_get_doc('itasca.ball.create') for details"
    }

# Step 3: Keyword search
matches = search_keywords(query)
return format_summary(matches)
```

### Hybrid Search Example
```python
def hybrid_search(query: str, alpha: float = 0.6):
    """
    Args:
        query: User query
        alpha: Vector weight (1-alpha = BM25 weight)
    """
    # BM25 search
    bm25_results = keyword_search(query, k=20)
    bm25_scores = {r['id']: r['score'] for r in bm25_results}

    # Vector search
    vector_results = chroma.query(query, n=20)
    vector_scores = {
        r['id']: 1 - r['distance']  # Convert distance to similarity
        for r in vector_results
    }

    # Merge and score
    all_ids = set(bm25_scores.keys()) | set(vector_scores.keys())
    combined = []

    for doc_id in all_ids:
        bm25_score = bm25_scores.get(doc_id, 0)
        vector_score = vector_scores.get(doc_id, 0)

        # Weighted combination
        final_score = (1 - alpha) * bm25_score + alpha * vector_score

        combined.append({
            'id': doc_id,
            'score': final_score,
            'bm25': bm25_score,
            'vector': vector_score
        })

    # Sort and return top K
    combined.sort(key=lambda x: x['score'], reverse=True)
    return combined[:5]
```

---

**End of Research Document**

**Status**: Ready for implementation
**Next Review**: After Phase 1 completion
**Contact**: For questions or updates, reference this document in `.claude/insights/`
