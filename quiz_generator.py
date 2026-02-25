"""
quiz_generator.py
─────────────────
Generates high-quality quiz questions from document text using NLP.

Question types:
  • multiple_choice  – fill-blank MCQ with smart POS-matched distractors
  • short_answer     – Wh- questions built from named entities
  • fill_blank       – blank out the most important noun, hint included
  • true_false       – real sentence (True) or deliberately corrupted (False)

Every question includes an 'explanation' field shown after answering.
Drop this file into your backend/ folder, replacing the old quiz_generator.py.
"""

import random
import re
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.tag import pos_tag
from nltk.chunk import ne_chunk
from collections import Counter


# ─────────────────────────────────────────────────────────────────────────────
#  Download required NLTK data quietly on first run
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_nltk():
    resources = [
        ('tokenizers/punkt',                        'punkt'),
        ('tokenizers/punkt_tab',                    'punkt_tab'),
        ('corpora/stopwords',                       'stopwords'),
        ('taggers/averaged_perceptron_tagger',      'averaged_perceptron_tagger'),
        ('taggers/averaged_perceptron_tagger_eng',  'averaged_perceptron_tagger_eng'),
        ('chunkers/maxent_ne_chunker',              'maxent_ne_chunker'),
        ('corpora/words',                           'words'),
    ]
    for path, pkg in resources:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(pkg, quiet=True)

_ensure_nltk()
STOPWORDS = set(stopwords.words('english'))


# ─────────────────────────────────────────────────────────────────────────────
#  Module-level NLP helpers
# ─────────────────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s\.,;:!?()\-\'"]', '', text)
    return text.strip()


def _extract_keywords(sentences: list, top_n: int = 80) -> list:
    """Return top-N meaningful words ranked by term frequency."""
    all_words = []
    for s in sentences:
        tokens = word_tokenize(s.lower())
        all_words.extend(
            t for t in tokens
            if t.isalpha() and t not in STOPWORDS and len(t) > 3
        )
    freq = Counter(all_words)
    return [w for w, _ in freq.most_common(top_n)]


def _pos_tag_sentence(sentence: str):
    tokens = word_tokenize(sentence)
    tags   = pos_tag(tokens)
    return tokens, tags


def _candidate_answers(tags: list) -> list:
    """
    Return (index, word, pos) for tokens that make good answer candidates:
    nouns, proper nouns, adjectives, non-auxiliary verbs, numbers.
    """
    good_pos = {
        'NN', 'NNS', 'NNP', 'NNPS',
        'JJ', 'JJR', 'JJS',
        'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ',
        'CD'
    }
    aux_verbs = {
        'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'shall', 'should', 'may', 'might',
        'must', 'can', 'could'
    }
    candidates = []
    for i, (word, tag) in enumerate(tags):
        if tag in good_pos and word.lower() not in STOPWORDS:
            if tag.startswith('V') and word.lower() in aux_verbs:
                continue
            if len(word) > 2 and word.isalpha():
                candidates.append((i, word, tag))
    return candidates


def _named_entities(sentence: str) -> list:
    """Extract named entities (people, places, orgs, etc.) from a sentence."""
    tokens = word_tokenize(sentence)
    tags   = pos_tag(tokens)
    tree   = ne_chunk(tags, binary=False)
    entities = []
    for subtree in tree:
        if hasattr(subtree, 'label'):
            entity = ' '.join(w for w, _ in subtree.leaves())
            entities.append(entity)
    return entities


def _build_distractors(answer: str, answer_pos: str,
                       corpus_keywords: list,
                       sentence_tokens: list,
                       n: int = 3) -> list:
    """
    Build n plausible wrong-answer options.
    Priority: same-POS corpus words → sentence tokens → generic fallback.
    """
    answer_lower = answer.lower()
    pool = []

    # 1. Same-POS words from corpus
    _, corpus_tags = _pos_tag_sentence(' '.join(corpus_keywords))
    same_pos = [
        w for w, t in corpus_tags
        if t.startswith(answer_pos[:2])
        and w.lower() != answer_lower
        and w.isalpha()
        and w.lower() not in STOPWORDS
        and len(w) > 2
    ]
    pool.extend(same_pos)

    # 2. Other tokens from the same sentence
    sent_extras = [
        w for w in sentence_tokens
        if w.lower() != answer_lower
        and w.isalpha()
        and w.lower() not in STOPWORDS
        and len(w) > 2
        and w not in pool
    ]
    pool.extend(sent_extras)

    # 3. Generic domain-neutral fallback
    fallback = [
        'system', 'process', 'method', 'result', 'value',
        'structure', 'function', 'element', 'factor', 'component',
        'approach', 'concept', 'principle', 'model', 'framework',
    ]
    pool.extend(f for f in fallback if f not in pool and f.lower() != answer_lower)

    # Deduplicate preserving order
    seen  = set()
    unique = []
    for w in pool:
        key = w.lower()
        if key not in seen and key != answer_lower:
            seen.add(key)
            unique.append(w)

    # Prefer distractors of similar length (harder)
    unique.sort(key=lambda w: abs(len(w) - len(answer)))
    return unique[:n]


# ─────────────────────────────────────────────────────────────────────────────
#  Individual question builders
# ─────────────────────────────────────────────────────────────────────────────

def _make_mcq(sentence: str, idx: int, corpus_keywords: list):
    """Multiple-choice: blank a key word, provide 3 wrong options."""
    sentence = _clean(sentence)
    tokens, tags = _pos_tag_sentence(sentence)
    candidates   = _candidate_answers(tags)
    if not candidates:
        return None

    entities        = _named_entities(sentence)
    entity_cands    = [c for c in candidates if c[1] in entities]
    noun_cands      = [c for c in candidates if c[2].startswith('NN')]

    if entity_cands:
        chosen = random.choice(entity_cands)
    elif noun_cands:
        chosen = random.choice(noun_cands)
    else:
        chosen = random.choice(candidates)

    ans_idx, answer, ans_pos = chosen

    question_tokens         = list(tokens)
    question_tokens[ans_idx] = '___'
    stem = ' '.join(question_tokens)
    stem = re.sub(r'\s([?.!,;:])', r'\1', stem)

    distractors = _build_distractors(answer, ans_pos, corpus_keywords, tokens)
    if len(distractors) < 2:
        return None

    options = [answer] + distractors[:3]
    random.shuffle(options)

    return {
        'id':          idx,
        'type':        'multiple_choice',
        'question':    f'Which word correctly fills the blank?\n"{stem}"',
        'context':     sentence,
        'options':     options,
        'answer':      answer,
        'explanation': f'The answer "{answer}" fits the context of the sentence.'
    }


def _make_wh_question(sentence: str, idx: int):
    """Short-answer Wh- question built from named entities."""
    sentence = _clean(sentence)
    tokens, tags = _pos_tag_sentence(sentence)
    entities     = _named_entities(sentence)

    if entities:
        entity = entities[0]
        months = ['January','February','March','April','May','June',
                  'July','August','September','October','November','December']
        if any(m in entity for m in months):
            qword = 'When'
        elif any(c.isupper() for c in entity[1:]):
            qword = random.choice(['Who', 'What'])
        else:
            qword = 'What'

        stem = sentence.replace(entity, qword, 1).strip()
        if not stem.endswith('?'):
            stem = stem.rstrip('.') + '?'

        return {
            'id':          idx,
            'type':        'short_answer',
            'question':    stem,
            'context':     sentence,
            'answer':      entity,
            'explanation': f'Based on the sentence: "{sentence}"'
        }

    # Fallback: pick a noun
    noun_cands = [
        (i, w) for i, (w, t) in enumerate(tags)
        if t.startswith('NN') and w.lower() not in STOPWORDS and len(w) > 3
    ]
    if not noun_cands:
        return None

    ans_idx, answer = random.choice(noun_cands)
    q_tokens        = list(tokens)
    q_tokens[ans_idx] = 'what'
    q = ' '.join(q_tokens).capitalize().rstrip('.') + '?'

    return {
        'id':          idx,
        'type':        'short_answer',
        'question':    q,
        'context':     sentence,
        'answer':      answer,
        'explanation': f'Based on the sentence: "{sentence}"'
    }


def _make_fill_blank(sentence: str, idx: int):
    """Fill-in-the-blank: blank out the most important noun."""
    sentence = _clean(sentence)
    tokens, tags = _pos_tag_sentence(sentence)
    candidates   = _candidate_answers(tags)

    noun_cands = [c for c in candidates if c[2].startswith('NN')]
    pool       = noun_cands if noun_cands else candidates
    if not pool:
        return None

    ans_idx, answer, _ = random.choice(pool)
    tokens_copy        = list(tokens)
    tokens_copy[ans_idx] = '_______'
    stem = ' '.join(tokens_copy)
    stem = re.sub(r'\s([?.!,;:])', r'\1', stem)

    return {
        'id':          idx,
        'type':        'fill_blank',
        'question':    f'Fill in the blank:\n"{stem}"',
        'answer':      answer,
        'hint':        f'The missing word has {len(answer)} letters.',
        'explanation': f'The missing word is "{answer}".'
    }


def _make_true_false(sentence: str, idx: int):
    """True/False: present the real sentence or a deliberately corrupted one."""
    sentence = _clean(sentence)
    if len(sentence.split()) < 6:
        return None

    tokens, tags = _pos_tag_sentence(sentence)
    is_true      = random.choice([True, False])

    if is_true:
        return {
            'id':          idx,
            'type':        'true_false',
            'question':    f'True or False?\n"{sentence}"',
            'options':     ['True', 'False'],
            'answer':      'True',
            'explanation': 'This statement appears directly in the document.'
        }

    # Corrupt: swap a key noun with a neutral replacement
    candidates = _candidate_answers(tags)
    noun_cands = [c for c in candidates if c[2].startswith('NN')]
    pool       = noun_cands if noun_cands else candidates

    if not pool:
        # Can't corrupt – make it True instead
        return {
            'id':          idx,
            'type':        'true_false',
            'question':    f'True or False?\n"{sentence}"',
            'options':     ['True', 'False'],
            'answer':      'True',
            'explanation': 'This statement appears directly in the document.'
        }

    ans_idx, original_word, _ = random.choice(pool)
    replacements = [
        r for r in ['system', 'process', 'method', 'concept', 'element',
                    'component', 'factor', 'structure', 'approach']
        if r.lower() != original_word.lower()
    ]
    replacement  = random.choice(replacements)
    tokens_copy  = list(tokens)
    tokens_copy[ans_idx] = replacement
    corrupted = ' '.join(tokens_copy)
    corrupted = re.sub(r'\s([?.!,;:])', r'\1', corrupted)

    return {
        'id':          idx,
        'type':        'true_false',
        'question':    f'True or False?\n"{corrupted}"',
        'options':     ['True', 'False'],
        'answer':      'False',
        'explanation': (
            f'The statement is false. '
            f'The correct word is "{original_word}", not "{replacement}".'
        )
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Main class
# ─────────────────────────────────────────────────────────────────────────────

class QuizGenerator:
    """
    Generates high-quality quiz questions from document text.
    Public API:  generate_quiz(text, num=5)  →  list of question dicts
    """

    def __init__(self):
        print("📝 Quiz Generator (Enhanced NLP) ready")

    def generate_quiz(self, text: str, num: int = 5) -> list:
        """
        Generate `num` quiz questions from `text`.
        Returns a list of question dicts, each with:
          id, type, question, answer, explanation
          + options (MCQ / true_false)
          + hint    (fill_blank)
          + context (MCQ / short_answer)
        """
        if not text or len(text.strip()) < 100:
            return [self._error_q(0,
                'Not enough text to generate a quiz.',
                'Please upload a longer document.'
            )]

        sentences = self._good_sentences(text)

        if len(sentences) < 3:
            return [self._error_q(0,
                'Document too short for a quiz.',
                'Please use a longer document.'
            )]

        num             = min(num, len(sentences))
        corpus_keywords = _extract_keywords(sentences, top_n=100)
        type_cycle      = ['mcq', 'short_answer', 'fill_blank', 'true_false']
        selected        = random.sample(sentences, num)
        questions       = []

        for i, sentence in enumerate(selected):
            q_type = type_cycle[i % len(type_cycle)]
            q      = self._build_question(q_type, sentence, i, corpus_keywords)

            # Fallback: try other types until one works
            if q is None:
                for fallback in type_cycle:
                    if fallback != q_type:
                        q = self._build_question(fallback, sentence, i, corpus_keywords)
                        if q:
                            break

            if q:
                questions.append(q)

        if not questions:
            return [self._error_q(0,
                'Could not generate questions.',
                'Try a document with more varied content.'
            )]

        return questions

    # ── Private helpers ────────────────────────────────────────────────────

    def _good_sentences(self, text: str) -> list:
        """Keep only sentences that are long enough and informative."""
        raw = sent_tokenize(text)
        return [
            s for s in raw
            if 8 <= len(s.split()) <= 60
            and not s.strip().startswith('•')
            and not re.match(r'^\d+[\.\)]', s.strip())
        ]

    def _build_question(self, q_type: str, sentence: str,
                        idx: int, corpus_keywords: list):
        try:
            if q_type == 'mcq':
                return _make_mcq(sentence, idx, corpus_keywords)
            elif q_type == 'short_answer':
                return _make_wh_question(sentence, idx)
            elif q_type == 'fill_blank':
                return _make_fill_blank(sentence, idx)
            elif q_type == 'true_false':
                return _make_true_false(sentence, idx)
        except Exception as e:
            print(f"⚠️  Quiz build error ({q_type}): {e}")
        return None

    @staticmethod
    def _error_q(idx: int, question: str, answer: str) -> dict:
        return {
            'id':       idx,
            'type':     'error',
            'question': question,
            'answer':   answer
        }