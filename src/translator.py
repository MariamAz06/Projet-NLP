# translator.py
# Fonctions de traduction

import re
import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config_ia import USE_OLLAMA
from src.prompts import PromptManager
from src.ollama_client import OllamaClient


class Translator:
    """Gestionnaire de traduction"""
    
    def __init__(self, ollama_client=None, translate_arabic=False):
        """
        Args:
            ollama_client: Instance de OllamaClient (créée si None)
            translate_arabic: Si True, active la traduction automatique de l'arabe
        """
        self.ollama_client = ollama_client or OllamaClient()
        self.translate_arabic = translate_arabic
    
    def translate_arabic_to_french(self, texte_arabe, max_length=2000):
        """Traduit le texte arabe en français pour améliorer l'extraction"""
        if not self.translate_arabic or not USE_OLLAMA:
            return texte_arabe
        
        if not texte_arabe or len(texte_arabe.strip()) < 20:
            return texte_arabe
        
        # Vérifier si c'est vraiment de l'arabe
        if not re.search(r'[\u0600-\u06FF]', texte_arabe):
            return texte_arabe
        
        # Limiter la longueur pour éviter les timeouts
        texte_a_traduire = texte_arabe[:max_length] if len(texte_arabe) > max_length else texte_arabe
        
        prompt = PromptManager.get_translation_prompt(texte_arabe, max_length)
        
        print(f"  [TRADUCTION] Traduction du texte arabe en cours...")
        traduction = self.ollama_client.call(prompt, max_retries=2, timeout=30)
        
        if traduction and len(traduction.strip()) > 20:
            print(f"  [TRADUCTION] Texte traduit avec succès ({len(traduction)} caractères)")
            return traduction.strip()
        else:
            print(f"  [TRADUCTION] Échec de la traduction, utilisation du texte original")
            return texte_arabe



