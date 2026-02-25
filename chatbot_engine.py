# backend/chatbot_engine.py - CONVERTED TO GROQ (FIXED)

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
import re
from datetime import datetime
import os
import traceback
import requests

# Download NLTK data once at module load
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)


class DocumentChatbot:
    """
    Document Q&A System using RAG (Retrieval-Augmented Generation) with Groq API.
    Each document gets its own TF-IDF vectorizer to avoid cross-document contamination.
    """

    def __init__(self, use_llm=True):
        print("\n" + "=" * 50)
        print("🤖 Initializing Document Chatbot (RAG + Groq)...")
        print("=" * 50)

        self.use_llm = use_llm
        self.llm_available = False
        self.api_key = None
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.available_models = []

        # Per-document vectorizers
        self.vectorizers = {}   # doc_id -> TfidfVectorizer (fitted)
        self.doc_chunks = {}    # doc_id -> list[str]
        self.doc_vectors = {}   # doc_id -> sparse matrix
        self.sentence_index = {}  # doc_id -> list[str]
        self.documents = {}     # doc_id -> metadata dict
        self.conversations = {} # doc_id -> list[dict]

        self.stop_words = set(stopwords.words('english'))

        # Try to connect to Groq API
        if use_llm:
            self._init_groq()

        print("✅ Document Chatbot ready!\n")

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_groq(self):
        """Initialise the Groq client."""
        self.api_key = os.environ.get("GROQ_API_KEY", "").strip()
        
        if not self.api_key:
            print("   ⚠️  GROQ_API_KEY not set — falling back to TF-IDF only.")
            print("   📝  Set it with: export GROQ_API_KEY=gsk_your_key_here")
            return

        try:
            # Test connection by listing models
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                models = response.json().get("data", [])
                self.available_models = [m["id"] for m in models]
                self.llm_available = True
                print(f"   ✅ Groq API connected! Available models: {len(self.available_models)}")
                
                # Show recommended models
                recommended = ['mixtral-8x7b-32768', 'llama3-70b-8192', 'llama3-8b-8192']
                available_recs = [m for m in recommended if m in self.available_models]
                if available_recs:
                    print(f"   🚀 Recommended: {', '.join(available_recs[:2])}")
            else:
                print(f"   ⚠️  Groq API error: {response.status_code} — falling back to TF-IDF only.")
                
        except Exception as e:
            print(f"   ⚠️  Groq API unavailable: {e} — falling back to TF-IDF only.")

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_document(self, doc_id: str, text: str, filename: str = "") -> bool:
        """
        Index a document for Q&A retrieval.
        Each document gets its own TF-IDF vectorizer so documents never
        interfere with each other.
        """
        if not text or len(text) < 50:
            return False

        text = re.sub(r'\s+', ' ', text).strip()
        all_sentences = sent_tokenize(text)
        self.sentence_index[doc_id] = all_sentences

        # Build overlapping chunks (window = 4 sentences, step = 2)
        chunks = []
        window, step = 4, 2
        for i in range(0, max(1, len(all_sentences) - window + 1), step):
            chunk = ' '.join(all_sentences[i: i + window])
            if len(chunk.split()) >= 10:
                chunks.append(chunk)

        # Fallback: single sentences if text is very short
        if not chunks:
            chunks = [s for s in all_sentences if len(s.split()) > 5]

        self.doc_chunks[doc_id] = chunks

        # Fit a fresh vectorizer for this document only
        vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=15000,
            ngram_range=(1, 3),
            min_df=1,
            max_df=0.95,
            sublinear_tf=True,
        )
        try:
            vectors = vectorizer.fit_transform(chunks)
            self.vectorizers[doc_id] = vectorizer
            self.doc_vectors[doc_id] = vectors
            print(f"   📚 Indexed {len(chunks)} chunks | {len(all_sentences)} sentences")
        except Exception as e:
            print(f"   ⚠️  Vectorization error: {e}")
            self.vectorizers[doc_id] = None
            self.doc_vectors[doc_id] = None

        self.documents[doc_id] = {
            'id': doc_id,
            'filename': filename,
            'text': text,
            'chunk_count': len(chunks),
            'sentence_count': len(all_sentences),
            'word_count': len(text.split()),
            'indexed_at': datetime.now().isoformat(),
        }

        if doc_id not in self.conversations:
            self.conversations[doc_id] = []

        return True

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def _retrieve_chunks(self, doc_id: str, question: str, top_k: int = 6) -> list[str]:
        """Return the most relevant chunks for a question using TF-IDF."""
        chunks = self.doc_chunks.get(doc_id, [])
        vectorizer = self.vectorizers.get(doc_id)
        vectors = self.doc_vectors.get(doc_id)

        if not chunks:
            return []

        scored: list[tuple[str, float]] = []

        # TF-IDF cosine similarity
        if vectorizer is not None and vectors is not None:
            try:
                q_vec = vectorizer.transform([question])
                sims = cosine_similarity(q_vec, vectors)[0]
                for idx, score in enumerate(sims):
                    if score > 0.03:
                        scored.append((chunks[idx], float(score)))
            except Exception as e:
                print(f"   ⚠️  Retrieval error: {e}")

        # Keyword overlap fallback / booster
        q_keywords = self._keywords(question)
        for chunk in chunks:
            c_keywords = self._keywords(chunk)
            if not c_keywords:
                continue
            overlap = len(q_keywords & c_keywords) / max(len(q_keywords), 1)
            if overlap > 0.1:
                # Merge with existing score or add new
                existing = next((i for i, (c, _) in enumerate(scored) if c == chunk), None)
                if existing is not None:
                    scored[existing] = (chunk, scored[existing][1] + overlap * 0.4)
                else:
                    scored.append((chunk, overlap * 0.4))

        # Deduplicate, sort, return top_k
        seen: set[str] = set()
        unique: list[tuple[str, float]] = []
        for chunk, score in scored:
            key = chunk[:120]
            if key not in seen:
                seen.add(key)
                unique.append((chunk, score))

        unique.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in unique[:top_k]]

    # ------------------------------------------------------------------
    # Answering
    # ------------------------------------------------------------------

    def answer_question(
        self,
        doc_id: str,
        question: str,
        conversation_history: list | None = None,
    ) -> dict:
        """Answer a question using RAG + Groq (or TF-IDF fallback)."""

        if doc_id not in self.doc_chunks or not self.doc_chunks[doc_id]:
            return {
                'answer': "Document not found or empty. Please upload a valid document.",
                'confidence': 0.0,
                'sources': [],
            }

        try:
            top_chunks = self._retrieve_chunks(doc_id, question, top_k=6)

            if self.llm_available and self.api_key and top_chunks:
                answer, confidence = self._answer_with_groq(
                    question, top_chunks, conversation_history or []
                )
            else:
                # Pure TF-IDF extraction fallback
                answer, confidence = self._answer_tfidf(doc_id, question, top_chunks)

            self._save_conversation(doc_id, question, answer, confidence)

            return {
                'answer': answer,
                'confidence': float(min(confidence, 1.0)),
                'sources': top_chunks[:2],
            }

        except Exception as e:
            print(f"❌ answer_question error: {e}")
            traceback.print_exc()
            return {
                'answer': "I encountered an error processing your question. Please try again.",
                'confidence': 0.0,
                'sources': [],
            }

    def _answer_with_groq(
        self,
        question: str,
        chunks: list[str],
        history: list[dict],
    ) -> tuple[str, float]:
        """
        Generate an answer using Groq with retrieved chunks as context (RAG).
        Includes recent conversation history for follow-up support.
        """

        # Build context block from retrieved chunks
        context = "\n\n---\n\n".join(
            f"[Excerpt {i + 1}]\n{chunk}" for i, chunk in enumerate(chunks)
        )

        system_prompt = (
            "You are a helpful document assistant. "
            "Answer the user's question using ONLY the document excerpts provided. "
            "If the excerpts do not contain enough information, say so clearly — do not invent facts. "
            "Be concise yet complete. Use plain language."
        )

        # Build conversation history
        conversation_text = ""
        for turn in history[-6:]:
            role = turn.get('role')
            content = turn.get('content', '')
            if role in ('user', 'assistant') and content:
                conversation_text += f"{role.capitalize()}: {content}\n"

        # Choose best available model
        model = self._select_best_model()
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Document excerpts:\n\n{context}\n\nConversation history:\n{conversation_text}\n\nQuestion: {question}"}
                ],
                "temperature": 0.3,  # Low for factual responses
                "max_tokens": 512,
                "top_p": 0.9
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result["choices"][0]["message"]["content"].strip()
                confidence = 0.90  # High confidence for LLM responses
                return answer, confidence
            else:
                print(f"   ⚠️  Groq API error {response.status_code}: {response.text[:200]}")
                return self._answer_tfidf_from_chunks(question, chunks)

        except Exception as e:
            print(f"   ⚠️  Unexpected Groq error: {e}")
            return self._answer_tfidf_from_chunks(question, chunks)

    def _select_best_model(self) -> str:
        """Select the best available Groq model."""
        if not self.available_models:
            return "mixtral-8x7b-32768"  # Safe default
        
        # Priority order (best to good)
        preferred = [
            "mixtral-8x7b-32768",  # Best for Q&A
            "llama3-70b-8192",      # Excellent
            "llama3-8b-8192",       # Good and fast
            "gemma-7b-it"           # Decent fallback
        ]
        
        for model in preferred:
            if model in self.available_models:
                return model
        
        return self.available_models[0]  # First available

    def _answer_tfidf(self, doc_id: str, question: str, chunks: list[str]) -> tuple[str, float]:
        """TF-IDF extraction fallback when Groq is unavailable."""
        if not chunks:
            return self._fallback_response(question), 0.2
        return self._answer_tfidf_from_chunks(question, chunks)

    def _answer_tfidf_from_chunks(self, question: str, chunks: list[str]) -> tuple[str, float]:
        """Extract the most relevant sentences from chunks."""
        q_keywords = self._keywords(question)
        scored_sentences: list[tuple[str, float]] = []
        seen: set[str] = set()

        for chunk in chunks:
            for sent in sent_tokenize(chunk):
                key = sent[:80]
                if key in seen or len(sent.split()) < 5:
                    continue
                seen.add(key)
                overlap = len(q_keywords & self._keywords(sent)) / max(len(q_keywords), 1)
                if overlap > 0.1:
                    scored_sentences.append((sent, overlap))

        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        top = [s for s, _ in scored_sentences[:4]]

        if not top:
            return self._fallback_response(question), 0.2

        answer = ' '.join(top)
        confidence = min(0.75, scored_sentences[0][1] * 1.2)
        return answer, confidence

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _keywords(self, text: str) -> set[str]:
        words = word_tokenize(text.lower())
        return {
            re.sub(r'[^\w]', '', w)
            for w in words
            if len(w) > 2 and w not in self.stop_words and not w.isdigit()
        }

    def _fallback_response(self, question: str) -> str:
        q = question.lower()
        if any(g in q for g in ('hello', 'hi', 'hey')):
            return "Hello! Ask me anything about your document."
        if 'help' in q:
            return (
                "You can ask things like:\n"
                "• 'What is this document about?'\n"
                "• 'Who is [name]?'\n"
                "• 'Summarise the main points'\n"
                "• 'Tell me about [topic]'"
            )
        if 'thank' in q:
            return "You're welcome! Feel free to ask more questions."
        return (
            "I couldn't find specific information about that in the document. "
            "Try rephrasing or ask about a different part of the document."
        )

    # ------------------------------------------------------------------
    # Conversation management
    # ------------------------------------------------------------------

    def _save_conversation(self, doc_id: str, question: str, answer: str, confidence: float):
        if doc_id not in self.conversations:
            self.conversations[doc_id] = []

        ts = datetime.now().isoformat()
        self.conversations[doc_id].extend([
            {'role': 'user', 'content': question, 'timestamp': ts},
            {'role': 'assistant', 'content': answer, 'confidence': confidence, 'timestamp': ts},
        ])

        # Keep last 50 messages
        self.conversations[doc_id] = self.conversations[doc_id][-50:]

    def get_conversation_history(self, doc_id: str) -> list[dict]:
        return self.conversations.get(doc_id, [])

    def clear_conversation(self, doc_id: str):
        self.conversations[doc_id] = []

    def get_document_info(self, doc_id: str) -> dict:
        return self.documents.get(doc_id, {})