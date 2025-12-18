# ollama_client.py
# Client Ollama pour les appels à l'API Ollama

import requests
import time
from config.config_ia import USE_OLLAMA, OLLAMA_MODEL


class OllamaClient:
    """Client pour interagir avec l'API Ollama"""
    
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.ollama_model = self._detect_ollama_model() if USE_OLLAMA else None
    
    def _detect_ollama_model(self):
        """Détecte automatiquement le nom exact du modèle Ollama installé"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            
            # Chercher le modèle configuré (avec ou sans :latest)
            for name in model_names:
                # Correspondance exacte
                if name == OLLAMA_MODEL:
                    return name
                # Correspondance avec :latest
                if name == f"{OLLAMA_MODEL}:latest":
                    return name
                # Correspondance si le nom commence par le modèle configuré
                if name.startswith(f"{OLLAMA_MODEL}:"):
                    return name
            
            # Si aucun modèle trouvé, retourner le nom configuré (Ollama essaiera de le charger)
            return OLLAMA_MODEL
        except:
            # En cas d'erreur, retourner le nom configuré
            return OLLAMA_MODEL
    
    def call(self, prompt, max_retries=2, timeout=30):
        """
        Appelle l'API Ollama avec un prompt
        
        Args:
            prompt: Le prompt à envoyer à Ollama
            max_retries: Nombre maximum de tentatives en cas d'échec
            timeout: Timeout en secondes pour chaque tentative
        
        Returns:
            La réponse d'Ollama ou None en cas d'échec
        """
        if not USE_OLLAMA or not self.ollama_model:
            return None
        
        # Calculer num_predict basé sur la longueur du prompt (limiter pour la vitesse)
        prompt_length = len(prompt)
        max_tokens = min(int(prompt_length * 0.3), 200)  # Max 200 tokens pour la vitesse
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.ollama_url,
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,  # Limiter les tokens générés
                            "temperature": 0.3,  # Plus déterministe et rapide
                            "top_p": 0.9,  # Réduire l'espace de recherche
                            "top_k": 20,  # Limiter les choix
                            "repeat_penalty": 1.1  # Éviter les répétitions
                        }
                    },
                    timeout=timeout
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "").strip()
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    # Ne pas afficher de message pour chaque tentative (trop verbeux)
                    time.sleep(1)
                else:
                    # Message silencieux - ne pas bloquer l'exécution
                    return None
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    return None
            except Exception as e:
                # Ne pas afficher toutes les erreurs (trop verbeux)
                return None
        
        return None
    
    def is_available(self):
        """Vérifie si Ollama est accessible"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            response.raise_for_status()
            return True
        except:
            return False


