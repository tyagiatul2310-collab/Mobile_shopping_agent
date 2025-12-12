# 📱 PhoneGenie - AI-Powered Mobile Shopping Assistant

PhoneGenie is an intelligent Streamlit-based chatbot that helps users find and compare mobile phones using natural language queries. It combines AI-powered intent understanding, vector search for typo correction, and natural language to SQL conversion to provide personalized phone recommendations.

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.9+
- Gemini API Key ([Get it here](https://makersuite.google.com/app/apikey))
- Pinecone API Key ([Get it here](https://www.pinecone.io/))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/tyagiatul2310-collab/Mobile_shopping_agent.git
   cd Mobile_shopping_agent
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv myenv
   source myenv/bin/activate  # On Windows: myenv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   PINECONE_API_KEY=your_pinecone_api_key_here
   ```

5. **Run the application**
   
   The SQLite database will be **automatically created** from the CSV file on first run.
   
   **Note:** Your Pinecone vector index should already be set up. If you need to rebuild it:
   ```python
   from src.services import resources
   resources.vector.build_index()  # Takes ~5-10 minutes
   ```
   ```bash
   streamlit run app.py
   ```

7. **Access the app**
   
   Open your browser and go to: `http://localhost:8501`

---

## 🏗️ Tech Stack & Architecture

### Tech Stack
- **Frontend/UI:** Streamlit (Python-based web framework)
- **LLM:** Google Gemini (gemini-2.0-flash for speed, gemini-2.5-pro for accuracy)
- **Vector Database:** Pinecone (for semantic similarity search)
- **Database:** SQLite (local phone data storage)
- **Embeddings:** Gemini text-embedding-004

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│                      (Streamlit - app.py)                       │
└───────────────┬─────────────────────────────────┬───────────────┘
                │                                 │
        ┌───────▼────────┐                ┌──────▼─────────┐
        │  Query Tab     │                │ Comparison Tab │
        │  (AI Chat)     │                │ (Side-by-Side) │
        └───────┬────────┘                └──────┬─────────┘
                │                                 │
                └────────────┬────────────────────┘
                             │
                    ┌────────▼──────────┐
                    │ Resource Manager  │
                    │   (Singletons)    │
                    └────────┬──────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
  ┌─────▼──────┐    ┌───────▼────────┐   ┌──────▼──────┐
  │ LLM Client │    │ Query Processor│   │  DB Client  │
  │  (Gemini)  │    │  (Orchestrator)│   │  (SQLite)   │
  └─────┬──────┘    └───────┬────────┘   └──────┬──────┘
        │                   │                    │
        │           ┌───────▼────────┐           │
        │           │ Vector Client  │           │
        │           │   (Pinecone)   │           │
        │           └────────────────┘           │
        │                                        │
        └──────────────┬─────────────────────────┘
                       │
              ┌────────▼─────────┐
              │   Config/Prompts │
              │   (Centralized)  │
              └──────────────────┘
```

### Project Structure

```
My_kaarma/
├── app.py                          # Main Streamlit application
├── data/
│   ├── mobiles_india_preprocessed.csv   # Phone dataset
│   └── mobiles_india_preprocessed.db    # SQLite database
├── src/
│   ├── config.py                   # Configuration & constants
│   ├── prompts.py                  # All LLM prompts
│   ├── styles.py                   # CSS styling
│   ├── services/
│   │   ├── llm_client.py          # Gemini API wrapper
│   │   ├── db_client.py           # SQLite operations
│   │   ├── vector_client.py       # Pinecone operations
│   │   ├── query_processor.py     # Query orchestration
│   │   └── resource_manager.py    # Singleton manager
│   ├── tabs/
│   │   ├── query_tab.py           # AI Chat interface
│   │   └── comparison_tab.py      # Phone comparison UI
│   └── utils/
│       └── helpers.py              # Utility functions
├── .env                            # Environment variables
├── .gitignore
├── requirements.txt
└── README.md
```

### Key Components

1. **LLM Client** - Handles all Gemini API interactions:
   - Intent parsing & entity extraction
   - NL-to-SQL generation
   - Result summarization
   - Embedding generation

2. **Query Processor** - Orchestrates the query flow:
   - Applies name corrections using vector search
   - Merges sidebar filters with query constraints
   - Coordinates between LLM, Vector, and DB clients

3. **Vector Client** - Manages semantic search:
   - Stores embeddings of company/model names in Pinecone
   - Finds similar names for typo correction
   - Filters by company for accurate model matching

4. **DB Client** - SQLite database operations:
   - Phone data retrieval
   - Filter-based queries
   - Metadata extraction (companies, price ranges, etc.)

---

## 🧠 Prompt Design & Safety Strategy

### Prompt Engineering Approach

#### 1. **Intent Classification Prompt**
- **Strategy:** Single-step parsing for efficiency
- **Safety:** Explicit task types (`query`, `general_qa`, `refusal`)
- **Design:** JSON-structured output with strict validation
- **Features:**
  - Entity extraction (companies, models)
  - Constraint detection (price, RAM, battery, camera)
  - Priority feature identification (sorting preferences)

#### 2. **NL-to-SQL Prompt**
- **Strategy:** Gemini Pro for higher accuracy
- **Safety:** 
  - Only generates SELECT statements
  - Parameterized queries to prevent SQL injection
  - Case-insensitive LOWER() for robust matching
  - LIMIT 5 hardcoded to prevent large data leaks
- **Design:** 
  - Clear table schema provided
  - Example-driven instruction
  - Multi-company OR logic for comparisons

#### 3. **Summarization Prompt**
- **Strategy:** Gemini Flash for speed
- **Safety:**
  - Zero-hallucination rules
  - Strict data binding to JSON fields
  - No external knowledge allowed
  - Only recommend phones from provided data
- **Design:**
  - Friendly, conversational tone
  - Structured markdown output
  - Direct answers to user questions
  - Actionable recommendations

#### 4. **General QA Prompt**
- **Strategy:** Tech education focused
- **Safety:** Limited to mobile technology topics
- **Design:** Clear, engaging explanations with examples

### Safety Measures

1. **Input Validation**
   - Malicious query detection with `refusal` task type
   - SQL injection prevention via parameterized queries
   - Case-insensitive matching for robustness

2. **Output Grounding**
   - All phone recommendations strictly from database
   - No hallucinated specifications
   - Buy links generated from actual model names

3. **Error Handling**
   - Graceful fallbacks for API failures
   - User-friendly error messages
   - Helpful suggestions when no results found

4. **Rate Limiting**
   - Caching for repeated queries
   - Efficient single LLM call for intent extraction
   - Optimized token usage

---

## ⚠️ Known Limitations

### 1. **API Rate Limits**
- **Issue:** Free tier Gemini has low RPM limits (4-7 requests/min)
- **Impact:** May encounter 429 errors during rapid queries
- **Workaround:** Wait 60 seconds between queries or upgrade to paid tier

### 2. **Dataset Limitations**
- **Issue:** Limited to ~970 phones in preprocessed dataset
- **Impact:** May not have latest 2024/2025 models
- **Workaround:** Update CSV with fresh data and rebuild database

### 3. **Vector Search Accuracy**
- **Issue:** Similarity threshold (0.4) may miss very different typos
- **Impact:** Some misspellings might not auto-correct
- **Workaround:** Users can check spelling or use sidebar filters

### 4. **Query Complexity**
- **Issue:** Very complex multi-condition queries may confuse intent parser
- **Impact:** Might not capture all constraints accurately
- **Workaround:** Break complex queries into simpler ones

### 5. **No Real-Time Pricing**
- **Issue:** Prices are from CSV (launched price), not current market price
- **Impact:** Display prices may be outdated
- **Workaround:** Buy links direct to Amazon/Flipkart for current prices

### 6. **Limited Language Support**
- **Issue:** Optimized for English queries only
- **Impact:** Hindi or regional language queries may not work well
- **Workaround:** Use English for best results

### 7. **Comparison Limit**
- **Issue:** Summary shows max 4 unique phones
- **Impact:** Large result sets are truncated
- **Workaround:** Use more specific queries or filters

### 8. **Cold Start**
- **Issue:** First query after startup is slower
- **Impact:** Initial response delay
- **Workaround:** Expected behavior, subsequent queries are faster

---

## 📊 Features

- ✅ Natural language phone search
- ✅ Intelligent typo correction
- ✅ Side-by-side comparison (up to 4 phones)
- ✅ Smart filters (price, brand, camera, battery)
- ✅ Conversational chat with history
- ✅ Direct Amazon/Flipkart buy links
- ✅ Detailed spec comparisons
- ✅ AI-powered recommendations
- ✅ Query caching for performance

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📝 License

This project is licensed under the MIT License.

---

## 👨‍💻 Author

**Atul Tyagi**
- GitHub: [@tyagiatul2310-collab](https://github.com/tyagiatul2310-collab)

---

## 🙏 Acknowledgments

- Google Gemini for LLM capabilities
- Pinecone for vector search infrastructure
- Streamlit for the amazing web framework
- Mobile phone dataset from Kaggle

---


