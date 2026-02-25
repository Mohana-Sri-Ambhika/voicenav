# backend/document_parser.py - COMPLETE WITH URL SUPPORT
import pdfplumber
from docx import Document
import requests
from bs4 import BeautifulSoup
import re

class DocumentParser:
    def __init__(self):
        print("📄 Document Parser ready")
    
    def parse_file(self, file_path, filename):
        ext = filename.lower().split('.')[-1]
        
        if ext == 'pdf':
            return self._parse_pdf(file_path)
        elif ext == 'docx':
            return self._parse_docx(file_path)
        elif ext == 'txt':
            return self._parse_txt(file_path)
        return ""
    
    def _parse_pdf(self, file_path):
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"PDF error: {e}")
        return self._clean(text)
    
    def _parse_docx(self, file_path):
        text = ""
        try:
            doc = Document(file_path)
            for para in doc.paragraphs:
                if para.text:
                    text += para.text + "\n"
        except Exception as e:
            print(f"DOCX error: {e}")
        return self._clean(text)
    
    def _parse_txt(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except:
                return ""
    
    def parse_url(self, url):
        """Extract text from any URL"""
        try:
            print(f"🌐 Fetching: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            print(f"✅ Fetched: {len(response.text)} bytes")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()
            
            # Get text from paragraphs and headings
            text_parts = []
            
            # Try to find main content
            main = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|main|article'))
            
            if main:
                for tag in main.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    if tag.text.strip():
                        text_parts.append(tag.text.strip())
            else:
                # Get all paragraphs
                for p in soup.find_all('p'):
                    if p.text.strip():
                        text_parts.append(p.text.strip())
                
                # Add headings
                for h in soup.find_all(['h1', 'h2', 'h3']):
                    if h.text.strip():
                        text_parts.append(h.text.strip())
            
            # If still no text, get all text
            if not text_parts:
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                text_parts = [line for line in lines if line]
            
            result = '\n'.join(text_parts)
            print(f"✅ Extracted: {len(result)} characters")
            
            return self._clean(result)
            
        except requests.exceptions.Timeout:
            print("❌ URL timeout")
            return ""
        except requests.exceptions.ConnectionError:
            print("❌ Connection error")
            return ""
        except Exception as e:
            print(f"❌ URL error: {e}")
            return ""
    
    def _clean(self, text):
        """Clean text but preserve line breaks"""
        if not text:
            return ""
        
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            line = re.sub(r'\s+', ' ', line).strip()
            if line:
                cleaned.append(line)
        return '\n'.join(cleaned)