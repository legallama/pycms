import requests
import json
from ..models.site_settings import SiteSettings

class AIHelper:
    @staticmethod
    def _get_api_key():
        settings = SiteSettings.load()
        return settings.gemini_api_key

    @classmethod
    def generate_content(cls, prompt: str):
        api_key = cls._get_api_key()
        if not api_key:
            return "Error: Gemini API Key not configured in Settings."
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            return f"Error communicating with Gemini: {str(e)}"

    @classmethod
    def get_seo_suggestions(cls, body_html: str):
        prompt = (
            f"Analyze the following HTML content and provide:\n"
            f"1. A compelling SEO Meta Description (max 160 chars).\n"
            f"2. Five relevant SEO Keywords (comma separated).\n"
            f"Format the response exactly as follows:\n"
            f"DESCRIPTION: [your description]\n"
            f"KEYWORDS: [keyword1, keyword2, ...]\n\n"
            f"CONTENT:\n{body_html[:3000]}"
        )
        return cls.generate_content(prompt)

    @classmethod
    def rewrite_text(cls, text: str, mode: str):
        if mode == "professional":
            prompt = f"Rewrite the following text to sound more professional, authoritative, and polished:\n\n{text}"
        elif mode == "shorter":
            prompt = f"Rewrite the following text to be more concise and shorter while keeping the main point:\n\n{text}"
        else:
            prompt = f"Rewrite the following text:\n\n{text}"
        
        return cls.generate_content(prompt)
