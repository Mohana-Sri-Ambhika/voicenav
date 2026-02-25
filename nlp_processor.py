# backend/nlp_processor.py - COMPLETE WORKING VERSION

import spacy
import re
from difflib import SequenceMatcher
import nltk
from nltk.tokenize import sent_tokenize
import pickle
import os
import json
from collections import defaultdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import trafilatura
import html2text
import validators

# ==================== WEB CONTENT EXTRACTOR ====================

class WebContentExtractor:
    """Extract clean text from URLs"""
    def __init__(self):
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.ignore_images = True
        self.h.ignore_tables = False
        self.h.ignore_emphasis = False
        self.h.body_width = 0
        
    def extract_from_url(self, url):
        """Extract clean text content from URL"""
        print(f"🌐 Fetching content from: {url}")
        
        try:
            # Send request with browser-like headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Try trafilatura first (best for main content extraction)
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
                if text and len(text) > 100:
                    print(f"✅ Extracted {len(text)} characters using trafilatura")
                    return self._post_process(text, url)
            
            # Fallback to BeautifulSoup + html2text
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Convert to markdown-style text
            text = self.h.handle(str(soup))
            
            # Clean up excessive whitespace
            text = re.sub(r'\n\s*\n', '\n\n', text)
            text = text.strip()
            
            print(f"✅ Extracted {len(text)} characters using BeautifulSoup")
            return self._post_process(text, url)
            
        except Exception as e:
            print(f"❌ Error extracting from URL: {e}")
            return None
    
    def _post_process(self, text, url):
        """Post-process extracted text"""
        # Detect if it's an article/blog post
        if self._is_article(text):
            text = self._extract_article_content(text)
        
        # Detect if it's documentation
        elif self._is_documentation(url, text):
            text = self._format_documentation(text)
        
        return text
    
    def _is_article(self, text):
        """Detect if content is an article/blog post"""
        lines = text.split('\n')
        if len(lines) > 20:
            # Check for article-like structure
            has_date = bool(re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b', text))
            has_byline = bool(re.search(r'by\s+[A-Z][a-z]+\s+[A-Z][a-z]+', text.lower()))
            return has_date or has_byline
        return False
    
    def _is_documentation(self, url, text):
        """Detect if content is documentation"""
        doc_indicators = ['docs', 'documentation', 'guide', 'tutorial', 'api', 'reference']
        url_lower = url.lower()
        
        # Check URL
        for indicator in doc_indicators:
            if indicator in url_lower:
                return True
        
        # Check content
        lines = text.split('\n')[:20]  # First 20 lines
        content_start = ' '.join(lines).lower()
        for indicator in doc_indicators:
            if indicator in content_start:
                return True
        
        return False
    
    def _extract_article_content(self, text):
        """Extract main content from article"""
        lines = text.split('\n')
        content_lines = []
        in_content = False
        
        for line in lines:
            # Skip common article metadata
            if re.match(r'^by\s+', line.lower()) and len(line) < 100:
                continue
            if re.match(r'^published|^date|^posted', line.lower()):
                continue
            if re.match(r'^share|^tweet|^email', line.lower()):
                continue
            
            # Start collecting after we find substantial content
            if len(line.strip()) > 50:
                in_content = True
            
            if in_content:
                content_lines.append(line)
        
        return '\n'.join(content_lines)
    
    def _format_documentation(self, text):
        """Format documentation text"""
        lines = text.split('\n')
        formatted = []
        
        for line in lines:
            # Preserve code blocks
            if line.strip().startswith('```') or line.strip().startswith('    '):
                formatted.append(line)
            # Format headings
            elif re.match(r'^#{1,3}\s+', line):
                formatted.append(f"\n{line}\n")
            else:
                formatted.append(line)
        
        return '\n'.join(formatted)
    
    def extract_metadata(self, url, soup):
        """Extract metadata from URL"""
        metadata = {
            'url': url,
            'domain': urlparse(url).netloc,
            'title': '',
            'description': '',
            'author': '',
            'published_date': '',
            'headings': []
        }
        
        # Get title
        if soup.title:
            metadata['title'] = soup.title.string
        
        # Get meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            metadata['description'] = meta_desc.get('content', '')
        
        # Get author
        author_meta = soup.find('meta', attrs={'name': 'author'})
        if author_meta:
            metadata['author'] = author_meta.get('content', '')
        
        # Get all headings for structure
        for level in range(1, 7):
            for heading in soup.find_all(f'h{level}'):
                metadata['headings'].append({
                    'level': level,
                    'text': heading.get_text().strip()
                })
        
        return metadata


# ==================== URL SECTION DETECTOR (ML-Based) ====================

class URLSectionDetector:
    """
    ML-based section detector that works well for web content
    (This is your original TrainedSectionDetector)
    """
    def __init__(self):
        self.heading_patterns = {
            'numbered': r'^\s*(\d+[\.\)\-]?\s*)+[A-Z0-9]',
            'roman': r'^\s*[IVX]+\.\s+[A-Z]',
            'all_caps': r'^[A-Z\s]{10,}$',
            'title_case': r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$',
            'html_headings': r'^h[1-6]',
            'markdown_headings': r'^#{1,6}\s+',
            'academic': ['abstract', 'introduction', 'methodology', 'results', 
                        'discussion', 'conclusion', 'references', 'appendix'],
            'web_common': ['navigation', 'menu', 'sidebar', 'footer', 'header',
                          'comments', 'related', 'popular', 'recent'],
            'legal': ['whereas', 'article', 'section', 'clause', 'paragraph'],
            'technical': ['overview', 'prerequisites', 'installation', 'configuration',
                         'api', 'usage', 'examples', 'troubleshooting']
        }
        
        self.feature_names = [
            'is_uppercase_ratio',
            'has_numbers',
            'word_count',
            'ends_with_colon',
            'starts_with_number',
            'average_word_length',
            'contains_special_chars',
            'is_bullet_point',
            'indent_level',
            'prev_line_empty',
            'next_line_empty',
            'similar_to_known_headings',
            'html_tag_weight',
            'font_size_indicator'
        ]
        
        self.model = None
        self.vectorizer = TfidfVectorizer(max_features=100)
        self.training_data = []
        self.known_heading_patterns = defaultdict(int)
        
    def extract_features(self, line, prev_line, next_line, lines, idx, html_context=None):
        """Extract features for ML-based heading detection"""
        features = []
        
        # Uppercase ratio
        uppercase_ratio = sum(1 for c in line if c.isupper()) / max(len(line), 1)
        features.append(uppercase_ratio)
        
        # Has numbers
        features.append(1 if re.search(r'\d', line) else 0)
        
        # Word count
        words = line.split()
        features.append(len(words))
        
        # Ends with colon
        features.append(1 if line.rstrip().endswith(':') else 0)
        
        # Starts with number
        features.append(1 if re.match(r'^\s*\d+', line) else 0)
        
        # Average word length
        avg_word_len = sum(len(w) for w in words) / max(len(words), 1)
        features.append(avg_word_len)
        
        # Contains special characters (.,;:-)
        features.append(1 if re.search(r'[.,;:\-]', line) else 0)
        
        # Is bullet point
        features.append(1 if re.match(r'^\s*[•\-*]\s+', line) else 0)
        
        # Indent level
        indent = len(line) - len(line.lstrip())
        features.append(indent / 4)  # Normalized by tab size
        
        # Previous line empty
        features.append(1 if idx > 0 and not lines[idx-1].strip() else 0)
        
        # Next line empty
        features.append(1 if idx < len(lines)-1 and not lines[idx+1].strip() else 0)
        
        # Similar to known headings
        similarity_score = 0
        for pattern, count in self.known_heading_patterns.items():
            if pattern in line.lower():
                similarity_score += count
        features.append(min(similarity_score / 10, 1))  # Normalize
        
        # HTML context (if available)
        if html_context and idx in html_context:
            html_weight = html_context[idx].get('weight', 0)
            features.append(html_weight)
            features.append(html_context[idx].get('font_size', 0))
        else:
            features.append(0)
            features.append(0)
        
        return features
    
    def train_on_document(self, text, manual_headings=None, html_context=None):
        """Train the detector on a document with optional manual heading labels"""
        lines = text.split('\n')
        features_list = []
        labels = []
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
                
            prev_line = lines[i-1] if i > 0 else ""
            next_line = lines[i+1] if i < len(lines)-1 else ""
            
            features = self.extract_features(line, prev_line, next_line, lines, i, html_context)
            features_list.append(features)
            
            # Auto-label based on patterns
            is_heading = self._rule_based_detection(line, prev_line, next_line)
            
            # Override with manual labels if provided
            if manual_headings and line.strip() in manual_headings:
                is_heading = manual_headings[line.strip()]
                
            labels.append(1 if is_heading else 0)
            
            # Update known patterns
            if is_heading:
                self.known_heading_patterns[line.lower().strip()] += 1
        
        self.training_data.extend(zip(features_list, labels))
        
        # Train/update model if we have enough data
        if len(self.training_data) >= 50:
            self._train_model()
    
    def _rule_based_detection(self, line, prev_line, next_line):
        """Rule-based heading detection as fallback"""
        line = line.strip()
        
        if not line:
            return False
            
        # Check against known patterns
        for pattern_name, pattern in self.heading_patterns.items():
            if pattern_name in ['academic', 'web_common', 'legal', 'technical']:
                if line.lower() in pattern:
                    return True
            elif isinstance(pattern, str) and re.match(pattern, line, re.IGNORECASE):
                return True
        
        # Length heuristics
        words = line.split()
        if len(words) > 15:  # Too long for heading
            return False
            
        # Format heuristics
        if (line[0].isupper() and 
            len(words) <= 10 and 
            not line.endswith(('.', ',', ';')) and
            (prev_line == "" or prev_line.endswith(('.', '!', '?')) or 
             next_line == "" or len(next_line.split()) > 10)):
            return True
            
        return False
    
    def _train_model(self):
        """Train Random Forest classifier on collected data"""
        if len(self.training_data) < 50:
            return
            
        X = np.array([item[0] for item in self.training_data])
        y = np.array([item[1] for item in self.training_data])
        
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.model.fit(X, y)
        print(f"✅ Model trained on {len(self.training_data)} samples")
    
    def predict_heading(self, line, prev_line, next_line, lines, idx, html_context=None):
        """Predict if a line is a heading using ML or fallback rules"""
        if self.model is not None and len(self.training_data) >= 50:
            features = np.array([self.extract_features(line, prev_line, next_line, lines, idx, html_context)])
            prob = self.model.predict_proba(features)[0]
            return prob[1] > 0.5  # Use probability threshold
        else:
            return self._rule_based_detection(line, prev_line, next_line)
    
    def extract_sections(self, text):
        """Extract sections from URL content using ML approach"""
        sections = {}
        lines = text.split('\n')
        current_section = "Introduction"
        current_content = []
        heading_candidates = []
        
        print("\n🔍 Scanning URL for sections using AI...")
        
        # First pass: identify all potential headings
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            prev_line = lines[i-1].strip() if i > 0 else ""
            next_line = lines[i+1].strip() if i < len(lines)-1 else ""
            
            is_heading = self.predict_heading(
                line, prev_line, next_line, lines, i
            )
            
            if is_heading:
                heading_candidates.append((i, line))
                print(f"  📍 Candidate heading: {line[:60]}")
        
        # If no headings found, treat as one section
        if not heading_candidates:
            return {"Content": text}
        
        # Second pass: group content under headings
        last_heading = "Introduction"
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                if current_content:
                    current_content.append('')
                continue
            
            # Check if this line is a heading
            is_heading_line = False
            for idx, heading in heading_candidates:
                if idx == i:
                    if current_content:
                        sections[last_heading] = '\n'.join(current_content).strip()
                    last_heading = heading
                    current_content = []
                    is_heading_line = True
                    break
            
            if not is_heading_line:
                current_content.append(line)
        
        # Add last section
        if current_content:
            sections[last_heading] = '\n'.join(current_content).strip()
        
        print(f"\n✅ Total sections detected: {len(sections)}")
        return sections


# ==================== DOCUMENT SECTION DETECTOR (Conservative) ====================

class DocumentSectionDetector:
    """
    Conservative section detector for uploaded documents (PDF, DOCX, TXT)
    Uses rule-based approach with minimal false positives
    """
    
    def __init__(self):
        # Common section headers that indicate REAL sections
        self.common_sections = {
            # Academic
            'abstract', 'introduction', 'background', 'literature review', 
            'methodology', 'methods', 'results', 'findings', 'discussion', 
            'conclusion', 'conclusions', 'references', 'bibliography', 
            'appendix', 'acknowledgments',
            
            # Business/Reports
            'executive summary', 'overview', 'objectives', 'scope', 
            'limitations', 'assumptions', 'recommendations', 'next steps',
            'budget', 'timeline', 'schedule', 'appendices',
            
            # Technical
            'installation', 'configuration', 'setup', 'usage', 'examples',
            'api', 'api reference', 'faq', 'troubleshooting', 'support',
            'system requirements', 'prerequisites', 'getting started',
            
            # Legal
            'definitions', 'terms', 'conditions', 'warranty', 'liability',
            'indemnification', 'governing law', 'dispute resolution',
            
            # Medical
            'chief complaint', 'history', 'physical examination', 'assessment',
            'plan', 'diagnosis', 'treatment', 'follow-up', 'prognosis'
        }
        
        # Section header patterns that are likely legitimate
        self.section_patterns = [
            r'^(?:chapter|section|part)\s+\d+[:.\s]+\w+',  # Chapter/Part numbering
            r'^\d+\.\d+\s+\w+',  # Numbered sections (1.1, 2.3)
            r'^[A-Z][A-Z\s]{3,}$',  # ALL CAPS headers (min 4 chars)
            r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$',  # Title Case (2-4 words)
            r'^[IVX]+\.\s+\w+',  # Roman numerals
        ]
        
        # Minimum section content length (to avoid false positives)
        self.min_section_content = 200
        
    def detect_sections(self, text):
        """
        Detect legitimate sections in document
        Returns dict of {section_name: content}
        If no sections found, returns empty dict (caller should treat as one document)
        """
        sections = {}
        lines = text.split('\n')
        
        current_section = "Introduction"
        current_content = []
        section_candidates = []
        
        print("\n📄 Scanning document for legitimate sections...")
        
        # First pass: identify potential section headers
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 3:
                continue
            
            if self._is_legitimate_header(line, i, lines):
                # Check if next few lines are substantial (not just a fluke)
                if self._has_substantial_content_after(i, lines):
                    section_candidates.append((i, line))
                    print(f"  📍 Found section: {line[:60]}")
        
        # If no sections found, return empty dict
        if not section_candidates:
            print("  ℹ️ No clear sections detected - treating as single document")
            return {}
        
        # Second pass: group content under sections
        last_heading = "Introduction"
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                if current_content:
                    current_content.append('')
                continue
            
            # Check if this line is a heading
            is_heading = False
            for idx, heading in section_candidates:
                if idx == i:
                    # Save previous section if it has enough content
                    if current_content and len(' '.join(current_content)) > self.min_section_content:
                        sections[last_heading] = '\n'.join(current_content)
                    
                    last_heading = heading
                    current_content = []
                    is_heading = True
                    break
            
            if not is_heading:
                current_content.append(line)
        
        # Add last section if it has enough content
        if current_content and len(' '.join(current_content)) > self.min_section_content:
            sections[last_heading] = '\n'.join(current_content)
        
        # Filter out sections that are too short
        sections = {name: content for name, content in sections.items() 
                   if len(content) > self.min_section_content}
        
        print(f"\n✅ Detected {len(sections)} legitimate sections")
        
        return sections
    
    def _is_legitimate_header(self, line, index, lines):
        """
        Strict check for legitimate section headers
        """
        line_lower = line.lower()
        
        # Check against common sections first
        if line_lower in self.common_sections:
            return True
        
        # Check against patterns
        for pattern in self.section_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        
        # Check formatting characteristics
        words = line.split()
        
        # Headers shouldn't be too long
        if len(words) > 8:
            return False
        
        # Headers shouldn't end with punctuation
        if line[-1] in '.!,;:?':
            return False
        
        # Headers are usually capitalized
        if not line[0].isupper():
            return False
        
        # Check context: previous line should be empty or shorter
        if index > 0:
            prev_line = lines[index-1].strip()
            if prev_line and len(prev_line) > len(line) * 0.7:
                # If previous line has similar length, this might not be a header
                return False
        
        # Next line should exist and be longer (content follows)
        if index < len(lines) - 1:
            next_line = lines[index+1].strip()
            if not next_line or len(next_line) < 20:
                return False
        
        return True
    
    def _has_substantial_content_after(self, header_idx, lines, look_ahead=5):
        """
        Check if there's substantial content after a potential header
        """
        content_chars = 0
        lines_checked = 0
        
        for i in range(header_idx + 1, min(header_idx + 20, len(lines))):
            line = lines[i].strip()
            if line:
                content_chars += len(line)
                lines_checked += 1
                if content_chars > 200:  # Enough content found
                    return True
            
            # Stop if we hit another potential header
            if i > header_idx + 2 and self._is_legitimate_header(line, i, lines):
                break
        
        return content_chars > 100


# ==================== MAIN NLP PROCESSOR ====================

class NLPProcessor:
    """
    Main NLP Processor with separate strategies for:
    - URL content (using ML approach)
    - Uploaded documents (using conservative approach)
    - Voice commands (unchanged)
    """
    
    def __init__(self, model_path='section_detector.pkl'):
        print("🧠 Loading NLP with dual-mode section detection...")
        
        # Initialize spaCy (keep for voice commands and general NLP)
        try:
            self.nlp = spacy.load("en_core_web_md")
            print("✅ NLP loaded (medium model)")
        except:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                print("✅ NLP loaded (small model)")
            except:
                print("⚠️ No spaCy model")
                self.nlp = None
        
        # Initialize NLTK
        try:
            nltk.data.find('tokenizers/punkt')
        except:
            nltk.download('punkt', quiet=True)
        
        # Initialize web content extractor (for URLs)
        self.web_extractor = WebContentExtractor()
        
        # Initialize URL section detector (ML-based)
        self.url_detector = URLSectionDetector()
        
        # Initialize document section detector (conservative)
        self.document_detector = DocumentSectionDetector()
        
        # Keep voice command intent patterns (unchanged)
        self.intent_patterns = {
            'read': ['read', 'tell', 'say', 'speak'],
            'summarize': ['summarize', 'summary', 'gist', 'tl;dr'],
            'explain': ['explain', 'what', 'why', 'how', '?', 'meaning'],
            'quiz': ['quiz', 'test', 'questions', 'examine'],
            'note': ['note', 'remember', 'save', 'highlight'],
            'bookmark': ['bookmark', 'mark', 'flag'],
            'control': ['pause', 'resume', 'stop', 'speed', 'volume'],
            'export': ['export', 'download', 'save'],
            'compare': ['compare', 'versus', 'vs', 'difference'],
            'search': ['search', 'find', 'look for', 'locate']
        }
        
        print("✅ NLP Processor ready with dual-mode detection")
    
    def extract_sections(self, text, source_type=None):
        """
        Main method called by app.py
        Intelligently decides which detector to use based on content characteristics
        """
        # Auto-detect source type if not provided
        if source_type is None:
            # Check if it looks like web content (has HTML-like structure)
            if '<' in text[:1000] and '>' in text[:1000]:
                source_type = 'url'
            # Check if it's very structured (likely document)
            elif text.count('\n\n') > 20 and len(text) > 5000:
                source_type = 'document'
            else:
                # Default to document detector (more conservative)
                source_type = 'document'
        
        print(f"📋 Using {source_type.upper()} section detection")
        
        if source_type == 'url':
            # Use ML-based detector for URLs
            sections = self.url_detector.extract_sections(text)
        else:
            # Use conservative detector for documents
            sections = self.document_detector.detect_sections(text)
            # If no sections detected, treat as single document
            if not sections:
                sections = {"Document": text}
        
        return sections
    
    def identify_intent(self, command):
        """Voice command intent detection (unchanged)"""
        cmd = command.lower()
        
        for intent, keywords in self.intent_patterns.items():
            for keyword in keywords:
                if keyword in cmd:
                    return intent
        return 'unknown'
    
    def find_section(self, command, sections):
        """Find the most relevant section based on command (unchanged)"""
        cmd_lower = command.lower()
        
        # Direct match
        for section in sections:
            if section.lower() in cmd_lower:
                return section
        
        # Fuzzy matching
        best_section = None
        best_ratio = 0
        
        for section in sections:
            ratio = SequenceMatcher(None, cmd_lower, section.lower()).ratio()
            
            cmd_words = set(cmd_lower.split())
            section_words = set(section.lower().split())
            overlap = len(cmd_words & section_words)
            keyword_score = overlap / max(len(cmd_words), 1)
            
            total_score = (ratio * 0.3) + (keyword_score * 0.7)
            
            if total_score > best_ratio and total_score > 0.3:
                best_ratio = total_score
                best_section = section
        
        return best_section
    
    def generate_overview(self, text, num_sentences=3):
        """Generate an intelligent overview of the text"""
        sentences = sent_tokenize(text)
        
        if len(sentences) <= num_sentences:
            return text[:500] + "..." if len(text) > 500 else text
        
        # Try to find important sentences
        if self.nlp:
            doc = self.nlp(text[:5000])  # Process first 5000 chars
            important_sentences = []
            
            for sent in doc.sents:
                # Check if sentence contains key information
                if any(token.ent_type_ for token in sent):  # Has named entities
                    important_sentences.append(sent.text)
                elif sent.text[0].isupper() and len(sent.text.split()) > 5:
                    important_sentences.append(sent.text)
                
                if len(important_sentences) >= num_sentences:
                    break
            
            if important_sentences:
                return ' '.join(important_sentences)
        
        # Fallback: return first few sentences
        return ' '.join(sentences[:num_sentences])
    
    def extract_keywords(self, text, top_n=10):
        """Extract key keywords from text"""
        if not self.nlp:
            return []
        
        doc = self.nlp(text[:10000])  # Limit text size for processing
        
        # Extract nouns and proper nouns
        keywords = []
        for token in doc:
            if token.pos_ in ['NOUN', 'PROPN'] and not token.is_stop and len(token.text) > 2:
                keywords.append(token.text.lower())
        
        # Count frequency
        from collections import Counter
        keyword_freq = Counter(keywords)
        
        return [word for word, count in keyword_freq.most_common(top_n)]


# For testing
if __name__ == "__main__":
    nlp = NLPProcessor()
    
    # Test with document text
    sample_text = """
    Introduction
    This is the introduction to our document. It contains several paragraphs of text that explain the background and context.
    
    Methodology
    We used a variety of methods to conduct this research. The primary approach was experimental.
    
    Results
    The results showed significant improvement in all test cases. We measured accuracy, precision, and recall.
    
    Conclusion
    In conclusion, our findings demonstrate that this approach is effective.
    """
    
    sections = nlp.extract_sections(sample_text, source_type='document')
    print("\n📊 Document Sections:", list(sections.keys()))