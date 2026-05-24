import re
import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from typing import List

class DocumentService:
    @staticmethod
    def clean_text(text: str) -> str:
        # Remove extra whitespaces, line breaks and formatting noise
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @classmethod
    def extract_from_text(cls, text: str) -> str:
        return cls.clean_text(text)

    @classmethod
    def extract_from_pdf(cls, file_path: str) -> str:
        text = ""
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
        
        return cls.clean_text(text)

    @classmethod
    async def extract_from_url(cls, url: str) -> str:
        # Prepend protocol if missing
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
            
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Strip scripts, styles, footer, and navigation
                for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    element.decompose()
                
                # Get text content
                text = soup.get_text(separator=" ")
                return cls.clean_text(text)
        except Exception as e:
            raise ValueError(f"Failed to scrape content from URL: {str(e)}")

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
        """Simple sliding window chunker based on character index"""
        chunks = []
        if not text:
            return chunks
            
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += chunk_size - chunk_overlap
            
        return chunks
