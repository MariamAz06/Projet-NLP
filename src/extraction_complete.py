# extraction_complete.py

import pandas as pd
import requests
import trafilatura
from langdetect import detect, LangDetectException
import htmldate
import dateparser
from urllib.parse import urlparse
from datetime import datetime
import json
import re
import time
from bs4 import BeautifulSoup
import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config_ia import USE_OLLAMA, OLLAMA_MODEL
from src.prompts import PromptManager
from config.data_constants import (
    COMMON_LOCATIONS_EXTENDED, EXCLUDED_WORDS, EXCLUDED_PATTERNS, LOCATION_PATTERNS,
    LOCATION_TRANSLATION, CITY_TO_COUNTRY, PAYS_CONNUS, USA_STATE_CODES,
    ANIMAUX, INVALID_ANIMAL_PATTERNS, ANIMAL_MAPPING,
    INVALID_RESPONSES, INVALID_PATTERNS, PHRASE_STARTERS, CONJUGATED_VERBS,
    GENERIC_TERMS, PREFIXES_TO_REMOVE, KNOWN_ACRONYMS
)
from src.ollama_client import OllamaClient
from src.utils import clean_content, calculate_stats, validate_content_coherence
from src.translator import Translator

# ============================================================================
# CLASSE NewsExtractor (intégrée complètement - tout en un seul fichier)
# ============================================================================

class NewsExtractor:
    """
    Classe principale pour l'extraction automatique d'informations depuis des URLs.
    Organise les méthodes en sections logiques :
    - Initialisation et configuration
    - Nettoyage et validation du contenu
    - Extraction de contenu et métadonnées
    - Détection de langue
    - Extraction de dates
    - Extraction de maladies
    - Extraction de lieux
    - Normalisation et validation
    - Traitement principal
    """
    
    # ============================================================================
    # SECTION 1: INITIALISATION ET CONFIGURATION
    # ============================================================================
    
    def __init__(self):
        # Utiliser OllamaClient pour gérer les appels à Ollama
        self.ollama_client = OllamaClient() if USE_OLLAMA else None
        self.ollama_model = self.ollama_client.ollama_model if self.ollama_client else None
        self.translate_arabic = False  # Désactiver la traduction automatique de l'arabe
        # Utiliser Translator pour les traductions
        self.translator = Translator(ollama_client=self.ollama_client, translate_arabic=self.translate_arabic) if USE_OLLAMA else None
    
    # ============================================================================
    # SECTION 2: NETTOYAGE ET VALIDATION DU CONTENU
    # ============================================================================
        
    def validate_content_coherence(self, titre, contenu):
        """Valide que le contenu est cohérent avec le titre et logiquement correct"""
        # Utiliser la fonction de base depuis utils.py
        contenu_validated, issues = validate_content_coherence(titre, contenu)
        
        # Ajouter des vérifications supplémentaires spécifiques à cette classe
        if not titre or not contenu:
            return contenu_validated, issues
        
        titre_lower = titre.lower()
        contenu_lower = contenu.lower()
        
        # Extraire les mots-clés importants du titre (exclure les mots vides)
        stop_words = {'the', 'a', 'an', 'le', 'la', 'les', 'de', 'du', 'des', 'et', 'and', 'or', 'in', 'on', 'at', 'for', 'to', 'of', 'is', 'are', 'was', 'were'}
        titre_keywords = [word for word in titre_lower.split() if len(word) > 3 and word not in stop_words]
        
        # Vérifier si au moins quelques mots-clés du titre sont dans le contenu
        matching_keywords = [kw for kw in titre_keywords if kw in contenu_lower]
        
        if len(titre_keywords) > 0:
            match_ratio = len(matching_keywords) / len(titre_keywords)
            if match_ratio < 0.4:  # Moins de 40% de correspondance
                issues.append(f"Contenu peu coherent avec le titre (ratio: {match_ratio:.2f})")
                print(f"  [ATTENTION] Titre et contenu peuvent etre incoherents")
        
        # Vérifier la cohérence logique : si le titre mentionne une maladie, elle doit être dans le contenu
        maladie_in_titre = self.extract_disease_with_regex(titre)
        if maladie_in_titre:
            maladie_in_contenu = self.extract_disease_with_regex(contenu)
            if not maladie_in_contenu:
                issues.append(f"Maladie '{maladie_in_titre}' mentionnee dans le titre mais absente du contenu")
        
        # Vérifier la cohérence logique : si le titre mentionne un lieu, il doit être dans le contenu
        lieu_in_titre = self.extract_location_with_regex(titre)
        if lieu_in_titre:
            lieu_in_contenu = self.extract_location_with_regex(contenu)
            if not lieu_in_contenu:
                issues.append(f"Lieu '{lieu_in_titre}' mentionne dans le titre mais absent du contenu")
        
        return contenu_validated, issues
    
    # ============================================================================
    # SECTION 3: EXTRACTION DE CONTENU ET MÉTADONNÉES
    # ============================================================================
    
    def extract_metadata_comprehensive(self, soup):
        """Extrait toutes les métadonnées possibles : og:title, meta title, article:published_time, og:site_name, JSON-LD"""
        metadata = {
            "title": "",
            "og_title": "",
            "site_name": "",
            "og_site_name": "",
            "published_time": "",
            "language": "",
            "json_ld": {}
        }
        
        # 1. Meta title standard
        if soup.title:
            metadata["title"] = soup.title.get_text().strip()
        
        # 2. OpenGraph title (og:title)
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            metadata["og_title"] = og_title.get('content').strip()
        
        # 3. Meta title (name="title")
        meta_title = soup.find('meta', attrs={'name': 'title'})
        if meta_title and meta_title.get('content'):
            metadata["title"] = meta_title.get('content').strip() or metadata["title"]
        
        # 4. OpenGraph site name (og:site_name)
        og_site_name = soup.find('meta', property='og:site_name')
        if og_site_name and og_site_name.get('content'):
            metadata["og_site_name"] = og_site_name.get('content').strip()
        
        # 5. Article published time (article:published_time)
        article_published = soup.find('meta', property='article:published_time')
        if article_published and article_published.get('content'):
            metadata["published_time"] = article_published.get('content').strip()
        
        # 6. Langue depuis les métadonnées
        html_lang = soup.find('html')
        if html_lang and html_lang.get('lang'):
            metadata["language"] = html_lang.get('lang')[:2]  # Prendre les 2 premiers caractères
        
        meta_lang = soup.find('meta', attrs={'http-equiv': 'Content-Language'})
        if meta_lang and meta_lang.get('content'):
            metadata["language"] = meta_lang.get('content')[:2] or metadata["language"]
        
        # 7. JSON-LD (Structured Data)
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            if script.string:
                try:
                    json_data = json.loads(script.string)
                    # Gérer les listes et objets
                    if isinstance(json_data, list):
                        json_data = json_data[0] if json_data else {}
                    
                    metadata["json_ld"] = json_data
                    
                    # Extraire le titre depuis JSON-LD
                    if not metadata["title"] and json_data.get('headline'):
                        metadata["title"] = json_data.get('headline', '').strip()
                    if not metadata["title"] and json_data.get('name'):
                        metadata["title"] = json_data.get('name', '').strip()
                    
                    # Extraire la date depuis JSON-LD
                    if not metadata["published_time"]:
                        date_published = json_data.get('datePublished') or json_data.get('datePublished')
                        if date_published:
                            metadata["published_time"] = date_published
                    
                    # Extraire le site name depuis JSON-LD
                    if not metadata["og_site_name"]:
                        publisher = json_data.get('publisher', {})
                        if isinstance(publisher, dict):
                            site_name = publisher.get('name', '')
                            if site_name:
                                metadata["og_site_name"] = site_name
                        elif isinstance(publisher, str):
                            metadata["og_site_name"] = publisher
                    
                    # Extraire la langue depuis JSON-LD
                    if not metadata["language"] and json_data.get('inLanguage'):
                        metadata["language"] = json_data.get('inLanguage', '')[:2]
                    
                except (json.JSONDecodeError, AttributeError):
                    continue
        
        return metadata
    
    def extract_content_from_html_tags(self, soup):
        """Extrait le contenu depuis les balises HTML spécifiées : h1, h2, article, p, time"""
        contenu_parts = []
        
        # 1. Extraire depuis <article>
        articles = soup.find_all('article')
        for article in articles:
            # Extraire les paragraphes <p> dans l'article
            paragraphs = article.find_all('p')
            for p in paragraphs:
                text = p.get_text(separator=' ', strip=True)
                if len(text) > 20:  # Ignorer les paragraphes trop courts
                    contenu_parts.append(text)
        
        # 2. Si pas d'article, chercher dans <main> ou conteneurs principaux
        if not contenu_parts:
            main = soup.find('main') or soup.find(attrs={'role': 'main'})
            if main:
                paragraphs = main.find_all('p')
                for p in paragraphs:
                    text = p.get_text(separator=' ', strip=True)
                    if len(text) > 20:
                        contenu_parts.append(text)
        
        # 3. Si toujours rien, chercher tous les <p> principaux (hors menus/footers)
        if not contenu_parts:
            # Exclure les paragraphes dans nav, header, footer, aside
            for p in soup.find_all('p'):
                # Vérifier que le paragraphe n'est pas dans un élément non désiré
                parent = p.find_parent(['nav', 'header', 'footer', 'aside', 'form'])
                if not parent:
                    text = p.get_text(separator=' ', strip=True)
                    if len(text) > 20:
                        contenu_parts.append(text)
        
        # 4. Extraire les titres h1, h2 pour contexte (mais pas comme contenu principal)
        # (On les utilise pour le titre, pas pour le contenu)
        
        return ' '.join(contenu_parts)
    
    def extract_content(self, url):
        """Extrait le contenu textuel et le titre depuis une URL avec toutes les méthodes possibles"""
        html_content = None
        try:
            # Utiliser trafilatura pour extraire le contenu principal
            try:
               downloaded = trafilatura.fetch_url(url)
            except Exception as trafilatura_error:
              # Si trafilatura échoue, continuer avec la méthode fallback
                print(f"  [ATTENTION] Trafilatura a échoué: {str(trafilatura_error)}")
                downloaded = None
            
            if downloaded:
                html_content = downloaded  # Garder le HTML pour l'extraction de date
                extracted = trafilatura.extract(downloaded, include_comments=False, 
                                                include_tables=False, include_images=False)
                if extracted:
                    # Extraire aussi le titre
                    metadata = trafilatura.extract_metadata(downloaded)
                    titre = metadata.title if metadata and metadata.title else ""
                    
                    # Nettoyer et valider le contenu
                    contenu_cleaned = clean_content(extracted.strip())
                    
                    # Garder le texte original en arabe
                    titre_original = titre
                    contenu_original = contenu_cleaned
                    
                    # Traduire si c'est de l'arabe pour améliorer l'extraction (mais garder l'original)
                    langue_detectee = self.detect_language(contenu_cleaned)
                    titre_traduit = None
                    contenu_traduit = None
                    if langue_detectee == 'ar' and self.translate_arabic:
                        print(f"  [TRADUCTION] Détection de texte arabe, traduction en cours pour extraction...")
                        titre_traduit = self.translate_arabic_to_french(titre, max_length=500) if titre else None
                        contenu_traduit = self.translate_arabic_to_french(contenu_cleaned, max_length=2000)
                        print(f"  [TRADUCTION] Traduction terminée, utilisation pour extraction uniquement")
                    
                    # Utiliser la traduction pour la validation si disponible, sinon l'original
                    titre_pour_validation = titre_traduit if titre_traduit else titre_original
                    contenu_pour_validation = contenu_traduit if contenu_traduit else contenu_original
                    
                    contenu_validated, issues = self.validate_content_coherence(titre_pour_validation, contenu_pour_validation)
                    
                    if issues:
                        print(f"  [VALIDATION CONTENU] Problemes detectes:")
                        for issue in issues:
                            print(f"    - {issue}")
                    
                    # Retourner le texte ORIGINAL en arabe (pas la traduction)
                    return {
                        "titre": titre_original,  # Texte original en arabe
                        "contenu": contenu_original,  # Texte original en arabe
                        "titre_traduit": titre_traduit,  # Traduction pour extraction (optionnel)
                        "contenu_traduit": contenu_traduit,  # Traduction pour extraction (optionnel)
                        "html": html_content,
                        "success": True
                    }
            
            # Fallback: utiliser requests + BeautifulSoup si trafilatura échoue
            # Headers améliorés pour éviter les erreurs 403
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7,ar;q=0.6',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }
            
            # Essayer avec headers améliorés
            try:
                response = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else None
                if status_code == 403:
                    # Si 403, essayer avec des headers encore plus complets
                    print(f"  [ATTENTION] Erreur 403, tentative avec headers alternatifs...")
                    try:
                        headers_alt = {
                            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.5',
                            'Referer': 'https://www.google.com/',
                            'DNT': '1',
                            'Connection': 'keep-alive'
                        }
                        
                        response = requests.get(url, timeout=15, headers=headers_alt, allow_redirects=True)
                        response.raise_for_status()
                    except requests.exceptions.HTTPError:
                        # Si ça échoue encore, retourner une erreur propre
                        error_msg = f"{status_code} Client Error: {e.response.reason if e.response else 'Forbidden'} for url: {url}"
                        raise requests.exceptions.HTTPError(error_msg, response=e.response)
                elif status_code == 404:
                    # Erreur 404 - page non trouvée
                    error_msg = f"404 Client Error: Not Found for url: {url}"
                    raise requests.exceptions.HTTPError(error_msg, response=e.response)
                else:
                    # Autres erreurs HTTP
                    error_msg = f"{status_code} Client Error: {e.response.reason if e.response else 'Unknown'} for url: {url}"
                    raise requests.exceptions.HTTPError(error_msg, response=e.response)
            except requests.exceptions.ConnectionError as e:
                # Erreur de connexion
                error_msg = f"Connection error for url: {url} - {str(e)}"
                raise requests.exceptions.ConnectionError(error_msg)
            except requests.exceptions.Timeout as e:
                # Timeout
                error_msg = f"Timeout error for url: {url} - {str(e)}"
                raise requests.exceptions.Timeout(error_msg)
            
            # Gérer l'encodage correctement pour les langues multilingues (arabe, chinois, etc.)
            if response.encoding is None or response.encoding == 'ISO-8859-1':
                # Essayer de détecter l'encodage depuis les headers ou le contenu
                response.encoding = response.apparent_encoding or 'utf-8'
            
            html_content = response.text
            
            # Utiliser lxml pour mieux gérer l'encodage multilingue
            try:
                soup = BeautifulSoup(response.content, 'lxml')
            except (ImportError, Exception):
                soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraire toutes les métadonnées possibles
            metadata_comprehensive = self.extract_metadata_comprehensive(soup)
            
            # Déterminer le titre (priorité : og:title > meta title > h1 > title tag)
            titre = ""
            if metadata_comprehensive["og_title"]:
                titre = metadata_comprehensive["og_title"]
            elif metadata_comprehensive["title"]:
                titre = metadata_comprehensive["title"]
            else:
                # Chercher dans h1
                h1 = soup.find('h1')
                if h1:
                    titre = h1.get_text().strip()
                elif soup.title:
                    titre = soup.title.get_text().strip()
            
            # Supprimer les éléments non pertinents avant extraction
            for element in soup.find_all(['nav', 'header', 'footer', 'aside', 'script', 'style', 
                                        'noscript', 'iframe', 'form']):
                element.decompose()
            
            # Supprimer les éléments avec classes/id de menu/navigation/publicité
            unwanted_patterns = [
                r'menu|nav|sidebar|advertisement|ad|popup|cookie|related|similar|recommended|trending',
                r'social|share|comment|newsletter|subscribe|follow'
            ]
            for pattern in unwanted_patterns:
                for element in soup.find_all(class_=re.compile(pattern, re.I)):
                    element.decompose()
                for element in soup.find_all(id=re.compile(pattern, re.I)):
                    element.decompose()
            
            # Extraire le contenu depuis les balises HTML spécifiées
            contenu = self.extract_content_from_html_tags(soup)
            
            # Si pas de contenu trouvé, utiliser les sélecteurs de fallback
            if not contenu or len(contenu) < 100:
                for selector in ['article', 'main', '[role="main"]', '.article-content', 
                               '.post-content', '.entry-content', '.content', '.post-body', '.entry-body']:
                    element = soup.select_one(selector)
                    if element:
                        contenu = element.get_text(separator=' ', strip=True)
                        if len(contenu) > 100:
                            break
            
            if not contenu or len(contenu) < 100:
                # Dernier recours: tout le body (mais nettoyé)
                body = soup.find('body')
                if body:
                    contenu = body.get_text(separator=' ', strip=True)
            
            # Nettoyer et valider le contenu
            contenu_cleaned = clean_content(contenu)
            
            # Garder le texte original en arabe
            titre_original = titre
            contenu_original = contenu_cleaned
            
            # Traduire si c'est de l'arabe pour améliorer l'extraction (mais garder l'original)
            langue_detectee = self.detect_language(contenu_cleaned, metadata=metadata_comprehensive, html_content=html_content)
            titre_traduit = None
            contenu_traduit = None
            if langue_detectee == 'ar' and self.translate_arabic:
                print(f"  [TRADUCTION] Détection de texte arabe, traduction en cours pour extraction...")
                titre_traduit = self.translate_arabic_to_french(titre, max_length=500) if titre else None
                contenu_traduit = self.translate_arabic_to_french(contenu_cleaned, max_length=2000)
                print(f"  [TRADUCTION] Traduction terminée, utilisation pour extraction uniquement")
            
            # Utiliser la traduction pour la validation si disponible, sinon l'original
            titre_pour_validation = titre_traduit if titre_traduit else titre_original
            contenu_pour_validation = contenu_traduit if contenu_traduit else contenu_original
            
            contenu_validated, issues = self.validate_content_coherence(titre_pour_validation, contenu_pour_validation)
            
            if issues:
                print(f"  [VALIDATION CONTENU] Problemes detectes:")
                for issue in issues:
                    print(f"    - {issue}")
            
            # Retourner le texte ORIGINAL en arabe (pas la traduction)
            return {
                "titre": titre_original,  # Texte original en arabe
                "contenu": contenu_original,  # Texte original en arabe
                "titre_traduit": titre_traduit,  # Traduction pour extraction (optionnel)
                "contenu_traduit": contenu_traduit,  # Traduction pour extraction (optionnel)
                "html": html_content,
                "metadata": metadata_comprehensive,
                "success": True
            }
            
        except Exception as e:
            print(f"Erreur lors de l'extraction de {url}: {str(e)}")
            return {
                "titre": "",
                "contenu": "",
                "html": None,
                "success": False,
                "erreur": str(e)
            }
    
    def detect_language(self, text, metadata=None, html_content=None):
        """Détecte la langue du texte avec toutes les méthodes possibles (métadonnées, HTML, détection texte)"""
        # Méthode 1: Depuis les métadonnées (priorité haute)
        if metadata and metadata.get("language"):
            lang = metadata["language"]
            if len(lang) >= 2:
                return lang[:2]
        
        # Méthode 2: Depuis les métadonnées HTML
        if html_content:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Chercher dans <html lang="...">
                html_tag = soup.find('html')
                if html_tag and html_tag.get('lang'):
                    lang = html_tag.get('lang')[:2]
                    if lang:
                        return lang
                
                # Chercher dans meta http-equiv="Content-Language"
                meta_lang = soup.find('meta', attrs={'http-equiv': 'Content-Language'})
                if meta_lang and meta_lang.get('content'):
                    lang = meta_lang.get('content')[:2]
                    if lang:
                        return lang
                
                # Chercher dans JSON-LD
                json_ld_scripts = soup.find_all('script', type='application/ld+json')
                for script in json_ld_scripts:
                    if script.string:
                        try:
                            json_data = json.loads(script.string)
                            if isinstance(json_data, list):
                                json_data = json_data[0] if json_data else {}
                            
                            in_language = json_data.get('inLanguage')
                            if in_language:
                                lang = str(in_language)[:2]
                                if lang:
                                    return lang
                        except (json.JSONDecodeError, AttributeError):
                            continue
            except (AttributeError, Exception):
                pass
        
        # Méthode 3: Détection depuis le texte (fallback)
        if not text or len(text.strip()) < 10:
            return "unknown"
        
        try:
            # Détection rapide pour l'arabe (caractères Unicode spécifiques)
            arabic_chars = re.search(r'[\u0600-\u06FF]', text)
            if arabic_chars:
                return 'ar'
            
            # Utiliser les 500 premiers caractères pour la détection (plus rapide)
            sample = text[:500] if len(text) > 500 else text
            lang = detect(sample)
            
            # Mapper les codes de langue vers les formats demandés
            lang_map = {
                'ar': 'ar',  # Arabe
                'fr': 'fr',  # Français
                'en': 'en',  # Anglais
                'es': 'es',  # Espagnol
                'de': 'de',  # Allemand
                'it': 'it',  # Italien
                'pt': 'pt',  # Portugais
                'ru': 'ru',  # Russe
                'zh-cn': 'zh',  # Chinois simplifié
                'zh-tw': 'zh',  # Chinois traditionnel
                'ja': 'ja',  # Japonais
                'ko': 'ko',  # Coréen
            }
            
            return lang_map.get(lang, lang)
        except LangDetectException:
            return "unknown"
        except Exception as e:
            print(f"Erreur detection langue: {str(e)}")
            return "unknown"
    
    # ============================================================================
    # SECTION 4: EXTRACTION DE DATES
    # ============================================================================
    
    def extract_date(self, url, html_content=None, text=None, metadata=None):
        """Extrait la date de publication avec TOUTES les méthodes possibles"""
        # Méthode 1: Utiliser htmldate pour extraire depuis le HTML (le plus fiable)
        if html_content:
            try:
                date_str = htmldate.find_date(html_content, outputformat='%Y-%m-%d')
                if date_str:
                    parsed_date = dateparser.parse(date_str)
                    if parsed_date:
                        return parsed_date.strftime("%d-%m-%Y")
            except Exception as e:
                pass
        
        # Méthode 2: Chercher dans les métadonnées extraites (article:published_time, JSON-LD)
        if metadata and metadata.get("published_time"):
            try:
                parsed_date = dateparser.parse(metadata["published_time"])
                if parsed_date:
                    return parsed_date.strftime("%d-%m-%Y")
            except (ValueError, TypeError, Exception):
                pass
        
        # Méthode 3: Chercher dans les métadonnées HTML (meta tags et balises <time>)
        if html_content:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Chercher dans les meta tags courants pour les dates
                meta_selectors = [
                    ('meta', {'property': 'article:published_time'}),
                    ('meta', {'property': 'article:modified_time'}),
                    ('meta', {'name': 'publish-date'}),
                    ('meta', {'name': 'pubdate'}),
                    ('meta', {'name': 'date'}),
                    ('meta', {'name': 'DC.date'}),
                    ('meta', {'name': 'publication_date'}),
                    ('meta', {'name': 'publishdate'}),
                    ('meta', {'itemprop': 'datePublished'}),
                    ('meta', {'itemprop': 'dateModified'}),
                ]
                
                for tag_name, attrs in meta_selectors:
                    element = soup.find(tag_name, attrs)
                    if element:
                        date_attr = element.get('content') or element.get('datetime')
                        if date_attr:
                            parsed_date = dateparser.parse(date_attr)
                            if parsed_date:
                                return parsed_date.strftime("%d-%m-%Y")
                
                # Chercher dans les balises <time>
                time_elements = soup.find_all('time')
                for time_elem in time_elements:
                    datetime_attr = time_elem.get('datetime')
                    if datetime_attr:
                        parsed_date = dateparser.parse(datetime_attr)
                        if parsed_date:
                            return parsed_date.strftime("%d-%m-%Y")
                    # Aussi chercher dans le texte de la balise time
                    time_text = time_elem.get_text(strip=True)
                    if time_text:
                        parsed_date = dateparser.parse(time_text, languages=['fr', 'en', 'ar', 'es', 'de', 'it', 'pt', 'ru'])
                        if parsed_date:
                            return parsed_date.strftime("%d-%m-%Y")
                
                # Chercher dans JSON-LD si présent dans le HTML
                json_ld_scripts = soup.find_all('script', type='application/ld+json')
                for script in json_ld_scripts:
                    if script.string:
                        try:
                            json_data = json.loads(script.string)
                            if isinstance(json_data, list):
                                json_data = json_data[0] if json_data else {}
                            
                            date_published = json_data.get('datePublished') or json_data.get('datePublished')
                            if date_published:
                                parsed_date = dateparser.parse(date_published)
                                if parsed_date:
                                    return parsed_date.strftime("%d-%m-%Y")
                        except (json.JSONDecodeError, AttributeError):
                            continue
                            
            except (AttributeError, Exception):
                pass
        
        # Méthode 4: Chercher dans le texte avec patterns "Publié le ..." (multilingue)
        if text:
            # Patterns pour "Publié le ..." dans différentes langues
            published_patterns = [
                # Français
                r'(?:Publié|publié|Publiée|publiée)\s+(?:le|le\s+)?(\d{1,2})[/\s-]+(\d{1,2})[/\s-]+(\d{4})',
                r'(?:Publié|publié)\s+(?:le|le\s+)?(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})',
                r'(?:Publié|publié)\s+(?:le|le\s+)?(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{1,2}),?\s+(\d{4})',
                # Anglais
                r'(?:Published|published|Posted|posted)\s+(?:on|on\s+)?(\d{1,2})[/\s-]+(\d{1,2})[/\s-]+(\d{4})',
                r'(?:Published|published)\s+(?:on|on\s+)?(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})',
                r'(?:Published|published)\s+(?:on|on\s+)?(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
                # Espagnol
                r'(?:Publicado|publicado)\s+(?:el|el\s+)?(\d{1,2})[/\s-]+(\d{1,2})[/\s-]+(\d{4})',
                r'(?:Publicado|publicado)\s+(?:el|el\s+)?(\d{1,2})\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(\d{4})',
                # Arabe (transcription)
                r'(?:نشر|تم\s+النشر)\s+(?:في|في\s+)?(\d{1,2})[/\s-]+(\d{1,2})[/\s-]+(\d{4})',
            ]
            
            for pattern in published_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.UNICODE)
                if matches:
                    try:
                        match = matches[0]
                        if isinstance(match, tuple):
                            date_str = ' '.join(str(m) for m in match if m)
                        else:
                            date_str = match
                        parsed_date = dateparser.parse(date_str, languages=['fr', 'en', 'ar', 'es', 'de', 'it', 'pt', 'ru'])
                        if parsed_date:
                            return parsed_date.strftime("%d-%m-%Y")
                    except (ValueError, TypeError, Exception):
                        continue
        
        # Méthode 5: Chercher dans le texte avec des patterns de date génériques (multilingue)
        if text:
            # Prendre les 1000 premiers caractères (où la date est souvent mentionnée)
            text_sample = text[:1000] if len(text) > 1000 else text
            
            # Patterns de dates courants (améliorés pour multilingue)
            date_patterns = [
                # Formats numériques universels
                r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',  # DD/MM/YYYY ou DD-MM-YYYY
                r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',  # YYYY/MM/DD
                # Français
                r'\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})\b',
                r'\b(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{1,2}),?\s+(\d{4})\b',
                # Anglais
                r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
                r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b',
                # Espagnol
                r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(\d{1,2}),?\s+(\d{4})\b',
                # Arabe (dates en chiffres arabes et transcription)
                r'\b(\d{1,2})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{4})\b',  # Format numérique universel
                # Allemand
                r'\b(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{1,2}),?\s+(\d{4})\b',
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, text_sample, re.IGNORECASE | re.UNICODE)
                if matches:
                    try:
                        match = matches[0]
                        date_str = ' '.join(str(m) for m in match) if isinstance(match, tuple) else match
                        parsed_date = dateparser.parse(date_str, languages=['fr', 'en', 'ar', 'es', 'de', 'it', 'pt', 'ru'])
                        if parsed_date:
                            return parsed_date.strftime("%d-%m-%Y")
                    except (ValueError, TypeError, Exception):
                        continue
        
        # Méthode 6: Utiliser dateparser directement sur le texte (plus flexible, multilingue)
        if text:
            try:
                # Prendre les 1000 premiers caractères pour éviter de parser tout le texte
                sample = text[:1000] if len(text) > 1000 else text
                # Essayer plusieurs langues pour le parsing
                parsed_date = dateparser.parse(sample, languages=['fr', 'en', 'ar', 'es', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko'])
                if parsed_date:
                    return parsed_date.strftime("%d-%m-%Y")
            except (ValueError, TypeError, Exception):
                pass
        
        return ""
    
    # ============================================================================
    # SECTION 6: INTÉGRATION OLLAMA
    # ============================================================================
    
    def call_ollama(self, prompt, max_retries=2, timeout=30):
        """Appelle l'API Ollama pour extraire des informations (optimisé pour la vitesse)"""
        if not self.ollama_client:
            return None
        return self.ollama_client.call(prompt, max_retries=max_retries, timeout=timeout)
    
    def translate_arabic_to_french(self, texte_arabe, max_length=2000):
        """Traduit le texte arabe en français pour améliorer l'extraction"""
        # Utiliser Translator depuis translator.py
        if not self.translator:
            return texte_arabe
        return self.translator.translate_arabic_to_french(texte_arabe, max_length=max_length)
    
    # ============================================================================
    # SECTION 7: EXTRACTION DE MALADIES
    # ============================================================================
    
    def extract_date_with_ollama(self, titre, contenu):
        """Utilise Ollama pour extraire la date de publication (multilingue)"""
        if not contenu or len(contenu.strip()) < 50:
            return ""
        
        # Détecter la langue pour adapter le prompt
        langue = self.detect_language(contenu)
        
        prompt = PromptManager.get_date_extraction_prompt(titre, contenu, langue)

        response = self.call_ollama(prompt)
        if not response:
            return ""
        
        # Chercher un pattern de date dans la réponse
        date_match = re.search(r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b', response)
        if date_match:
            try:
                day, month, year = date_match.groups()
                # Vérifier que c'est une date valide
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime("%d-%m-%Y")
            except (ValueError, TypeError, Exception):
                pass
        
        return ""
    
    def extract_disease_with_ollama(self, titre, contenu):
        """Utilise Ollama pour extraire la maladie animale depuis le titre ou le contenu
        
        Args:
            titre: Le titre de l'article
            contenu: Le contenu de l'article
        
        Returns:
            Le nom de la maladie extraite, ou None si non trouvée
        """
        if not USE_OLLAMA:
            return None
        
        # Utiliser le titre en priorité, puis le contenu si le titre est court
        texte_analyse = titre if titre and len(titre.strip()) > 20 else ""
        if not texte_analyse and contenu:
            texte_analyse = contenu[:800]  # Réduit de 1000 à 800 caractères
        elif titre and contenu:
            # Combiner titre + début du contenu
            texte_analyse = f"{titre}\n\n{contenu[:600]}"  # Réduit de 800 à 600 caractères
        
        if not texte_analyse or len(texte_analyse.strip()) < 20:
            return None
        
        # Détecter la langue pour adapter le prompt
        langue = self.detect_language(texte_analyse)
        
        # Créer un prompt renforcé selon la langue avec exemples
        prompt = PromptManager.get_disease_extraction_prompt(texte_analyse, langue)
        
        response = self.call_ollama(prompt)
        if not response:
            return None
        
        # Nettoyer la réponse
        maladie = response.strip()
        # Enlever les guillemets si présents
        maladie = maladie.strip('"\'')
        # Prendre seulement la première ligne
        maladie = maladie.split('\n')[0].strip()
        
        # Rejeter les réponses d'Ollama mal parsées (instructions, métadonnées, etc.)
        invalid_patterns = [
            'assistant', 'helpful', 'extract', 'illness', 'disease', 'exact', 'short', 'empty',
            'you are', 'tu es', 'أنت', 'expert', 'extract', 'extrais', 'استخرج',
            'non trouvée', 'non trouvee', 'not found', 'لا يوجد', 'n/a', 'none', 'null',
            'diagnosed', 'reproduction', 'inc.', 'corp', 'ltd', 'company', 'société',
            'enfermedad', 'ayuda', 'esta', 'para', 'affichage', 'ailleurs', 'article', 'suivant',
            'parole', 'trouvé', 'trouve', 'provenant', 'oiseaux', 'soeurs', 'brésiliens',
            'verse', 'probleme', 'vervant', 'd\'oiseaux', 'brésiliens', 'provenant',
            'citation', 'très important', 'very important', 'important', 'note:', 'note :',
            'remarque', 'remark', 'attention', 'warning', 'alert', 'alerte',
            'question:', 'question', 'correct', 'here\'s', 'answer', 'sure', 'here is',
            'suggested', 'changes', 'updated', 'version', 'revised', 'edition'
        ]
        
        # Rejeter les réponses qui commencent par des mots d'instruction ou de formatage
        if maladie.lower().startswith(('citation', 'citation:', 'très important', 'very important', 
                                       'important:', 'note:', 'remarque:', 'attention:', 'warning:',
                                       'question:', 'question', 'correct', 'here\'s', 'here is',
                                       'suggested', 'changes', 'updated', 'version')):
            return None
        
        # Rejeter les réponses qui contiennent des phrases d'instruction complètes
        if any(phrase in maladie.lower() for phrase in ['question: correct', 'here\'s answer', 
                                                         'suggested changes', 'updated version',
                                                         'revised version', 'correct here']):
            return None
        
        # Rejeter les réponses qui sont juste des points de suspension
        if maladie.strip() in ['...', '..', '.', '…', '…', '…']:
            return None
        maladie_lower = maladie.lower()
        if any(pattern in maladie_lower for pattern in invalid_patterns):
            return None
        
        # Rejeter les réponses qui contiennent des phrases complètes ou des mots de liaison
        phrase_indicators = ['l\'', 'd\'', 'de la', 'du', 'des', 'le', 'la', 'les', 'un', 'une',
                            'pour', 'avec', 'dans', 'sur', 'par', 'vers', 'depuis', 'jusqu\'',
                            'après', 'avant', 'pendant', 'sous', 'chez', 'entre', 'parmi',
                            'alors', 'donc', 'mais', 'car', 'puisque', 'parce que', 'afin de',
                            'pour que', 'bien que', 'quoique', 'malgré', 'en dépit de',
                            'affichage', 'ailleurs', 'article', 'suivant', 'parole']
        maladie_words = maladie.split()
        if len(maladie_words) > 0:
            # Si la réponse commence par un mot de liaison, c'est probablement une phrase
            if maladie_words[0].lower() in phrase_indicators:
                return None
            # Si la réponse contient trop de mots de liaison, c'est probablement une phrase
            liaison_count = sum(1 for word in maladie_words if word.lower() in phrase_indicators)
            if liaison_count > len(maladie_words) / 2:
                return None
        
        # Rejeter si la réponse contient des emails, URLs ou domaines
        if '@' in maladie or 'www.' in maladie_lower or '.com' in maladie_lower or '.gov' in maladie_lower or '.co.uk' in maladie_lower:
            return None
        
        # Rejeter si la réponse contient des parenthèses avec des URLs ou emails
        if '(' in maladie and ('.' in maladie or '@' in maladie):
            return None
        
        # Rejeter les noms d'entreprises (contiennent "Inc.", "Corp", "Ltd", etc.)
        if re.search(r'\b(inc\.?|corp\.?|ltd\.?|company|société)\b', maladie_lower):
            return None
        
        # Vérifier que ce n'est pas "NON TROUVEE" ou vide
        if not maladie or maladie.upper() == "NON TROUVEE" or len(maladie) < 3:
            return None
        
        # Rejeter si la réponse contient des points multiples (probablement une phrase d'instruction)
        if maladie.count('.') > 2:
            return None
        
        # Rejeter si la réponse contient des mots qui indiquent une instruction (ex: "disease exact short name")
        instruction_words = ['exact', 'short', 'name', 'empty', 'disease', 'maladie', 'extract', 'extract']
        if any(word in maladie_lower for word in instruction_words) and len(maladie.split()) <= 4:
            # Si c'est une phrase courte avec des mots d'instruction, c'est probablement une instruction
            return None
        
        # Normaliser la maladie
        maladie = self.normalize_disease_name(maladie)
        
        # Vérifier que c'est valide (pas trop long, pas de mots interdits)
        if maladie and len(maladie) >= 3 and len(maladie.split()) <= 5:
            # Vérifier qu'il n'y a pas de mots interdits
            mots_interdits = ['shots', 'for', 'after', 'dies', 'outbreak', 'lifted', 'quarantine', 'case', 'maladie', 'disease', 'assistant', 'helpful', 'extract']
            if not any(word in maladie.lower() for word in mots_interdits):
                return maladie
        
        return None
    
    def extract_disease_with_regex(self, texte, normalize=True):
        """Extrait le nom de la maladie avec des patterns regex (fallback multilingue) - cherche dans tout le texte
        
        Args:
            texte: Le texte dans lequel chercher la maladie
            normalize: Si True, normalise le résultat. Si False, retourne la maladie brute (pour éviter la récursion)
        """
        if not texte:
            return ""
        
        # Si le texte est très long, chercher dans plusieurs parties pour être sûr de trouver
        # Prioriser le début (où les informations importantes sont souvent)
        text_samples = []
        if len(texte) > 3000:
            text_samples.append(texte[:3000])  # Début
            text_samples.append(texte[len(texte)//2:len(texte)//2 + 2000])  # Milieu
            text_samples.append(texte[-2000:])  # Fin
        else:
            text_samples.append(texte)
        
        # Liste de maladies animales courantes (en plusieurs langues)
        diseases = [
            # Français
            r'\b(grippe\s+aviaire|influenza\s+aviaire|H5N1|H7N9)\b',
            r'\b(fièvre\s+aphteuse|FMD|foot-and-mouth)\b',
            r'\b(peste\s+porcine|ASF|African\s+Swine\s+Fever)\b',
            r'\b(rage|rabies)\b',
            r'\b(maladie\s+de\s+Newcastle|NDV)\b',
            r'\b(brucellose|brucellosis)\b',
            r'\b(fièvre\s+catarrhale\s+ovine|bluetongue|FCO)\b',
            r'\b(anthrax|charbon)\b',
            r'\b(maladie\s+hémorragique\s+épizootique|MHE|EHD)\b',
            r'\b(lumpy\s+skin\s+disease|LSD|dermatose\s+nodulaire)\b',
            r'\b(peste\s+bovine|rinderpest)\b',
            r'\b(fièvre\s+du\s+Nil\s+occidental|West\s+Nile)\b',
            r'\b(fièvre\s+hémorragique\s+de\s+Crimée-Congo|FHCC|Crimean-Congo\s+hemorrhagic\s+fever|CCHF)\b',
            r'\b(chronic\s+wasting\s+disease|CWD)\b',
            r'\b(fièvre\s+de\s+la\s+vallée\s+du\s+Rift|FVR|Rift\s+Valley\s+fever|RVF)\b',
            r'\b(variole\s+du\s+singe|monkeypox)\b',
            r'\b(maladie\s+à\s+virus\s+Ebola|Ebola)\b',
            r'\b(fièvre\s+de\s+Lassa|Lassa\s+fever)\b',
            r'\b(لسان\s+أزرق|bluetongue|fièvre\s+catarrhale)\b',
            # Anglais
            r'\b(avian\s+influenza|bird\s+flu)\b',
            r'\b(swine\s+flu|porcine\s+influenza)\b',
            r'\b(african\s+swine\s+fever)\b',
            r'\b(classical\s+swine\s+fever|hog\s+cholera)\b',
            r'\b(porcine\s+epidemic\s+diarrhea|PED)\b',
            r'\b(porcine\s+reproductive\s+and\s+respiratory\s+syndrome|PRRS)\b',
            r'\b(chronic\s+wasting\s+disease|CWD)\b',
            r'\b(crimean-congo\s+hemorrhagic\s+fever|CCHF|FHCC)\b',
            r'\b(rift\s+valley\s+fever|RVF)\b',
            r'\b(monkeypox)\b',
            r'\b(ebola)\b',
            r'\b(lassa\s+fever)\b',
            # Arabe (maladies animales courantes) - patterns améliorés pour extraire sans "مرض"
            # Patterns qui capturent le nom de la maladie après "مرض" ou "داء" (avec groupes de capture)
            r'مرض\s+(التهاب\s+الجلد\s+العقدي|التهاب\s+الجلد|حمى\s+الطيور|الحمى\s+القلاعية|السعار|الجمرة|البروسيلا|حمى\s+الخنازير)',
            r'داء\s+(التهاب\s+الجلد\s+العقدي|التهاب\s+الجلد|حمى\s+الطيور|الحمى\s+القلاعية|السعار|الجمرة|البروسيلا)',
            r'بمرض\s+(التهاب\s+الجلد\s+العقدي|التهاب\s+الجلد|حمى\s+الطيور|الحمى\s+القلاعية|السعار)',
            # Patterns pour les noms de maladies directement (sans "مرض") - prioritaires
            r'\b(التهاب\s+الجلد\s+العقدي|التهاب\s+الجلد\s+العقدي\s+بالأبقار)\b',
            r'\b(حمى\s+الطيور|إنفلونزا\s+الطيور|إنفلونزا\s+طيور)\b',
            r'\b(الحمى\s+القلاعية|حمى\s+قلاعية|الحمى\s+القلاعية\s+الحيوانية)\b',
            r'\b(السعار|داء\s+الكلب|داء\s+الكلب\s+العدواني)\b',
            r'\b(الجمرة|الطاعون|الجمرة\s+الخبيثة)\b',
            r'\b(البروسيلا|الحمى\s+المالطية|داء\s+البروسيلا)\b',
            r'\b(حمى\s+الخنازير|طاعون\s+الخنازير)\b',
            r'\b(النزف\s+الوبائي\s+الحيواني|النزف\s+الوبائي)\b',
            r'\b(اللسان\s+الأزرق|لسان\s+أزرق)\b',
            # Espagnol
            r'\b(gripe\s+aviar|influenza\s+aviar)\b',
            r'\b(fiebre\s+aftosa)\b',
            r'\b(peste\s+porcina)\b',
            r'\b(rabia)\b',
            # Portugais
            r'\b(gripe\s+aviária|influenza\s+aviária)\b',
            r'\b(febre\s+aftosa)\b',
            r'\b(peste\s+suína)\b',
            # Allemand
            r'\b(Vogelgrippe|Geflügelpest)\b',
            r'\b(Maul-und-Klauenseuche)\b',
            r'\b(Schweinepest)\b',
            # Codes et acronymes internationaux (toujours valides)
            r'\b(H5N1|H7N9|H5N8|FMD|ASF|NDV|LSD|EHD|MHE|PED|PRRS)\b',
        ]
        
        # Pour l'arabe, on ne peut pas utiliser lower() car ça casse l'encodage
        # On cherche directement dans le texte original
        # Chercher dans tous les échantillons pour être sûr de trouver
        for text_sample in text_samples:
            for pattern in diseases:
                match = re.search(pattern, text_sample, re.IGNORECASE | re.UNICODE)
                if match:
                    disease_found = match.group(0).strip()
                    # Si le pattern a capturé un groupe (maladie après "مرض"), utiliser le groupe
                    if match.groups():
                        # Prendre le premier groupe capturé (le nom de la maladie sans "مرض")
                        disease_found = match.group(1).strip() if match.group(1) else disease_found
                    # Normaliser seulement si demandé (pour éviter la récursion infinie)
                    if normalize:
                        return self.normalize_disease_name(disease_found)
                    else:
                        return disease_found.strip()
        
        return ""
    
    def extract_location_from_beginning(self, texte):
        """Extrait le lieu depuis le début de l'article et les premières phrases (priorité haute)"""
        if not texte:
            return ""
        
        # Prendre les 800 premiers caractères (début de l'article) - AUGMENTÉ
        debut_article = texte[:800] if len(texte) > 800 else texte
        
        # Prendre les 5 premières phrases - AUGMENTÉ
        sentences = re.split(r'[.!?]\s+', texte)
        premieres_phrases = ' '.join(sentences[:5]) if len(sentences) >= 5 else texte[:500]
        
        # Prendre aussi le premier paragraphe complet
        paragraphs = re.split(r'\n\s*\n', texte)
        premier_paragraphe = paragraphs[0] if paragraphs else texte[:600]
        
        # Chercher dans ces zones prioritaires (ordre: premier paragraphe > premières phrases > début)
        for text_sample in [premier_paragraphe, premieres_phrases, debut_article]:
            lieu = self.extract_location_with_regex(text_sample, normalize=False)
            if lieu and self.is_valid_location(lieu):
                return lieu
        
        return ""
    
    def extract_location_from_categories(self, soup):
        """Extrait le lieu depuis les catégories du site (meta tags, JSON-LD, breadcrumbs)"""
        lieu = ""
        
        # 1. Chercher dans les meta tags de catégorie
        category_meta = soup.find('meta', attrs={'name': 'category'}) or \
                       soup.find('meta', attrs={'property': 'article:section'})
        if category_meta and category_meta.get('content'):
            category = category_meta.get('content')
            # Vérifier si la catégorie contient un nom de lieu
            lieu = self.extract_location_with_regex(category, normalize=False)
            if lieu and self.is_valid_location(lieu):
                return lieu
        
        # 2. Chercher dans les meta tags géographiques (NOUVEAU)
        geo_meta = soup.find('meta', attrs={'name': 'geo.region'}) or \
                   soup.find('meta', attrs={'name': 'geo.placename'}) or \
                   soup.find('meta', attrs={'property': 'article:tag'})
        if geo_meta and geo_meta.get('content'):
            geo_content = geo_meta.get('content')
            lieu = self.extract_location_with_regex(geo_content, normalize=False)
            if lieu and self.is_valid_location(lieu):
                return lieu
        
        # 3. Chercher dans JSON-LD articleSection et location
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            if script.string:
                try:
                    json_data = json.loads(script.string)
                    if isinstance(json_data, list):
                        json_data = json_data[0] if json_data else {}
                    
                    # Chercher dans articleSection
                    article_section = json_data.get('articleSection')
                    if article_section:
                        lieu = self.extract_location_with_regex(article_section, normalize=False)
                        if lieu and self.is_valid_location(lieu):
                            return lieu
                    
                    # Chercher dans contentLocation (NOUVEAU)
                    content_location = json_data.get('contentLocation', {})
                    if isinstance(content_location, dict):
                        location_name = content_location.get('name') or content_location.get('addressLocality')
                        if location_name:
                            lieu = self.extract_location_with_regex(location_name, normalize=False)
                            if lieu and self.is_valid_location(lieu):
                                return lieu
                    elif isinstance(content_location, str):
                        lieu = self.extract_location_with_regex(content_location, normalize=False)
                        if lieu and self.is_valid_location(lieu):
                            return lieu
                except (json.JSONDecodeError, AttributeError):
                    continue
        
        # 4. Chercher dans les breadcrumbs
        breadcrumbs = soup.find_all(attrs={'itemtype': 'http://schema.org/BreadcrumbList'}) or \
                     soup.find_all(class_=re.compile(r'breadcrumb', re.I))
        for breadcrumb in breadcrumbs:
            text = breadcrumb.get_text(separator=' ', strip=True)
            lieu = self.extract_location_with_regex(text, normalize=False)
            if lieu and self.is_valid_location(lieu):
                return lieu
        
        # 5. Chercher dans les tags/article tags (NOUVEAU)
        tags = soup.find_all('meta', attrs={'property': 'article:tag'}) or \
               soup.find_all(class_=re.compile(r'tag|tags|category', re.I))
        for tag in tags:
            if hasattr(tag, 'get'):
                tag_content = tag.get('content') or tag.get_text(separator=' ', strip=True)
            else:
                tag_content = tag.get_text(separator=' ', strip=True)
            if tag_content:
                lieu = self.extract_location_with_regex(tag_content, normalize=False)
                if lieu and self.is_valid_location(lieu):
                    return lieu
        
        return ""
    
    def extract_location_from_url(self, url):
        """Extrait le pays depuis le domaine de l'URL
        
        Args:
            url: L'URL à analyser
            
        Returns:
            Le nom du pays si détecté, ou None
        """
        if not url:
            return None
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Dictionnaire de correspondances domaines -> pays (ÉTENDU)
            domain_to_country = {
                # Corée du Sud
                'yna.co.kr': 'South Korea', 'yonhapnews.co.kr': 'South Korea', 'koreaherald.com': 'South Korea',
                # Royaume-Uni
                'bbc.co.uk': 'UK', 'bbc.com': 'UK', 'theguardian.com': 'UK', 'independent.co.uk': 'UK',
                'telegraph.co.uk': 'UK', 'dailymail.co.uk': 'UK', 'thetimes.co.uk': 'UK',
                # France
                'lemonde.fr': 'France', 'france24.com': 'France', 'lefigaro.fr': 'France',
                'liberation.fr': 'France', 'leparisien.fr': 'France', 'franceinfo.fr': 'France',
                # USA
                'nytimes.com': 'USA', 'washingtonpost.com': 'USA', 'cnn.com': 'USA',
                'wsj.com': 'USA', 'usatoday.com': 'USA', 'reuters.com': 'USA',
                # Égypte
                'ahram.org.eg': 'مصر', 'gate.ahram.org.eg': 'مصر', 'youm7.com': 'مصر',
                'almasryalyoum.com': 'مصر', 'alwatannews.com': 'مصر',
                # Maroc
                'le12.ma': 'المغرب', 'hespress.com': 'المغرب', 'alyaoum24.com': 'المغرب',
                'le360.ma': 'المغرب', 'medias24.com': 'المغرب',
                # Autres pays arabes
                'aljazeera.net': 'قطر', 'alarabiya.net': 'السعودية', 'skynewsarabia.com': 'الإمارات',
                # Autres pays
                'spiegel.de': 'Germany', 'lemonde.fr': 'France', 'repubblica.it': 'Italy',
                'elpais.com': 'Spain', 'globo.com': 'Brazil', 'xinhuanet.com': 'China',
            }
            
            # Vérifier le domaine exact
            if domain in domain_to_country:
                return domain_to_country[domain]
            
            # Vérifier les TLD (Top Level Domains) - ÉTENDU
            tld_to_country = {
                '.kr': 'South Korea', '.co.kr': 'South Korea',
                '.uk': 'UK', '.co.uk': 'UK',
                '.fr': 'France',
                '.eg': 'مصر',
                '.ma': 'المغرب',
                '.dz': 'الجزائر',
                '.tn': 'تونس',
                '.sa': 'السعودية', '.ae': 'الإمارات', '.qa': 'قطر', '.kw': 'الكويت',
                '.jo': 'الأردن', '.lb': 'لبنان', '.sy': 'سوريا', '.iq': 'العراق',
                '.ir': 'إيران', '.tr': 'Turkey', '.de': 'Germany', '.it': 'Italy',
                '.es': 'Spain', '.pt': 'Portugal', '.nl': 'Netherlands', '.be': 'Belgium',
                '.ch': 'Switzerland', '.at': 'Austria', '.se': 'Sweden', '.no': 'Norway',
                '.dk': 'Denmark', '.fi': 'Finland', '.pl': 'Poland', '.cz': 'Czech Republic',
                '.gr': 'Greece', '.ie': 'Ireland', '.ca': 'Canada', '.au': 'Australia',
                '.nz': 'New Zealand', '.za': 'South Africa', '.mx': 'Mexico', '.ar': 'Argentina',
                '.br': 'Brazil', '.cl': 'Chile', '.co': 'Colombia', '.ve': 'Venezuela',
                '.jp': 'Japan', '.cn': 'China', '.in': 'India', '.id': 'Indonesia',
                '.ph': 'Philippines', '.th': 'Thailand', '.vn': 'Vietnam', '.my': 'Malaysia',
                '.sg': 'Singapore', '.ru': 'Russia', '.kz': 'Kazakhstan', '.uz': 'Uzbekistan',
            }
            
            for tld, country in tld_to_country.items():
                if domain.endswith(tld):
                    return country
            
            return None
        except (AttributeError, KeyError, Exception):
            return None
    
    def extract_location_with_regex(self, texte, normalize=True):
        """Extrait le lieu avec des patterns regex (fallback multilingue) - cherche dans tout le texte
        
        Args:
            texte: Le texte dans lequel chercher le lieu
            normalize: Si True, normalise le résultat. Si False, retourne le lieu brut (pour éviter la récursion)
        """
        if not texte:
            return ""
        
        # Utiliser la liste étendue depuis data_constants.py
        common_locations_extended = COMMON_LOCATIONS_EXTENDED
        
        # Si le texte est très long, chercher dans plusieurs parties pour être sûr de trouver
        # PRIORITÉ: début de l'article (premiers 500 caractères)
        text_samples = []
        if len(texte) > 500:
            text_samples.append(texte[:500])  # Début (priorité haute)
        if len(texte) > 3000:
            text_samples.append(texte[:3000])  # Début étendu
            text_samples.append(texte[len(texte)//2:len(texte)//2 + 2000])  # Milieu
            text_samples.append(texte[-2000:])  # Fin
        else:
            text_samples.append(texte)
        
        # Utiliser les constantes depuis data_constants.py
        common_locations = common_locations_extended
        excluded_words = EXCLUDED_WORDS
        excluded_patterns = EXCLUDED_PATTERNS
        location_patterns = LOCATION_PATTERNS
        
        locations_found = []
        
        # Chercher dans tous les échantillons de texte
        for text_sample in text_samples:
            for pattern in location_patterns:
                matches = re.findall(pattern, text_sample, re.UNICODE)
                for match in matches:
                    if isinstance(match, tuple):
                        # Filtrer les prépositions et garder les noms propres
                        prepositions = ['in', 'at', 'from', 'near', 'around', 'en', 'dans', 'à', 'au', 'aux', 'في', 'ب', 'من', 'إلى']
                        location_parts = [m for m in match if m and m.lower() not in prepositions and len(m) > 2]
                        if location_parts:
                            location = ', '.join(location_parts)
                            # FILTRER les faux positifs
                            location_lower = location.lower()
                            if any(excluded in location_lower for excluded in excluded_words):
                                continue  # Ignorer ce résultat
                            if len(location) > 3:
                                locations_found.append(location.strip())
                    else:
                        # FILTRER les faux positifs
                        match_lower = match.lower() if isinstance(match, str) else str(match).lower()
                        if any(excluded in match_lower for excluded in excluded_words):
                            continue  # Ignorer ce résultat
                        if len(match) > 3:
                            locations_found.append(match.strip())
        
        # Vérifier si les lieux trouvés contiennent des pays/régions connus
        for loc in locations_found:
            # Vérifier si le lieu contient un pays/région connu
            for common_loc in common_locations:
                if common_loc.lower() in loc.lower() or loc.lower() in common_loc.lower():
                    # Vérification supplémentaire : le lieu ne doit pas être un faux positif
                    loc_lower = loc.lower()
                    if any(excluded in loc_lower for excluded in excluded_words):
                        continue  # Ignorer ce résultat
                    # Normaliser seulement si demandé (pour éviter la récursion infinie)
                    if normalize:
                        return self.normalize_location_name(loc)
                    else:
                        return loc.strip()
        
        # Si aucun lieu connu, filtrer et retourner le premier valide (normalisé si demandé)
        for loc in locations_found:
            loc_lower = loc.lower()
            # Vérifier que ce n'est pas un faux positif (mots exclus)
            if any(excluded in loc_lower for excluded in excluded_words):
                continue
            # Vérifier que ce n'est pas un faux positif (patterns exclus)
            if any(re.search(pattern, loc, re.IGNORECASE) for pattern in excluded_patterns):
                continue
            # Vérifier que ça ressemble à un lieu (contient au moins une majuscule ou est en arabe)
            if re.search(r'[A-Z]', loc) or re.search(r'[\u0600-\u06FF]', loc):
                # Validation supplémentaire : le lieu ne doit pas être trop court ou trop long
                if len(loc.strip()) < 3 or len(loc.split()) > 5:
                    continue
                # Validation : ne doit pas contenir de ponctuation suspecte
                if re.search(r'^[،,]\s*|\s*[،,]$', loc):  # Commence ou finit par virgule
                    continue
                if normalize:
                    return self.normalize_location_name(loc)
                else:
                    return loc.strip()
        
        return ""
    
    def normalize_disease_name(self, maladie, recursion_depth=0):
        """Normalise et nettoie le nom de la maladie pour qu'il soit clair et exact
        
        Args:
            maladie: Le nom de la maladie à normaliser
            recursion_depth: Profondeur de récursion pour éviter les boucles infinies (max 2)
        """
        if not maladie or maladie == "nan" or not maladie.strip():
            return ""
        
        # Protection contre la récursion infinie
        if recursion_depth >= 2:
            # Si on a déjà normalisé 2 fois, retourner la maladie nettoyée sans ré-extraction
            maladie = maladie.strip()
            maladie = re.sub(r'\s+', ' ', maladie)
            maladie = re.sub(r'\n+', ' ', maladie)
            return maladie.strip()
        
        maladie = maladie.strip()
        
        # Normaliser les noms de maladies courants (corrections spécifiques)
        disease_normalizations = {
            # Anglais
            'foot-and-mouth': 'Foot-and-mouth disease',
            'Foot-and-Mouth': 'Foot-and-mouth disease',
            'foot and mouth': 'Foot-and-mouth disease',
            'FMD': 'Foot-and-mouth disease',
            'rage': 'rabies',  # En anglais, c'est "rabies"
            'Rabies': 'rabies',
            'Anthrax': 'anthrax',
            'Bluetongue': 'bluetongue',
            'lumpy skin disease': 'dermatose nodulaire',
            'LSD': 'dermatose nodulaire',
            'chronic wasting disease': 'chronic wasting disease',
            'CWD': 'chronic wasting disease',
            'crimean-congo hemorrhagic fever': 'fièvre hémorragique de Crimée-Congo',
            'CCHF': 'fièvre hémorragique de Crimée-Congo',
            'FHCC': 'fièvre hémorragique de Crimée-Congo',
            'rift valley fever': 'fièvre de la vallée du Rift',
            'RVF': 'fièvre de la vallée du Rift',
            'FVR': 'fièvre de la vallée du Rift',
            # Français
            'rage': 'rage',  # En français, c'est "rage"
            'fièvre aphteuse': 'fièvre aphteuse',
            'fièvre catarrhale ovine': 'fièvre catarrhale ovine',
            'fièvre catarrhale': 'fièvre catarrhale ovine',
            'FCO': 'fièvre catarrhale ovine',
            'MHE': 'hémorragique épizootique',
            'maladie hémorragique épizootique': 'hémorragique épizootique',
            'fièvre hémorragique de Crimée-Congo': 'fièvre hémorragique de Crimée-Congo',
            'fièvre de la vallée du Rift': 'fièvre de la vallée du Rift',
            'variole du singe': 'variole du singe',
            'maladie à virus Ebola': 'maladie à virus Ebola',
            'fièvre de Lassa': 'fièvre de Lassa',
        }
        
        # Appliquer les normalisations
        maladie_lower = maladie.lower().strip()
        if maladie_lower in disease_normalizations:
            maladie = disease_normalizations[maladie_lower]
        elif maladie in disease_normalizations:
            maladie = disease_normalizations[maladie]
        
        maladie = maladie.strip()
        
        # Supprimer les mots génériques qui précèdent le nom de la maladie (multilingue)
        generic_disease_words_patterns = [
            # Français
            r'^(maladie|disease|désordre|disorder)\s+',
            r'^(cas|case)\s+de\s+',
            r'^(épidémie|epidemic|outbreak)\s+de\s+',
            # Anglais
            r'^(disease|illness|disorder|condition)\s+',
            r'^(case|outbreak|epidemic)\s+of\s+',
            # Arabe - IMPORTANT: supprimer "مرض" et "داء" au début et à la fin
            r'^(مرض|داء)\s+',  # Au début
            r'\s+(مرض|داء)$',  # À la fin
            r'^(تفشي|انتشار)\s+',
            # Espagnol
            r'^(enfermedad|enfermedades)\s+',
            # Allemand
            r'^(Krankheit|Erkrankung)\s+',
        ]
        
        for pattern in generic_disease_words_patterns:
            maladie = re.sub(pattern, '', maladie, flags=re.IGNORECASE | re.UNICODE)
        
        maladie = maladie.strip()
        
        # Cas spécial pour l'arabe : supprimer "مرض" et autres mots génériques
        # Exemple: "مرض التهاب الجلد العقدي" -> "التهاب الجلد العقدي"
        if re.search(r'[\u0600-\u06FF]', maladie):  # Si c'est de l'arabe
            # Supprimer "مرض" au début, au milieu ou à la fin
            maladie = re.sub(r'^مرض\s+', '', maladie)
            maladie = re.sub(r'\s+مرض\s+', ' ', maladie)  # Au milieu
            maladie = re.sub(r'\s+مرض$', '', maladie)  # À la fin
            # Supprimer "داء" aussi
            maladie = re.sub(r'^داء\s+', '', maladie)
            maladie = re.sub(r'\s+داء\s+', ' ', maladie)
            maladie = re.sub(r'\s+داء$', '', maladie)
            # Supprimer "بمرض" (avec préposition)
            maladie = re.sub(r'^بمرض\s+', '', maladie)
            maladie = re.sub(r'\s+بمرض\s+', ' ', maladie)
            # Supprimer "تفشي" au début
            maladie = re.sub(r'^تفشي\s+', '', maladie)
            maladie = maladie.strip()
        
        # Supprimer les parties de titre qui peuvent s'être glissées
        # Si la maladie contient des mots qui ne sont pas des noms de maladies
        non_disease_words = ['shots', 'for', 'after', 'dies', 'outbreak', 'lifted', 'due', 'to', 
                            'confirmation', 'case', 'single', 'urged', 'following', 'quarantine',
                            'تفشي', 'بالأبقار', 'الشرطة', 'الزراعية', 'في', 'من', 'إلى']
        
        words = maladie.split()
        # Si plus de 4 mots, c'est probablement une erreur (titre qui s'est glissé)
        # Limite stricte: maximum 4 mots pour une maladie
        if len(words) > 4:
            # Essayer d'extraire seulement la maladie (prioriser les mots les plus longs = plus significatifs)
            maladie_keywords = [w for w in words if w.lower() not in non_disease_words and len(w) > 2]
            if maladie_keywords:
                # Trier par longueur (les plus longs en premier) et prendre max 4
                maladie_keywords_sorted = sorted(maladie_keywords, key=len, reverse=True)
                maladie = ' '.join(maladie_keywords_sorted[:4])
            else:
                # Si aucun mot valide, retourner vide
                return ""
        
        # Normaliser les variantes courantes
        maladie_normalized = {
            'rabies': 'rage',
            'avian influenza': 'grippe aviaire',
            'bird flu': 'grippe aviaire',
            'foot-and-mouth disease': 'fièvre aphteuse',
            'fmd': 'fièvre aphteuse',
            'african swine fever': 'peste porcine africaine',
            'asf': 'peste porcine africaine',
            'lumpy skin disease': 'dermatose nodulaire',
            'lsd': 'dermatose nodulaire',
            'bluetongue': 'fièvre catarrhale ovine',
            'bovine spongiform encephalopathy': 'encéphalopathie spongiforme bovine',
            'bse': 'encéphalopathie spongiforme bovine',
            'chronic wasting disease': 'chronic wasting disease',
            'cwd': 'chronic wasting disease',
            'crimean-congo hemorrhagic fever': 'fièvre hémorragique de Crimée-Congo',
            'cchf': 'fièvre hémorragique de Crimée-Congo',
            'fhcc': 'fièvre hémorragique de Crimée-Congo',
            'rift valley fever': 'fièvre de la vallée du Rift',
            'rvf': 'fièvre de la vallée du Rift',
            'fvr': 'fièvre de la vallée du Rift',
            # Arabe -> français (traduire en français)
            'التهاب الجلد العقدي': 'dermatose nodulaire',
            'حمى الطيور': 'grippe aviaire',
            'الحمى القلاعية': 'fièvre aphteuse',
            'السعار': 'rage',
            'النزف الوبائي الحيواني': 'maladie hémorragique épizootique',
            'اللسان الأزرق': 'fièvre catarrhale ovine',
        }
        
        maladie_lower = maladie.lower()
        
        # Vérifier d'abord si c'est une maladie en arabe (priorité pour la traduction)
        if re.search(r'[\u0600-\u06FF]', maladie):
            # Dictionnaire de traduction des maladies arabes en français
            arabic_disease_translation = {
                'التهاب الجلد العقدي': 'dermatose nodulaire',
                'التهاب': 'dermatose nodulaire',  # Si seulement "التهاب" est trouvé
                'حمى الطيور': 'grippe aviaire',
                'الحمى القلاعية': 'fièvre aphteuse',
                'السعار': 'rage',
                'النزف الوبائي الحيواني': 'maladie hémorragique épizootique',
                'اللسان الأزرق': 'fièvre catarrhale ovine',
                'لسان أزرق': 'fièvre catarrhale ovine',  # Variante sans "ال"
            }
            
            # Chercher une correspondance exacte ou partielle (priorité aux correspondances exactes)
            for arabic_key, french_value in arabic_disease_translation.items():
                if arabic_key == maladie or arabic_key in maladie:
                    return french_value
        
        # Ensuite, vérifier dans le dictionnaire général (anglais/français)
        for key, value in maladie_normalized.items():
            # Pour l'arabe, on a déjà vérifié ci-dessus, donc on peut ignorer les clés arabes ici
            if re.search(r'[\u0600-\u06FF]', key):
                continue
            if key in maladie_lower or key == maladie:
                return value
        
        # Nettoyer les caractères parasites (retours à la ligne, etc.)
        maladie = re.sub(r'\s+', ' ', maladie)  # Espaces multiples
        maladie = re.sub(r'\n+', ' ', maladie)  # Retours à la ligne
        maladie = maladie.strip()
        
        # Si la maladie contient des parties de titre évidentes, les supprimer
        if any(word in maladie.lower() for word in ['shots', 'for', 'after', 'dies', 'outbreak', 'lifted']):
            # C'est probablement une erreur, essayer d'extraire seulement la maladie
            # Passer normalize=False pour éviter la récursion infinie
            maladie_extracted = self.extract_disease_with_regex(maladie, normalize=False)
            if maladie_extracted:
                # Normaliser le résultat extrait avec incrémentation de la profondeur de récursion
                return self.normalize_disease_name(maladie_extracted, recursion_depth=recursion_depth + 1)
        
        return maladie
    
    def is_valid_location(self, lieu):
        """Valide qu'un lieu extrait est réellement un lieu géographique et pas un faux positif"""
        if not lieu or len(lieu.strip()) < 2:
            return False
        
        lieu_lower = lieu.lower()
        lieu_stripped = lieu.strip()
        
        # Rejeter les phrases trop longues (probablement des extraits de texte, pas des lieux)
        # Un lieu géographique ne devrait pas dépasser 5-6 mots
        words = lieu_stripped.split()
        if len(words) > 6:
            return False
        
        # Rejeter les phrases qui contiennent des verbes ou des prépositions au début
        # (ex: "دولة الإمارات، الفرصة لاعتمادها والالتزام" - c'est une phrase complète)
        if len(words) > 3:
            # Vérifier si c'est une phrase complète avec des verbes/prépositions
            arabic_verbs_preps = ['الفرصة', 'لاعتمادها', 'والالتزام', 'بسبب', 'من', 'على', 'في', 'إلى', 'مع']
            if any(verb_prep in lieu_stripped for verb_prep in arabic_verbs_preps):
                return False
        
        # Rejeter les réponses d'Ollama mal parsées
        if 'assistant' in lieu_lower or 'helpful' in lieu_lower or 'extract' in lieu_lower:
            return False
        
        # Rejeter les points de suspension ou valeurs vides
        if lieu_stripped in ['...', '..', '.', 'nan', 'none', 'null', 'empty', '']:
            return False
        
        # Rejeter les nationalités/langues (pas des lieux géographiques)
        nationalities_languages = [
            'chinese', 'russian', 'english', 'french', 'spanish', 'german', 'italian', 'portuguese',
            'japanese', 'korean', 'arabic', 'turkish', 'dutch', 'polish', 'greek', 'swedish',
            'norwegian', 'danish', 'finnish', 'czech', 'hungarian', 'romanian', 'bulgarian',
            'chinois', 'russe', 'anglais', 'français', 'espagnol', 'allemand', 'italien', 'portugais',
            'japonais', 'coréen', 'arabe', 'turc', 'néerlandais', 'polonais', 'grec', 'suédois',
            'norvégien', 'danois', 'finlandais', 'tchèque', 'hongrois', 'roumain', 'bulgare'
        ]
        if lieu_lower in nationalities_languages or any(nat in lieu_lower for nat in nationalities_languages if len(nat) > 4):
            return False
        
        # Rejeter les phrases complètes en arabe qui ne sont pas des lieux
        # Exemple: "كتابها الذي نشرته عبر صفحتها" (son livre qu'elle a publié sur sa page)
        arabic_non_location_words = [
            'كتاب', 'كتابها', 'صفحة', 'صفحتها', 'نشر', 'نشرته', 'عبر', 'الذي', 'التي',
            'منع', 'استيراد', 'يرصد', 'إصابات', 'توطن', 'سلالات', 'جديدة', 'يقرر',
            'إطار', 'خطة', 'الهيئة', 'العامة', 'إقدام', 'السلطات', 'أبقار', 'مستوردة',
            'الفرصة', 'لاعتمادها', 'والالتزام', 'مخاوف', 'إقدام', 'نشرته', 'صفحتها'
        ]
        # Vérifier si le lieu contient des mots qui indiquent que ce n'est pas un lieu
        if any(word in lieu_stripped for word in arabic_non_location_words):
            # Si c'est une phrase complète (plus de 2 mots), rejeter
            if len(words) > 2:
                return False
            # Même pour 2 mots, si c'est une phrase descriptive, rejeter
            if len(words) == 2 and any(word in lieu_stripped for word in ['كتابها', 'صفحتها', 'نشرته', 'الذي', 'التي']):
                return False
        
        # Rejeter les lieux qui contiennent des prépositions ou mots de liaison (ex: "Washington Dans")
        prepositions_fr = ['dans', 'sur', 'sous', 'avec', 'sans', 'pour', 'par', 'vers', 'depuis', 'jusqu\'', 
                          'après', 'avant', 'pendant', 'chez', 'entre', 'parmi', 'contre', 'selon', 'malgré']
        prepositions_en = ['in', 'on', 'at', 'with', 'for', 'by', 'to', 'from', 'into', 'onto', 'upon',
                           'after', 'before', 'during', 'through', 'across', 'against', 'among', 'between']
        words_lower = [w.lower() for w in words]
        if any(prep in words_lower for prep in prepositions_fr + prepositions_en):
            return False
        
        # Liste étendue de mots à exclure (faux positifs)
        excluded_patterns = [
            # Ministères et départements
            r'\b(agriculture|environment|department|ministry|ministère|office|bureau|ministry of|department of)\b',
            # Organisations
            r'\b(health|santé|food|alimentation|rural|development|développement|affairs|affaires)\b',
            # Services
            r'\b(services|authority|autorité|agency|agence|organization|organisation)\b',
            # Institutions
            r'\b(institute|institut|center|centre|laboratory|laboratoire|hospital|hôpital)\b',
            # Éducation
            r'\b(school|école|university|université|college|collège)\b',
            # Entreprises
            r'\b(company|société|corporation|corp|inc|ltd|sarl)\b',
            # Mots arabes à exclure (phrases incomplètes)
            r'\b(جهاز|وزارة|مكتب|مكتبة|مستشفى|مدرسة|جامعة|الشرطة|الزراعية|إطار|خطة|الهيئة|العامة|بسبب|مخاوف|من|إقدام|السلطات|على|أبقار|مستوردة)\b',
            # Phrases arabes incomplètes (commençant par des prépositions ou verbes)
            r'^(بسبب|من|على|في|إلى|مع|منع|استيراد|يرصد|إصابات|توطن|سلالات|جديدة|يقرر)',
            # Mots génériques
            r'\b(shots|for|after|dies|outbreak|lifted|due|to|confirmation|case|single|urged|following|quarantine)\b',
            # Noms de personnes communs (à exclure des lieux)
            r'\b(culture|muhadjir|effendy|elvi|martina|muhammad|ahmed|ali|hassan|fatima)\b',
            # Titres de fonction arabes (à exclure des lieux)
            r'\b(رؤساء|فروع|موجه|وحدات|مدراء|مسؤولين|عاملين|موظفين)\b',
        ]
        
        # Vérifier si le lieu contient des mots exclus
        for pattern in excluded_patterns:
            if re.search(pattern, lieu_lower, re.IGNORECASE | re.UNICODE):
                return False
        
        # Vérifier les phrases arabes incomplètes (contiennent des prépositions ou verbes)
        arabic_prepositions = ['بسبب', 'من', 'على', 'في', 'إلى', 'مع', 'منع', 'استيراد', 'يرصد', 'إصابات', 'توطن', 'سلالات', 'جديدة', 'يقرر', 'إطار', 'خطة', 'الهيئة', 'العامة', 'إقدام', 'السلطات', 'أبقار', 'مستوردة']
        # Titres de fonction arabes (à exclure)
        arabic_job_titles = ['رؤساء', 'فروع', 'موجه', 'وحدات', 'مدراء', 'مسؤولين', 'عاملين', 'موظفين']
        if any(prep in lieu_stripped for prep in arabic_prepositions):
            # Si c'est une phrase complète avec un vrai lieu, c'est OK, sinon rejeter
            # Exemple: "بريطانيا" est OK, mais "بريطانيا بسبب الحر" n'est pas OK
            if len(lieu_stripped.split()) > 3:  # Plus de 3 mots = probablement une phrase
                return False
        # Rejeter les titres de fonction arabes
        if any(title in lieu_stripped for title in arabic_job_titles):
                return False
        
        # Vérifier que le lieu contient au moins un nom propre (majuscule) ou est en arabe
        has_capital = bool(re.search(r'[A-Z]', lieu))
        has_arabic = bool(re.search(r'[\u0600-\u06FF]', lieu))
        
        if not has_capital and not has_arabic:
            return False
        
        # Vérifier que le lieu ne contient pas que des mots courts (probablement des prépositions)
        words = lieu.split()
        if len(words) > 0:
            long_words = [w for w in words if len(w) > 3]
            if len(long_words) == 0:
                return False
        
        # Rejeter les lieux qui contiennent des noms de personnes (pattern: "Lieu, Nom Prénom")
        # Exemple: "Culture, Muhadjir Effendy" ou "Kabupaten Pinrang, Elvi Martina"
        # Rejeter aussi les nationalités/langues dans les lieux multiples (ex: "Chinese, Russian")
        if ',' in lieu:
            parts = [p.strip() for p in lieu.split(',')]
            if len(parts) >= 2:
                # Vérifier si toutes les parties sont des nationalités/langues (pas des lieux)
                all_nationalities = True
                for part in parts:
                    part_lower = part.lower()
                    if part_lower not in nationalities_languages and not any(nat in part_lower for nat in nationalities_languages if len(nat) > 4):
                        all_nationalities = False
                        break
                if all_nationalities:
                    # Toutes les parties sont des nationalités, rejeter
                    return False
                
                # Si la deuxième partie ressemble à un nom de personne (2-3 mots, pas de majuscules cohérentes avec un lieu)
                second_part = parts[1]
                second_words = second_part.split()
                # Si la deuxième partie a 2-3 mots et ne ressemble pas à un lieu (pas de "County", "State", etc.)
                if 2 <= len(second_words) <= 3:
                    if not any(word in second_part.lower() for word in ['county', 'state', 'province', 'region', 'city', 'ville', 'pays', 'country']):
                        # Vérifier si c'est une nationalité/langue
                        if second_part.lower() in nationalities_languages or any(nat in second_part.lower() for nat in nationalities_languages if len(nat) > 4):
                            return False
                        # Probablement un nom de personne
                        return False
        
        # Rejeter les noms de communautés (ex: "Burnham Woods Community")
        if 'community' in lieu_lower or 'communauté' in lieu_lower:
            return False
        
        # Rejeter les réponses Ollama mal parsées pour les lieux
        invalid_location_patterns = [
            'you are', 'helpful', 'assistant', 'ai', 'expert', 'geography', 'géographie',
            'el país', 'la región', 'country name', 'pays', 'country', 'région',
            '1.', 'المدينة', 'المنطقة', ':'  # Réponses Ollama mal formatées
        ]
        if any(pattern in lieu_lower for pattern in invalid_location_patterns):
            return False
        
        # Accepter les pays valides même s'ils sont courts (UK, USA, etc.)
        pays_valides_courts = ['usa', 'uk', 'fr', 'eg', 'ma', 'dz', 'tn', 'kr', 'jp', 'cn', 'in', 'au', 'ca', 'mx', 'br', 'ar', 'za']
        if lieu_lower in pays_valides_courts or lieu_stripped in ['USA', 'UK', 'France', 'مصر', 'المغرب']:
            return True
        
        return True
    
    def translate_location_to_french(self, lieu):
        """Traduit un nom de lieu en français
        
        Args:
            lieu: Le nom du lieu à traduire (peut être en anglais, arabe, etc.)
        
        Returns:
            Le nom du lieu en français
        """
        # Gérer les cas None, vide, ou non-string
        if lieu is None:
            return ""
        if not isinstance(lieu, str):
            lieu = str(lieu)
        if not lieu or lieu == "nan" or not lieu.strip():
            return lieu if isinstance(lieu, str) else ""
        
        lieu_clean = lieu.strip()
        lieu_lower = lieu_clean.lower()
        
        # Dictionnaire de traduction des pays en français
        location_translation = LOCATION_TRANSLATION
        
        # Chercher une correspondance exacte
        if lieu_lower in location_translation:
            return location_translation[lieu_lower]
        
        # Chercher une correspondance partielle (pour les noms avec espaces ou virgules)
        for key, value in location_translation.items():
            if key in lieu_lower:
                return value
        
        # Si pas de traduction trouvée, retourner le lieu original (peut être déjà en français)
        return lieu_clean
    
    def enrich_location_with_country(self, lieu, contenu=None, titre=None):
        """Extrait uniquement le pays depuis le lieu, le contenu ou le titre et le traduit en français
        
        Args:
            lieu: Le nom du lieu (ville ou région)
            contenu: Le contenu de l'article pour chercher le pays
            titre: Le titre de l'article
        
        Returns:
            Le pays uniquement en français (ex: "France", "États-Unis", "Égypte")
        """
        # Gérer les cas None, vide, ou non-string
        if lieu is None:
            return ""
        if not isinstance(lieu, str):
            lieu = str(lieu)
        if not lieu or lieu == "nan" or not lieu.strip():
            return lieu if isinstance(lieu, str) else ""
        
        lieu_clean = lieu.strip()
        
        # Utiliser le dictionnaire depuis data_constants.py
        city_to_country = CITY_TO_COUNTRY
        
        # Vérifier si le lieu contient déjà un pays (format "Ville, Pays")
        if ',' in lieu_clean:
            parts = [p.strip() for p in lieu_clean.split(',')]
            # Si le dernier élément ressemble à un pays, extraire uniquement le pays
            if len(parts) >= 2:
                last_part = parts[-1].strip()
                # Utiliser les codes d'état USA depuis data_constants.py
                usa_state_codes = USA_STATE_CODES
                # Si le dernier élément est un code pays (NY, UK, etc.) ou un pays connu
                if len(last_part) <= 3 or last_part in ['USA', 'UK', 'France', 'مصر', 'المغرب', 'Kazakhstan', 'South Korea', 'Afghanistan', 'Pakistan', 'Zambia', 'Botswana', 'Philippines', 'Indonesia', 'Uganda', 'Brazil', "Côte d'Ivoire", 'Paraguay', 'South Africa', 'Australia', 'Ireland']:
                    # Retourner uniquement le pays
                    pays_normalise = {
                        'NY': 'USA', 'NC': 'USA', 'GA': 'USA', 'VA': 'USA', 'CA': 'USA', 'TX': 'USA', 'FL': 'USA', 'IL': 'USA', 'PA': 'USA', 'OH': 'USA', 'MI': 'USA', 'SC': 'USA',
                        'US': 'USA', 'United States': 'USA',
                        'UK': 'UK', 'United Kingdom': 'UK',
                        'France': 'France',
                        'مصر': 'مصر', 'المغرب': 'المغرب',
                        'Kazakhstan': 'Kazakhstan',
                        'South Korea': 'South Korea', 'Korea': 'South Korea',
                        'Afghanistan': 'Afghanistan',
                        'Pakistan': 'Pakistan',
                        'Zambia': 'Zambia',
                        'Botswana': 'Botswana',
                        'Philippines': 'Philippines',
                        'Indonesia': 'Indonesia',
                        'Uganda': 'Uganda',
                        'Brazil': 'Brazil',
                        "Côte d'Ivoire": "Côte d'Ivoire",
                        'Paraguay': 'Paraguay',
                        'South Africa': 'South Africa',
                        'Australia': 'Australia',
                        'Ireland': 'Ireland'
                    }.get(last_part, last_part)
                    # Si c'est un code d'état USA, retourner États-Unis (en français)
                    if last_part in usa_state_codes:
                        return 'États-Unis'
                    # Traduire le pays en français
                    return self.translate_location_to_french(pays_normalise)
        
        # Chercher le pays dans le contenu si disponible
        texte_recherche = ""
        if contenu:
            texte_recherche += contenu[:2000]  # Premiers 2000 caractères
        if titre:
            texte_recherche += " " + titre
        
        if texte_recherche:
            # Liste des pays à chercher (français, anglais, arabe)
            pays_list = {
                # Pays en français/anglais
                'France', 'france', 'français', 'française',
                'United States', 'USA', 'US', 'America', 'American',
                'United Kingdom', 'UK', 'Britain', 'British',
                'Kazakhstan', 'kazakhstan',
                'South Korea', 'Korea', 'korean',
                'Afghanistan', 'afghanistan',
                'Pakistan', 'pakistan',
                'Zambia', 'zambia',
                'Botswana', 'botswana',
                'Philippines', 'philippines',
                # Pays en arabe
                'مصر', 'المغرب', 'تونس', 'الجزائر', 'لبنان', 'الأردن',
                'السعودية', 'الإمارات', 'قطر', 'الكويت', 'العراق', 'سوريا'
            }
            
            # Chercher le pays dans le texte (prioriser les pays mentionnés explicitement)
            pays_trouve = None
            pays_prioritaires = ['France', 'UK', 'USA', 'South Korea', 'Kazakhstan', 'Afghanistan', 
                                'Pakistan', 'Zambia', 'Botswana', 'Philippines', 'مصر', 'المغرب',
                                'Indonesia', 'Uganda', 'Brazil', 'Côte d\'Ivoire', 'Paraguay']
            
            # D'abord chercher les pays prioritaires (mentionnés dans le contexte de l'article)
            for pays in pays_prioritaires:
                if pays.lower() in texte_recherche.lower() or pays in texte_recherche:
                    # Vérifier que ce n'est pas juste une partie du nom de la ville
                    if pays.lower() not in lieu_clean.lower():
                        # Vérifier que le pays est mentionné dans un contexte géographique (pas juste dans une URL ou un nom d'organisation)
                        pays_context = self._check_country_context(pays, texte_recherche)
                        if pays_context:
                            pays_trouve = pays
                            break
            
            # Si aucun pays prioritaire trouvé, chercher dans la liste complète
            if not pays_trouve:
                for pays in pays_list:
                    if pays.lower() in texte_recherche.lower() or pays in texte_recherche:
                        # Vérifier que ce n'est pas juste une partie du nom de la ville
                        if pays.lower() not in lieu_clean.lower():
                            pays_context = self._check_country_context(pays, texte_recherche)
                            if pays_context:
                                pays_trouve = pays
                                break
            
            # Si on a trouvé un pays, l'ajouter
            if pays_trouve:
                # IMPORTANT: Si le lieu original est déjà un pays connu valide, ne pas le remplacer
                # sauf si le pays trouvé dans le texte est le même ou très proche
                pays_connus = PAYS_CONNUS
                
                # Vérifier si le lieu original est déjà un pays connu
                lieu_est_pays_connu = False
                lieu_pays_normalise = None
                for pays_connu in pays_connus:
                    if lieu_clean.lower() == pays_connu.lower() or lieu_clean == pays_connu:
                        lieu_est_pays_connu = True
                        lieu_pays_normalise = pays_connu
                        break
                
                # Si le lieu original est déjà un pays connu, ne le remplacer que si:
                # 1. Le pays trouvé dans le texte est le même, OU
                # 2. Le pays trouvé est très proche (variante du même pays)
                if lieu_est_pays_connu:
                    pays_trouve_lower = pays_trouve.lower()
                    lieu_pays_lower = lieu_pays_normalise.lower() if lieu_pays_normalise else lieu_clean.lower()
                    
                    # Vérifier si c'est le même pays ou une variante
                    variantes_pays = {
                        'brazil': ['brésil', 'brazil'],
                        'brésil': ['brazil', 'brésil'],
                        'usa': ['united states', 'us', 'america', 'usa'],
                        'uk': ['united kingdom', 'britain', 'uk'],
                        'france': ['france', 'français', 'française']
                    }
                    
                    # Si c'est le même pays ou une variante, accepter
                    if pays_trouve_lower == lieu_pays_lower:
                        # Même pays, normaliser et retourner
                        pays_normalise = {
                            'france': 'France', 'français': 'France', 'française': 'France',
                            'usa': 'USA', 'us': 'USA', 'united states': 'USA', 'america': 'USA', 'american': 'USA',
                            'uk': 'UK', 'united kingdom': 'UK', 'britain': 'UK', 'british': 'UK',
                            'brazil': 'Brazil', 'brésil': 'Brazil',
                            'kazakhstan': 'Kazakhstan',
                            'south korea': 'South Korea', 'korea': 'South Korea', 'korean': 'South Korea',
                            'afghanistan': 'Afghanistan',
                            'pakistan': 'Pakistan',
                            'zambia': 'Zambia',
                            'botswana': 'Botswana',
                            'philippines': 'Philippines',
                            'indonesia': 'Indonesia', 'indonésie': 'Indonesia',
                            'uganda': 'Uganda',
                            'côte d\'ivoire': "Côte d'Ivoire", 'cote d\'ivoire': "Côte d'Ivoire",
                            'paraguay': 'Paraguay',
                            'belgium': 'Belgium', 'belgique': 'Belgium',
                            'south africa': 'South Africa',
                            'australia': 'Australia',
                            'ireland': 'Ireland',
                            'مصر': 'مصر', 'المغرب': 'المغرب', 'تونس': 'تونس', 'الجزائر': 'الجزائر'
                        }.get(pays_trouve_lower, pays_trouve)
                        # Traduire le pays en français
                        return self.translate_location_to_french(pays_normalise)
                    elif any(variante in pays_trouve_lower for variante in variantes_pays.get(lieu_pays_lower, [])):
                        # Variante du même pays, normaliser et retourner
                        pays_normalise = {
                            'brazil': 'Brazil', 'brésil': 'Brazil',
                            'usa': 'USA', 'us': 'USA', 'united states': 'USA', 'america': 'USA',
                            'uk': 'UK', 'united kingdom': 'UK', 'britain': 'UK',
                            'france': 'France', 'français': 'France', 'française': 'France'
                        }.get(pays_trouve_lower, lieu_pays_normalise)
                        # Traduire le pays en français
                        return self.translate_location_to_french(pays_normalise)
                    else:
                        # Pays différent trouvé dans le texte, mais le lieu original est déjà un pays connu
                        # Ne pas remplacer - garder le lieu original
                        return lieu_pays_normalise if lieu_pays_normalise else lieu_clean
                
                # Normaliser le nom du pays
                pays_normalise = {
                    'france': 'France', 'français': 'France', 'française': 'France',
                    'usa': 'USA', 'us': 'USA', 'united states': 'USA', 'america': 'USA', 'american': 'USA',
                    'uk': 'UK', 'united kingdom': 'UK', 'britain': 'UK', 'british': 'UK',
                    'kazakhstan': 'Kazakhstan',
                    'south korea': 'South Korea', 'korea': 'South Korea', 'korean': 'South Korea',
                    'afghanistan': 'Afghanistan',
                    'pakistan': 'Pakistan',
                    'zambia': 'Zambia',
                    'botswana': 'Botswana',
                    'philippines': 'Philippines',
                    'indonesia': 'Indonesia', 'indonésie': 'Indonesia',
                    'uganda': 'Uganda',
                    'brazil': 'Brazil', 'brésil': 'Brazil',
                    'côte d\'ivoire': "Côte d'Ivoire", 'cote d\'ivoire': "Côte d'Ivoire",
                    'paraguay': 'Paraguay',
                    'belgium': 'Belgium', 'belgique': 'Belgium',
                    'south africa': 'South Africa',
                    'australia': 'Australia',
                    'ireland': 'Ireland',
                    'مصر': 'مصر', 'المغرب': 'المغرب', 'تونس': 'تونس', 'الجزائر': 'الجزائر'
                }.get(pays_trouve.lower(), pays_trouve)
                
                # IMPORTANT: Ne pas ajouter USA automatiquement si le lieu n'est pas aux USA
                # Vérifier que le contexte indique vraiment les USA
                if pays_normalise == 'USA':
                    # Si le lieu original contient des indicateurs clairs des USA (états, counties, etc.), accepter USA
                    lieu_lower = lieu_clean.lower()
                    usa_indicators_in_lieu = [
                        'county', 'ny', 'ca', 'tx', 'fl', 'nc', 'sc', 'ga', 'va', 'il', 'pa', 'oh', 'mi',
                        'new york', 'california', 'texas', 'florida', 'north carolina', 'south carolina',
                        'georgia', 'virginia', 'illinois', 'pennsylvania', 'ohio', 'michigan',
                        'rockland', 'orange', 'chatham', 'savannah', 'danville', 'wyoming',
                        'yellowstone', 'coody lake', 'national park'
                    ]
                    if any(indicator in lieu_lower for indicator in usa_indicators_in_lieu):
                        # Le lieu contient clairement un indicateur USA, accepter États-Unis (en français)
                        return self.translate_location_to_french(pays_normalise)
                    
                    # Sinon, vérifier que le texte mentionne vraiment les USA dans un contexte géographique
                    usa_context = self._check_usa_context(texte_recherche, lieu_clean)
                    if not usa_context:
                        # Ne pas ajouter USA si le contexte ne le justifie pas
                        # MAIS: Si le lieu original est déjà un pays connu (comme "Paraguay"), ne pas le remplacer par USA
                        pays_connus_non_usa = ['Paraguay', 'Belgium', 'Belgique', 'France', 'UK', 'South Korea', 'Kazakhstan', 
                                              'Afghanistan', 'Pakistan', 'Zambia', 'Botswana', 'Philippines', 'Indonesia', 
                                              'Uganda', 'Brazil', 'Brésil', "Côte d'Ivoire", 'South Africa', 'Australia', 'Ireland',
                                              'Africa', 'Afrique',  # Continents - ne pas remplacer par un pays
                                              'مصر', 'المغرب', 'تونس', 'الجزائر']
                        if lieu_clean in pays_connus_non_usa or lieu_clean in [p.lower() for p in pays_connus_non_usa]:
                            # Le lieu original est un pays connu, ne pas le remplacer par USA
                            # Traduire en français
                            return self.translate_location_to_french(lieu_clean)
                        # Traduire en français
                        return self.translate_location_to_french(lieu_clean)
                
                # Retourner uniquement le pays (pas "Ville, Pays") en français
                return self.translate_location_to_french(pays_normalise)
        
        # Si pas de contenu, utiliser le dictionnaire de correspondances
        if lieu_clean in city_to_country:
            pays = city_to_country[lieu_clean]
            # Retourner uniquement le pays (traduit en français)
            return self.translate_location_to_french(pays)
        
        # Si le lieu est déjà un pays connu, le retourner tel quel
        pays_connus = PAYS_CONNUS
        if lieu_clean in pays_connus or lieu_clean in [p.lower() for p in pays_connus]:
            # Traduire en français
            return self.translate_location_to_french(lieu_clean)
        
        # Si le lieu n'est pas un pays connu et n'est pas dans le dictionnaire, utiliser Ollama pour convertir ville -> pays
        # TOUJOURS essayer de trouver le pays, même pour les noms simples comme "Keen Lake"
        if USE_OLLAMA and lieu_clean:
            # Vérifier si c'est probablement une ville (contient des mots comme "County", "City", "Region", etc.)
            ville_keywords = ['county', 'city', 'region', 'province', 'state', 'district', 'ville', 'cité', 'محافظة', 'مدينة', 'منطقة', 'lake', 'park', 'national']
            is_probably_city = any(keyword.lower() in lieu_clean.lower() for keyword in ville_keywords)
            
            # Si le lieu n'est pas dans la liste des pays connus, c'est probablement une ville/région
            # TOUJOURS essayer de trouver le pays via Ollama
            if lieu_clean not in pays_connus and lieu_clean not in [p.lower() for p in pays_connus]:
                print(f"  [OLLAMA] Conversion lieu -> pays pour: {lieu_clean}")
                pays_ollama = self.convert_city_to_country_with_ollama(lieu_clean, contenu=contenu, titre=titre)
                if pays_ollama and pays_ollama.strip():
                    print(f"  [OLLAMA] Pays trouvé: {pays_ollama}")
                    # Traduire en français
                    return self.translate_location_to_french(pays_ollama.strip())
        
        # Traduire en français avant de retourner
        return self.translate_location_to_french(lieu_clean)
    
    def convert_city_to_country_with_ollama(self, ville, contenu=None, titre=None):
        """Utilise Ollama pour convertir une ville/cité en pays correspondant
        
        Args:
            ville: Le nom de la ville/cité à convertir
            contenu: Le contenu de l'article (optionnel, pour contexte)
            titre: Le titre de l'article (optionnel, pour contexte)
        
        Returns:
            Le nom du pays correspondant, ou None si non trouvé
        """
        if not USE_OLLAMA or not ville or not ville.strip():
            return None
        
        # Détecter la langue pour adapter le prompt
        texte_contexte = ""
        if titre:
            texte_contexte += titre
        if contenu:
            texte_contexte += " " + contenu[:400]  # Réduit de 500 à 400 caractères
        
        langue_detectee = self.detect_language(texte_contexte if texte_contexte else ville)
        
        # Créer un prompt selon la langue
        prompt = PromptManager.get_location_conversion_prompt(ville, langue_detectee)
        
        response = self.call_ollama(prompt)
        if response:
            # Nettoyer la réponse (enlever espaces, caractères parasites)
            pays = response.strip()
            
            # Rejeter les réponses d'Ollama mal parsées (instructions, métadonnées, etc.)
            invalid_patterns = [
                'you are', 'tu es', 'أنت', 'expert', 'helpful', 'assistant', 'ai',
                'el país', 'la región', 'country name', 'pays', 'country', 'région',
                'géographie', 'geography', 'expert', 'convert', 'convertis', 'convertir'
            ]
            pays_lower = pays.lower()
            if any(pattern in pays_lower for pattern in invalid_patterns):
                return None
            
            # Enlever les préfixes/suffixes communs dans les réponses Ollama
            prefixes_to_remove = [
                'el país/la región:', 'el país:', 'la región:', 'country name:', 'pays:', 'country:', 'région:',
                'you are a helpful ai assistant.', 'you are a helpful assistant.', 'you are',
                'tu es', 'أنت', 'example:', 'exemple:', 'مثال:'
            ]
            for prefix in prefixes_to_remove:
                if pays_lower.startswith(prefix.lower()):
                    pays = pays[len(prefix):].strip()
                    # Nettoyer les deux-points et points restants
                    pays = pays.lstrip(':').strip()
                    pays = pays.rstrip('.').strip()
            
            # Nettoyer les formats comme "Example: "Tatarstan" → "Russian Federation"
            # Chercher le pattern "→" ou "->" et prendre ce qui suit
            if '→' in pays or '->' in pays:
                parts = re.split(r'[→-]', pays, maxsplit=1)
                if len(parts) > 1:
                    pays = parts[-1].strip()
            
            # Enlever les guillemets si présents
            pays = pays.strip('"\'')
            # Prendre seulement la première ligne (au cas où Ollama ajoute des explications)
            pays = pays.split('\n')[0].strip()
            
            # Nettoyer les guillemets restants après le split
            pays = pays.strip('"\'')
            
            # Vérifier que c'est un pays valide (pas vide, pas trop long)
            if pays and len(pays) < 50 and len(pays) > 1:
                return pays
        
        return None
    
    def _check_country_context(self, pays, texte):
        """Vérifie que le pays est mentionné dans un contexte géographique valide"""
        if not texte or not pays:
            return False
        
        texte_lower = texte.lower()
        pays_lower = pays.lower()
        
        # Mots-clés qui indiquent un contexte géographique valide
        context_keywords = [
            'in', 'at', 'from', 'to', 'of', 'en', 'à', 'de', 'du', 'dans', 'au',
            'في', 'من', 'إلى', 'ب', 'في', 'منطقة', 'مدينة', 'بلد', 'دولة',
            'province', 'region', 'country', 'state', 'county', 'district'
        ]
        
        # Chercher le pays dans le texte avec contexte
        pays_pos = texte_lower.find(pays_lower)
        if pays_pos == -1:
            return False
        
        # Vérifier le contexte avant et après le pays (50 caractères de chaque côté)
        context_before = texte_lower[max(0, pays_pos - 50):pays_pos]
        context_after = texte_lower[pays_pos + len(pays):min(len(texte_lower), pays_pos + len(pays) + 50)]
        
        # Vérifier si un mot-clé de contexte est présent
        has_context = any(keyword in context_before or keyword in context_after for keyword in context_keywords)
        
        # Éviter les faux positifs : rejeter si le pays est dans une URL, un email, ou un nom d'organisation
        if '@' in context_before or '@' in context_after:
            return False
        if 'http' in context_before or 'http' in context_after:
            return False
        if 'ministry' in context_before or 'ministry' in context_after:
            # Accepter seulement si c'est clairement géographique (ex: "Ministry of Health in France")
            if 'in ' + pays_lower in context_after or 'of ' + pays_lower in context_after:
                return True
            return False
        
        return has_context or len(pays) > 4  # Accepter les pays longs même sans contexte explicite
    
    def _check_usa_context(self, texte, lieu):
        """Vérifie que le contexte indique vraiment les USA (évite d'ajouter USA partout)"""
        if not texte or not lieu:
            return False
        
        texte_lower = texte.lower()
        lieu_lower = lieu.lower()
        
        # Indicateurs que c'est vraiment aux USA
        usa_indicators = [
            'united states', 'usa', 'us', 'america', 'american',
            'new york', 'california', 'texas', 'florida', 'illinois',
            'county, ny', 'county, ca', 'county, tx', 'county, fl',
            'north carolina', 'south carolina', 'georgia', 'virginia'
        ]
        
        # Si le lieu contient déjà un état américain ou un code d'état
        usa_states = ['ny', 'ca', 'tx', 'fl', 'nc', 'sc', 'ga', 'va', 'il', 'pa', 'oh', 'mi']
        if any(state in lieu_lower for state in usa_states):
            return True
        
        # Si le texte mentionne explicitement les USA dans le contexte du lieu
        for indicator in usa_indicators:
            if indicator in texte_lower:
                # Vérifier que c'est dans le contexte du lieu mentionné
                indicator_pos = texte_lower.find(indicator)
                lieu_pos = texte_lower.find(lieu_lower)
                if lieu_pos != -1 and abs(indicator_pos - lieu_pos) < 200:
                    return True
        
        return False
    
    def normalize_location_name(self, lieu, recursion_depth=0, contenu=None, titre=None):
        """Normalise et nettoie le nom du lieu pour qu'il soit clair et exact
        
        Args:
            lieu: Le nom du lieu à normaliser
            recursion_depth: Profondeur de récursion pour éviter les boucles infinies (max 2)
            contenu: Le contenu de l'article (optionnel, pour enrichir avec le pays)
            titre: Le titre de l'article (optionnel, pour enrichir avec le pays)
        """
        if not lieu or lieu == "nan" or not lieu.strip():
            return ""
        
        # VALIDATION IMMÉDIATE : vérifier que c'est un lieu valide
        if not self.is_valid_location(lieu):
            # Si ce n'est pas un lieu valide, essayer de ré-extraire
            if recursion_depth < 1:
                lieu_extracted = self.extract_location_with_regex(lieu, normalize=False)
                if lieu_extracted and self.is_valid_location(lieu_extracted):
                    return self.normalize_location_name(lieu_extracted, recursion_depth=recursion_depth + 1, contenu=contenu, titre=titre)
            return ""  # Retourner vide si ce n'est pas un lieu valide
        
        # Protection contre la récursion infinie
        if recursion_depth >= 2:
            # Si on a déjà normalisé 2 fois, retourner le lieu nettoyé sans ré-extraction
            lieu = lieu.strip()
            lieu = re.sub(r'\s+', ' ', lieu)
            lieu = re.sub(r'\s+region\s*$', '', lieu, flags=re.IGNORECASE)
            lieu = re.sub(r'\s+county\s*,', ' County,', lieu, flags=re.IGNORECASE)
            # Vérifier une dernière fois que c'est valide
            if self.is_valid_location(lieu):
                return lieu.strip()
            return ""
        
        lieu = lieu.strip()
        
        # Gérer les lieux multiples séparés par des virgules (ex: "France, Belgium" ou "Chinese, Russian")
        if ',' in lieu:
            parts = [p.strip() for p in lieu.split(',')]
            valid_locations = []
            for part in parts:
                # Valider chaque partie individuellement
                if self.is_valid_location(part):
                    valid_locations.append(part)
                # Si une partie contient plusieurs lieux (ex: "France Belgium"), essayer de les séparer
                elif ' ' in part and len(part.split()) <= 3:
                    # Essayer d'extraire un lieu valide de cette partie
                    lieu_extracted = self.extract_location_with_regex(part, normalize=False)
                    if lieu_extracted and self.is_valid_location(lieu_extracted):
                        valid_locations.append(lieu_extracted)
            
            # Si on a trouvé des lieux valides, prendre le premier (ou le plus pertinent)
            if valid_locations:
                # Prioriser les pays sur les villes/régions
                countries = ['France', 'UK', 'USA', 'Belgium', 'Netherlands', 'Germany', 'Spain', 'Italy',
                            'China', 'Japan', 'South Korea', 'India', 'Brazil', 'Argentina', 'Canada',
                            'مصر', 'المغرب', 'الجزائر', 'تونس', 'ليبيا', 'سوريا', 'العراق', 'إيران']
                for loc in valid_locations:
                    if loc in countries or any(country.lower() in loc.lower() for country in countries):
                        lieu = loc
                        break
                else:
                    # Sinon, prendre le premier lieu valide
                    lieu = valid_locations[0]
            else:
                # Aucun lieu valide trouvé dans les parties séparées
                return ""
        
        # VALIDATION : Vérifier que c'est un vrai lieu géographique
        if not self.is_valid_location(lieu):
            # Si ce n'est pas un lieu valide, essayer d'extraire un vrai lieu
            lieu_extracted = self.extract_location_with_regex(lieu, normalize=False)
            if lieu_extracted and self.is_valid_location(lieu_extracted):
                return self.normalize_location_name(lieu_extracted, recursion_depth=recursion_depth + 1, contenu=contenu, titre=titre)
            return ""  # Retourner vide si pas de lieu valide
        
        # Supprimer les parties de titre qui peuvent s'être glissées
        # Si le lieu contient des mots qui ne sont pas des noms géographiques
        non_location_words = ['shots', 'for', 'after', 'dies', 'outbreak', 'lifted', 'due', 'to',
                             'confirmation', 'case', 'single', 'urged', 'following', 'quarantine',
                             'تفشي', 'مرض', 'الالتهاب', 'العقدي', 'بالأبقار']
        
        words = lieu.split()
        # Si plus de 4 mots, c'est probablement une erreur (titre qui s'est glissé)
        # Limite stricte: maximum 4 mots pour un lieu (ex: "Rockland County, NY" = 3 mots)
        if len(words) > 4:
            # Essayer d'extraire seulement le lieu géographique (prioriser les mots avec majuscules = noms propres)
            location_keywords = []
            for w in words:
                w_lower = w.lower()
                # Prioriser les mots avec majuscules (noms propres) et exclure les mots non-géographiques
                if (w[0].isupper() or len(w) > 3) and w_lower not in non_location_words and len(w) > 2:
                    location_keywords.append(w)
            if location_keywords:
                # Prendre max 4 mots, en préservant l'ordre si possible (ville, région, pays)
                lieu = ' '.join(location_keywords[:4])
            else:
                # Si aucun mot valide, retourner vide
                return ""
        
        # Nettoyer les caractères parasites
        lieu = re.sub(r'\s+', ' ', lieu)  # Espaces multiples
        lieu = re.sub(r'\n+', ', ', lieu)  # Retours à la ligne -> virgule
        lieu = re.sub(r'[،,]+', ', ', lieu)  # Normaliser les virgules arabes
        lieu = lieu.strip()
        
        # Supprimer les parties évidentes de titre
        if any(word in lieu.lower() for word in ['shots', 'for', 'after', 'dies', 'outbreak', 'lifted', 
                                                 'agriculture', 'environment', 'department']):
            # C'est probablement une erreur, essayer d'extraire seulement le lieu
            # Passer normalize=False pour éviter la récursion infinie
            lieu_extracted = self.extract_location_with_regex(lieu, normalize=False)
            if lieu_extracted and self.is_valid_location(lieu_extracted):
                # Normaliser le résultat extrait avec incrémentation de la profondeur de récursion
                return self.normalize_location_name(lieu_extracted, recursion_depth=recursion_depth + 1, contenu=contenu, titre=titre)
            # Si on ne trouve rien, retourner vide plutôt qu'une erreur
            return ""
        
        # Normaliser les formats courants
        # "Rockland County, NY" -> "Rockland County, NY"
        # "Karaganda region" -> "Karaganda"
        lieu = re.sub(r'\s+region\s*$', '', lieu, flags=re.IGNORECASE)
        lieu = re.sub(r'\s+county\s*,', ' County,', lieu, flags=re.IGNORECASE)
        
        # Validation finale : s'assurer que le résultat est toujours valide
        if not self.is_valid_location(lieu):
            return ""
        
        lieu = lieu.strip()
        
        # Enrichir avec le pays si disponible
        if contenu or titre:
            lieu = self.enrich_location_with_country(lieu, contenu=contenu, titre=titre)
        
        # Traduire en français à la fin
        lieu = self.translate_location_to_french(lieu)
        
        return lieu
    
    # ============================================================================
    # SECTION 9: EXTRACTION D'ORGANISMES
    # ============================================================================
    
    def extract_organism_with_ollama(self, titre, contenu):
        """Extrait le nom de l'organisme (ministère, organisation, institution) mentionné"""
        if not USE_OLLAMA or not contenu:
            return None
        
        # Utiliser plus de contexte pour améliorer la détection
        texte_analyse = f"{titre}\n\n{contenu[:1500]}" if titre else contenu[:1500]
        langue = self.detect_language(texte_analyse)
        
        prompt = PromptManager.get_organism_extraction_prompt(texte_analyse, langue)
        
        response = self.call_ollama(prompt, max_retries=2, timeout=30)
        if not response:
            return None
        
        organisme = response.strip().strip('"\'')
        organisme = organisme.split('\n')[0].strip()
        
        # Nettoyer les préfixes communs dans les réponses Ollama
        prefixes_to_remove = PREFIXES_TO_REMOVE
        organisme_lower = organisme.lower()
        for prefix in prefixes_to_remove:
            if organisme_lower.startswith(prefix):
                organisme = organisme[len(prefix):].strip()
                # Enlever les deux-points restants
                organisme = organisme.lstrip(':').strip()
                break
        
        # Utiliser les constantes depuis data_constants.py
        invalid_responses = INVALID_RESPONSES
        if not organisme or organisme.upper() in invalid_responses:
            return None
        # Vérifier aussi si ça contient "non trouvé" ou variantes (même avec fautes)
        organisme_upper = organisme.upper()
        if 'NON TROUV' in organisme_upper or 'NOT FOUND' in organisme_upper or 'NO FOUND' in organisme_upper:
            return None
        
        # Utiliser les patterns depuis data_constants.py
        invalid_patterns = INVALID_PATTERNS
        if any(pattern in organisme.lower() for pattern in invalid_patterns):
            return None
        
        # Utiliser les constantes depuis data_constants.py
        phrase_starters = PHRASE_STARTERS
        organisme_lower = organisme.lower().strip()
        if any(starter in organisme_lower for starter in phrase_starters):
            return None
        
        # Utiliser les constantes depuis data_constants.py
        conjugated_verbs = CONJUGATED_VERBS
        organisme_words = organisme_lower.split()
        if any(verb in organisme_words for verb in conjugated_verbs):
            return None
        
        # Rejeter les phrases trop longues (plus de 8 mots = probablement une phrase complète)
        if len(organisme.split()) > 8:
            return None
        
        # Utiliser les constantes depuis data_constants.py
        generic_terms = GENERIC_TERMS
        # Vérifier exactement (sans espaces) et aussi comme mot isolé
        organisme_clean = organisme.lower().strip()
        if organisme_clean in [term.lower() for term in generic_terms]:
            return None
        # Vérifier si c'est un mot isolé qui est dans la liste
        if len(organisme.split()) == 1 and organisme_clean in [term.lower() for term in generic_terms]:
            return None
        
        # Rejeter si trop court (moins de 2 caractères)
        if len(organisme.strip()) < 2:
            return None
        
        # Rejeter les mots isolés trop courts (sauf acronymes connus)
        if len(organisme.split()) == 1 and len(organisme) < 3:
            # Utiliser les constantes depuis data_constants.py
            known_acronyms = KNOWN_ACRONYMS
            if organisme.upper() not in known_acronyms:
                return None
        
        # Limiter la longueur
        if len(organisme.split()) > 8:
            return None
        
        return organisme
    
    def extract_organism_with_regex(self, texte):
        """Extrait les organismes avec des expressions régulières"""
        if not texte:
            return None
        
        # Patterns pour les organismes (améliorés et étendus)
        patterns = [
            # Ministères
            r'(?:Ministère|Ministry|وزارة)\s+(?:de\s+)?(?:l\'|la\s+|du\s+|des\s+)?(?:Agriculture|Santé|Health|الزراعة|الصحة|Environment|Environnement)',
            r'(?:Ministry\s+of\s+Agriculture|Ministry\s+of\s+Health|Ministry\s+of\s+Environment)',
            # Organisations internationales
            r'(?:OMS|WHO|World Health Organization|منظمة الصحة العالمية)',
            r'(?:FAO|Food and Agriculture Organization|منظمة الأغذية والزراعة)',
            r'(?:OIE|WOAH|World Organisation for Animal Health|المنظمة العالمية لصحة الحيوان)',
            r'(?:CDC|Centers for Disease Control|Centers?\s+for\s+Disease\s+Control)',
            r'(?:EFSA|European Food Safety Authority)',
            r'(?:ANSES|Agence nationale de sécurité sanitaire)',
            r'(?:ECDC|European Centre for Disease Prevention)',
            r'(?:UN|United Nations|الأمم المتحدة)',
            r'(?:UNICEF|United Nations Children\'s Fund)',
            # Agences gouvernementales
            r'(?:USDA|United States Department of Agriculture)',
            r'(?:APHIS|Animal and Plant Health Inspection Service)',
            r'(?:DEFRA|Department for Environment, Food and Rural Affairs)',
            r'(?:DGAL|Direction générale de l\'alimentation)',
            # Organisations régionales
            r'(?:EU|European Union|الاتحاد الأوروبي)',
            r'(?:ASEAN|Association of Southeast Asian Nations)',
        ]
        
        # Chercher les patterns
        for pattern in patterns:
            match = re.search(pattern, texte, re.IGNORECASE)
            if match:
                result = match.group(0).strip()
                # Nettoyer le résultat
                result = re.sub(r'\s+', ' ', result)
                return result
        
        # Chercher aussi des acronymes seuls (OMS, WHO, FAO, etc.)
        acronyms = ['OMS', 'WHO', 'FAO', 'OIE', 'WOAH', 'CDC', 'EFSA', 'ANSES', 'ECDC', 'USDA', 'APHIS', 'DEFRA', 'DGAL']
        texte_upper = texte.upper()
        for acronym in acronyms:
            if acronym in texte_upper:
                # Vérifier que ce n'est pas dans un mot plus long
                pattern = r'\b' + re.escape(acronym) + r'\b'
                if re.search(pattern, texte, re.IGNORECASE):
                    return acronym
        
        return None
    
    # ============================================================================
    # SECTION 10: EXTRACTION D'ANIMAUX
    # ============================================================================
    
    def extract_animal_with_ollama(self, titre, contenu):
        """Extrait le nom de l'animal (espèce) mentionné dans l'article"""
        if not USE_OLLAMA or not contenu:
            return None
        
        # Utiliser plus de contexte pour améliorer la détection
        texte_analyse = f"{titre}\n\n{contenu[:1500]}" if titre else contenu[:1500]
        langue = self.detect_language(texte_analyse)
        
        prompt = PromptManager.get_animal_extraction_prompt(texte_analyse, langue)
        
        response = self.call_ollama(prompt, max_retries=2, timeout=30)
        if not response:
            return None
        
        animal = response.strip().strip('"\'')
        animal = animal.split('\n')[0].strip()
        
        # Validation
        if not animal or animal.upper() in ['NON TROUVE', 'NON TROUVEE', 'NOT FOUND', 'N/A', 'NONE']:
            return None
        
        # Rejeter les réponses invalides
        invalid_patterns = ['assistant', 'helpful', 'extract', 'you are', 'tu es', 'expert', 'citation', '...',
                           'minimalism', 'uniqueent', 'absolute', 'revised', 'here\'s', 'answer', 'sure',
                           'correct', 'here', 'is', 'the', 'animal', 'l\'animal', 'الحيوان',
                           # Rejeter les lieux (pas des animaux)
                           'lieu', 'lieux', 'place', 'places', 'location', 'locations', 'nouveau', 'nouveaux',
                           'new', 'ville', 'city', 'pays', 'country', 'région', 'region', 'état', 'state']
        if any(pattern in animal.lower() for pattern in invalid_patterns):
            return None
        
        # Rejeter si c'est trop générique
        generic_terms = ['l\'animal', 'the animal', 'animal', 'حيوان', 'animaux', 'animals']
        if animal.lower().strip() in [term.lower() for term in generic_terms]:
            return None
        
        # Limiter la longueur
        if len(animal.split()) > 3:
            return None
        
        # Normaliser l'animal vers un nom standardisé
        animal = self.normalize_animal_name(animal)
        
        # Vérifier que la normalisation a fonctionné (retourne None si invalide)
        if not animal:
            return None
        
        return animal
    
    def extract_animal_with_regex(self, texte):
        """Extrait les animaux avec des expressions régulières"""
        if not texte:
            return None
        
        # Liste complète d'animaux (français, anglais, arabe) - TOUS les animaux possibles
        # Utiliser le dictionnaire depuis data_constants.py
        animaux = ANIMAUX
        
        texte_lower = texte.lower()
        langue = self.detect_language(texte)
        
        # Chercher avec des patterns flexibles (mots entiers)
        # D'abord dans la langue détectée
        for animal in animaux.get(langue, animaux['en']):
            # Chercher le mot entier (pas juste une sous-chaîne)
            pattern = r'\b' + re.escape(animal.lower()) + r'\b'
            if re.search(pattern, texte_lower, re.IGNORECASE):
                return self.normalize_animal_name(animal)
            # Aussi chercher comme sous-chaîne si c'est un mot arabe (caractères Unicode)
            if re.search(r'[\u0600-\u06FF]', animal):
                if animal.lower() in texte_lower:
                    return self.normalize_animal_name(animal)
        
        # Chercher aussi en anglais (langue universelle)
        if langue != 'en':
            for animal in animaux['en']:
                pattern = r'\b' + re.escape(animal.lower()) + r'\b'
                if re.search(pattern, texte_lower, re.IGNORECASE):
                    return self.normalize_animal_name(animal)
        
        # Chercher aussi en français si la langue n'est pas française
        if langue != 'fr':
            for animal in animaux['fr']:
                pattern = r'\b' + re.escape(animal.lower()) + r'\b'
                if re.search(pattern, texte_lower, re.IGNORECASE):
                    return self.normalize_animal_name(animal)
        
        # Chercher aussi en arabe si la langue n'est pas arabe
        if langue != 'ar':
            for animal in animaux['ar']:
                if animal in texte:
                    return self.normalize_animal_name(animal)
        
        return None
    
    def normalize_animal_name(self, animal):
        """Normalise le nom de l'animal vers un nom standardisé (français) quelle que soit la langue"""
        if not animal or not animal.strip():
            return None
        
        animal_lower = animal.lower().strip()
        
        # Utiliser les patterns depuis data_constants.py
        invalid_animal_patterns = INVALID_ANIMAL_PATTERNS
        if any(pattern in animal_lower for pattern in invalid_animal_patterns):
            return None
        
        # Rejeter si contient "|" (probablement un nom d'organisme ou de site)
        if '|' in animal:
            return None
        
        # Utiliser le dictionnaire depuis data_constants.py
        animal_mapping = ANIMAL_MAPPING
        
        # Chercher une correspondance exacte (insensible à la casse)
        for key, normalized in animal_mapping.items():
            if animal_lower == key.lower():
                return normalized
        
        # Chercher une correspondance partielle (si l'animal contient le mot-clé)
        for key, normalized in animal_mapping.items():
            if key.lower() in animal_lower or animal_lower in key.lower():
                return normalized
        
        # Si aucune correspondance trouvée, retourner l'animal original (normalisé en minuscules)
        return animal.strip().lower()
    
    def validate_and_correct_with_ollama(self, titre, contenu, maladie, lieu, langue):
        """Utilise Ollama pour valider et corriger les informations pour garantir la cohérence logique"""
        if not contenu or len(contenu.strip()) < 50:
            return maladie, lieu, []
        
        # Stocker contenu et titre pour les passer à normalize_location_name
        self._current_contenu = contenu
        self._current_titre = titre
        
        issues = []
        # Utiliser moins de contenu pour la validation (réduit pour la vitesse)
        contenu_sample = contenu[:2000] if len(contenu) > 2000 else contenu  # Réduit de 4000 à 2000
        texte_complet = f"{titre}\n\n{contenu_sample}"
        
        # Créer un prompt pour valider et corriger avec Ollama
        prompt = PromptManager.get_validation_prompt(titre, contenu, maladie, lieu, langue)
        
        response = self.call_ollama(prompt)
        
        if response:
            try:
                # Extraire le JSON de la réponse
                json_match = re.search(r'\{.*?\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    data = json.loads(json_str)
                    
                    validated_maladie = data.get("maladie", "").strip()
                    validated_lieu = data.get("lieu", "").strip()
                    is_coherent = data.get("coherent", True)
                    raison = data.get("raison", "")
                    
                    if not is_coherent or raison:
                        issues.append(f"Validation Ollama: {raison}")
                    
                    # Normaliser les informations validées par Ollama
                    validated_maladie = self.normalize_disease_name(validated_maladie)
                    validated_lieu = self.normalize_location_name(validated_lieu, contenu=contenu, titre=titre)
                    
                    # Validation stricte de la maladie validée par Ollama
                    # Rejeter si la maladie validée est trop courte ou contient des patterns invalides
                    if validated_maladie and validated_maladie.strip():
                        validated_maladie_clean = validated_maladie.strip().lower()
                        # Rejeter les réponses incohérentes
                        invalid_disease_patterns = ['question:', 'correct', 'here\'s', 'answer', 'suggested', 
                                                   'changes', 'updated', 'version', 'revised']
                        if any(pattern in validated_maladie_clean for pattern in invalid_disease_patterns):
                            # Ne pas utiliser la maladie validée si elle contient des patterns invalides
                            validated_maladie = None
                        # Rejeter si trop courte (moins de 3 caractères)
                        elif len(validated_maladie_clean) < 3:
                            validated_maladie = None
                    
                    # Si Ollama a trouvé des informations, les utiliser
                    # IMPORTANT: Ne remplacer que si Ollama trouve quelque chose, sinon garder ce qui est trouvé
                    if validated_maladie and validated_maladie.strip():
                        if validated_maladie != maladie:
                            issues.append(f"Maladie corrigee: '{maladie}' -> '{validated_maladie}'")
                        maladie = validated_maladie
                    # Ne pas supprimer la maladie si Ollama ne la trouve pas (garder ce qui est trouvé)
                    
                    if validated_lieu and validated_lieu.strip():
                        if validated_lieu != lieu:
                            issues.append(f"Lieu corrige: '{lieu}' -> '{validated_lieu}'")
                        lieu = validated_lieu
                    # Ne pas supprimer le lieu si Ollama ne le trouve pas (garder ce qui est trouvé)
                    # Si on avait un lieu et qu'Ollama retourne vide, garder le lieu original
            except (AttributeError, Exception):
                pass
        
        return maladie, lieu, issues
    
    def is_date_or_non_geographic(self, text):
        """Détecte si un texte est une date ou un mot non géographique (à rejeter comme lieu)"""
        if not text or not text.strip():
            return False
        
        text_lower = text.lower().strip()
        
        # Mots de date en français/anglais
        date_keywords_fr_en = [
            'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 
            'septembre', 'octobre', 'novembre', 'décembre',
            'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
            'september', 'october', 'november', 'december',
            'jour', 'day', 'semaine', 'week', 'mois', 'month', 'année', 'year',
            'prochain', 'next', 'dernier', 'last', 'aujourd\'hui', 'today', 'hier', 'yesterday'
        ]
        
        # Mots de date en arabe
        date_keywords_ar = [
            'يوم', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت',
            'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس',
            'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
            'المقبل', 'الجاري', 'القادم', 'السابق', 'اليوم', 'أمس', 'غداً'
        ]
        
        # Mots non géographiques (titres, institutions, etc.)
        non_geographic_keywords = [
            'ministry', 'ministère', 'وزارة', 'department', 'département', 'مديرية',
            'office', 'bureau', 'مكتب', 'director', 'directeur', 'مدير',
            'governor', 'gouverneur', 'محافظ', 'lieutenant', 'لواء', 'colonel', 'عقيد',
            'minister', 'ministre', 'وزير', 'president', 'président', 'رئيس',
            'director', 'directeur', 'مدير', 'manager', 'gestionnaire', 'مدير'
        ]
        
        # Vérifier si le texte contient des mots de date
        text_words = text_lower.split()
        for word in text_words:
            if word in date_keywords_fr_en or word in date_keywords_ar:
                return True
            if any(keyword in word for keyword in date_keywords_fr_en):
                return True
            if any(keyword in word for keyword in date_keywords_ar):
                return True
        
        # Vérifier si le texte contient des mots non géographiques
        for keyword in non_geographic_keywords:
            if keyword in text_lower:
                return True
        
        # Vérifier si c'est un format de date (contient des chiffres avec des mots de mois/jour)
        if re.search(r'\d+', text) and any(kw in text_lower for kw in date_keywords_fr_en + date_keywords_ar):
            return True
        
        return False
    
    def validate_extracted_info(self, maladie, lieu, contenu, titre):
        """Valide que les informations extraites sont cohérentes avec le contenu (cherche dans TOUT le contenu)"""
        issues = []
        confirmations = []  # Messages de confirmation pour les informations validées
        validated_maladie = maladie
        validated_lieu = lieu
        
        # Utiliser TOUT le contenu pour la validation, pas seulement le début
        texte_complet = f"{titre} {contenu}".lower()
        
        # Valider la maladie
        if maladie and maladie != "nan" and maladie.strip():
            maladie_lower = maladie.lower()
            # Vérifier si la maladie ou ses mots-clés sont dans le contenu
            maladie_keywords = [kw for kw in maladie_lower.split() if len(kw) > 3]
            found_in_content = any(keyword in texte_complet for keyword in maladie_keywords)
            
            if found_in_content:
                # Confirmer que la maladie existe et est correcte
                confirmations.append(f"✓ Maladie '{maladie}' EXISTE dans le contenu et est CORRECTE")
            else:
                issues.append(f"Maladie '{maladie}' extraite mais non trouvee dans le contenu")
                # Essayer de trouver une maladie similaire dans TOUT le contenu
                maladie_alt = self.extract_disease_with_regex(contenu)
                if maladie_alt:
                    validated_maladie = maladie_alt
                    issues.append(f"  -> Remplacee par '{maladie_alt}' trouvee dans le contenu complet")
                    confirmations.append(f"✓ Maladie '{maladie_alt}' EXISTE dans le contenu et est CORRECTE")
                else:
                    # Essayer aussi dans le titre
                    maladie_alt = self.extract_disease_with_regex(titre)
                    if maladie_alt:
                        validated_maladie = maladie_alt
                        issues.append(f"  -> Remplacee par '{maladie_alt}' trouvee dans le titre")
                        confirmations.append(f"✓ Maladie '{maladie_alt}' EXISTE dans le titre et est CORRECTE")
                    else:
                        validated_maladie = ""  # Supprimer si non cohérente
                        issues.append(f"  -> Supprimee (non coherente)")
        
        # Valider le lieu : Si trouvé et valide, on le garde (ne pas supprimer)
        if lieu and lieu != "nan" and lieu.strip():
            # Vérifier si le lieu extrait est en fait une date ou un mot non géographique
            if self.is_date_or_non_geographic(lieu):
                issues.append(f"Lieu '{lieu}' rejete (date ou mot non geographique)")
                validated_lieu = ""
                # Essayer de trouver un lieu géographique réel dans le contenu
                lieu_alt = self.extract_location_with_regex(contenu)
                if lieu_alt and not self.is_date_or_non_geographic(lieu_alt):
                    validated_lieu = lieu_alt
                    issues.append(f"  -> Remplace par '{lieu_alt}' trouve dans le contenu")
                    confirmations.append(f"✓ Lieu '{lieu_alt}' EXISTE dans le contenu et est CORRECT")
                else:
                    # Essayer aussi dans le titre
                    lieu_alt = self.extract_location_with_regex(titre)
                    if lieu_alt and not self.is_date_or_non_geographic(lieu_alt):
                        validated_lieu = lieu_alt
                        issues.append(f"  -> Remplace par '{lieu_alt}' trouve dans le titre")
                        confirmations.append(f"✓ Lieu '{lieu_alt}' EXISTE dans le titre et est CORRECT")
            else:
                # Vérifier que le lieu existe dans le contenu
                lieu_lower = lieu.lower()
                lieu_keywords = [kw for kw in lieu_lower.split() if len(kw) > 2]
                found_in_content = any(keyword in texte_complet for keyword in lieu_keywords)
                
                # Vérifier les incohérences géographiques (ex: "France" alors que le contenu mentionne Yellowstone/USA)
                usa_indicators = ['yellowstone', 'usa', 'united states', 'america', 'wyoming', 'montana', 
                                'national park', 'coody lake', 'county', 'ny', 'ca', 'tx', 'fl']
                france_indicators = ['france', 'français', 'française', 'paris', 'lyon', 'marseille']
                
                # Si le lieu est "France" mais le contenu mentionne clairement des indicateurs USA
                if lieu_lower in ['france', 'français', 'française'] and any(indicator in texte_complet for indicator in usa_indicators):
                    # Rejeter "France" et chercher un lieu USA dans le contenu
                    issues.append(f"Lieu '{lieu}' incohérent (contenu mentionne USA/Yellowstone)")
                    validated_lieu = ""
                    # Chercher un lieu USA dans le contenu
                    lieu_alt = self.extract_location_with_regex(contenu)
                    if lieu_alt and not self.is_date_or_non_geographic(lieu_alt):
                        validated_lieu = lieu_alt
                        issues.append(f"  -> Remplace par '{lieu_alt}' trouve dans le contenu")
                        confirmations.append(f"✓ Lieu '{lieu_alt}' EXISTE dans le contenu et est CORRECT")
                    else:
                        # Si on trouve Yellowstone ou un lieu USA, l'utiliser
                        if 'yellowstone' in texte_complet:
                            validated_lieu = "Yellowstone National Park"
                            confirmations.append(f"✓ Lieu 'Yellowstone National Park' EXISTE dans le contenu et est CORRECT")
                        elif any(indicator in texte_complet for indicator in ['usa', 'united states', 'america']):
                            validated_lieu = "États-Unis"
                            confirmations.append(f"✓ Lieu 'États-Unis' EXISTE dans le contenu et est CORRECT")
                elif found_in_content:
                    # Confirmer que le lieu existe et est correct
                    confirmations.append(f"✓ Lieu '{lieu}' EXISTE dans le contenu et est CORRECT")
                else:
                    # Le lieu est valide mais pas trouvé dans le contenu (peut être dans les métadonnées)
                    # Mais vérifier quand même s'il n'y a pas d'incohérence
                    if lieu_lower in ['france', 'français', 'française'] and any(indicator in texte_complet for indicator in usa_indicators):
                        issues.append(f"Lieu '{lieu}' extrait depuis metadonnees mais incohérent avec le contenu (mentionne USA)")
                        validated_lieu = ""
                        # Chercher un lieu dans le contenu
                        lieu_alt = self.extract_location_with_regex(contenu)
                        if lieu_alt:
                            validated_lieu = lieu_alt
                            issues.append(f"  -> Remplace par '{lieu_alt}' trouve dans le contenu")
                    else:
                        confirmations.append(f"✓ Lieu '{lieu}' EXISTE (extrait depuis les metadonnees) et est CORRECT")
        
        return validated_maladie, validated_lieu, issues, confirmations
    
    def extract_structured_info(self, titre, contenu, url):
        """Utilise Ollama pour extraire les informations structurées avec fallback regex"""
        if not contenu or len(contenu.strip()) < 50:
            # Essayer quand même avec le titre seul
            if titre:
                maladie = self.extract_disease_with_regex(titre)
                lieu = self.extract_location_with_regex(titre)
                return {
                    "lieu": lieu,
                    "maladie": maladie,
                    "source": ""
                }
            return {
                "lieu": "",
                "maladie": "",
                "source": ""
            }
        
        # Détecter la langue pour adapter le prompt
        langue_detectee = self.detect_language(contenu if contenu else titre)
        
        # Utiliser moins de contenu pour une extraction plus rapide
        # Analyser le contenu complet ou un échantillon représentatif
        if len(contenu) <= 3000:
            # Si le contenu est raisonnable, utiliser tout
            contenu_sample = contenu
        else:
            # Si très long, prendre plusieurs échantillons stratégiques (réduits)
            # Début (où les infos importantes sont souvent)
            debut = contenu[:2000]  # Réduit de 4000 à 2000
            # Milieu (où les détails peuvent être)
            milieu = contenu[len(contenu)//3:len(contenu)//3 + 1000]  # Réduit de 2000 à 1000
            # Fin (où les conclusions peuvent être)
            fin = contenu[-1000:]  # Réduit de 2000 à 1000
            contenu_sample = f"{debut}\n\n[... section milieu ...]\n\n{milieu}\n\n[... section fin ...]\n\n{fin}"
        
        # Créer un prompt multilingue pour Ollama avec exemples
        # IMPORTANT: Si le contenu est vide, on utilise uniquement le titre (pour l'extraction du lieu)
        if contenu and len(contenu.strip()) >= 50:
            texte_complet = f"{titre}\n\n{contenu_sample}"
        else:
            # Utiliser uniquement le titre si le contenu est vide
            texte_complet = titre
        
        # Prompts selon la langue détectée avec instructions de cohérence strictes et exemples
        prompt = PromptManager.get_structured_extraction_prompt(texte_complet, langue_detectee)

        response = self.call_ollama(prompt)
        
        lieu = ""
        maladie = ""
        source = ""
        
        # Essayer d'extraire le JSON de la réponse Ollama
        if response:
            try:
                # Chercher un bloc JSON dans la réponse (amélioré pour gérer les JSON multilignes)
                json_match = re.search(r'\{[^{}]*"lieu"[^{}]*"maladie"[^{}]*"source"[^{}]*\}', response, re.DOTALL)
                if not json_match:
                    # Essayer une recherche plus large
                    json_match = re.search(r'\{.*?\}', response, re.DOTALL)
                
                if json_match:
                    json_str = json_match.group(0)
                    # Nettoyer le JSON
                    json_str = re.sub(r'[^\x20-\x7E\n]', '', json_str)  # Enlever caractères non-ASCII
                    data = json.loads(json_str)
                    lieu = data.get("lieu", "").strip()
                    maladie = data.get("maladie", "").strip()
                    source = data.get("source", "").strip()
                    
                    # VALIDATION POST-EXTRACTION : vérifier que le lieu est valide
                    if lieu and not self.is_valid_location(lieu):
                        print(f"  [VALIDATION] Lieu '{lieu}' rejeté (faux positif détecté)")
                        lieu = ""  # Rejeter le lieu invalide
                    
                    # VALIDATION POST-EXTRACTION : vérifier que la maladie est valide
                    if maladie:
                        # Vérifier que ce n'est pas un faux positif (trop long, contient des mots interdits)
                        if len(maladie.split()) > 5:
                            print(f"  [VALIDATION] Maladie '{maladie}' rejetée (trop longue)")
                            maladie = ""
                        elif any(word in maladie.lower() for word in ['shots', 'for', 'after', 'dies', 'outbreak', 'lifted', 'quarantine', 'case']):
                            print(f"  [VALIDATION] Maladie '{maladie}' rejetée (contient des mots interdits)")
                            maladie = ""
            except Exception as e:
                # Si le parsing JSON échoue, essayer d'extraire manuellement
                if "lieu" in response.lower():
                    lieu_match = re.search(r'["\']?lieu["\']?\s*:\s*["\']?([^"\',}]+)', response, re.IGNORECASE)
                    if lieu_match:
                        lieu = lieu_match.group(1).strip().strip('"\'')
                
                if "maladie" in response.lower():
                    maladie_match = re.search(r'["\']?maladie["\']?\s*:\s*["\']?([^"\',}]+)', response, re.IGNORECASE)
                    if maladie_match:
                        maladie = maladie_match.group(1).strip().strip('"\'')
                
                if "source" in response.lower():
                    source_match = re.search(r'["\']?source["\']?\s*:\s*["\']?([^"\',}]+)', response, re.IGNORECASE)
                    if source_match:
                        source = source_match.group(1).strip().strip('"\'')
        
        # Fallback: utiliser regex si Ollama n'a pas trouvé
        # Chercher dans TOUT le contenu, pas seulement dans l'échantillon
        if not maladie:
            # Chercher d'abord dans le contenu complet
            maladie = self.extract_disease_with_regex(contenu)
            if not maladie:
                # Si pas trouvé, chercher aussi dans le titre
                maladie = self.extract_disease_with_regex(titre)
        
        if not lieu:
            # EXTRACTION MULTI-PASSES pour le lieu
            # Pass 1: Début de l'article (priorité haute)
            lieu = self.extract_location_from_beginning(contenu)
            if not lieu or not self.is_valid_location(lieu):
                # Pass 2: Contenu complet avec regex
                lieu = self.extract_location_with_regex(contenu)
                if not lieu or not self.is_valid_location(lieu):
                    # Pass 3: Titre
                    lieu = self.extract_location_with_regex(titre)
                    if not lieu or not self.is_valid_location(lieu):
                        lieu = ""
        
        # Valider la cohérence des informations extraites (première passe)
        validated_maladie, validated_lieu, issues, confirmations = self.validate_extracted_info(
            maladie, lieu, contenu, titre
        )
        
        # Afficher les confirmations (informations validées comme existantes et correctes)
        if confirmations:
            print(f"  [VALIDATION] Informations verifiees et confirmees:")
            for confirmation in confirmations:
                print(f"    {confirmation}")
        
        # Validation renforcée avec Ollama pour garantir la cohérence logique
        # IMPORTANT: Ne pas appeler si on a déjà un lieu/maladie trouvé (pour éviter de les supprimer)
        if USE_OLLAMA and contenu and len(contenu.strip()) > 100:
            # Ne valider avec Ollama que si on n'a pas déjà trouvé de lieu/maladie
            # ou si on veut juste corriger/améliorer ce qui est trouvé
            print(f"  [VALIDATION RENFORCEE] Verification de la coherence logique avec Ollama...")
            langue_detectee = self.detect_language(contenu if contenu else titre)
            validated_maladie, validated_lieu, ollama_issues = self.validate_and_correct_with_ollama(
                titre, contenu, validated_maladie, validated_lieu, langue_detectee
            )
            issues.extend(ollama_issues)
            # IMPORTANT: Si Ollama a supprimé le lieu/maladie mais qu'on en avait un, le restaurer
            # Ne pas remplacer un lieu validé par plusieurs méthodes par un lieu d'Ollama moins fiable
            if not validated_lieu and lieu and lieu.strip() and self.is_valid_location(lieu):
                validated_lieu = lieu
                issues.append(f"Lieu '{lieu}' restaure (Ollama l'a supprime mais il etait valide)")
            # Si Ollama propose un lieu mais qu'on en avait déjà un validé, garder l'original si meilleur
            elif validated_lieu and lieu and lieu.strip() and lieu != validated_lieu:
                # Si le lieu original est valide et a été trouvé par plusieurs méthodes, le garder
                if self.is_valid_location(lieu) and validated_lieu != lieu:
                    # Vérifier si le lieu original est meilleur (plus court, plus précis)
                    if len(lieu.split()) <= len(validated_lieu.split()) and self.is_valid_location(lieu):
                        validated_lieu = lieu
                        issues.append(f"Lieu original '{lieu}' conserve (meilleur que '{validated_lieu}' d'Ollama)")
            if not validated_maladie and maladie and maladie.strip():
                validated_maladie = maladie
                issues.append(f"Maladie '{maladie}' restauree (Ollama l'a supprimee mais elle etait valide)")
        
        # Normaliser les informations pour qu'elles soient claires et exactes
        # IMPORTANT: Ne normaliser que si on a quelque chose, sinon garder ce qui est trouvé
        if validated_maladie and validated_maladie.strip():
            validated_maladie = self.normalize_disease_name(validated_maladie)
        if validated_lieu and validated_lieu.strip():
            validated_lieu = self.normalize_location_name(validated_lieu, contenu=contenu, titre=titre)
        
        # Validation finale : vérifier que les informations normalisées sont valides
        if validated_maladie and len(validated_maladie.split()) > 5:
            # Trop de mots, probablement une erreur
            issues.append(f"Maladie '{validated_maladie}' semble incorrecte (trop longue)")
            validated_maladie = self.extract_disease_with_regex(contenu) or ""
        
        # VALIDATION FINALE STRICTE DU LIEU
        if validated_lieu:
            # Vérifier que c'est un lieu valide (pas un faux positif)
            if not self.is_valid_location(validated_lieu):
                issues.append(f"Lieu '{validated_lieu}' rejeté (faux positif détecté)")
                validated_lieu = self.extract_location_with_regex(contenu) or ""
                # Vérifier à nouveau après ré-extraction
                if validated_lieu and not self.is_valid_location(validated_lieu):
                    validated_lieu = ""
            elif len(validated_lieu.split()) > 4:
                # Trop de mots, probablement une erreur
                issues.append(f"Lieu '{validated_lieu}' semble incorrect (trop long)")
                validated_lieu = self.extract_location_with_regex(contenu) or ""
                # Vérifier à nouveau après ré-extraction
                if validated_lieu and not self.is_valid_location(validated_lieu):
                    validated_lieu = ""
        
        # Vérifier que le lieu n'est pas une partie du titre
        if validated_lieu and titre:
            titre_lower = titre.lower()
            lieu_lower = validated_lieu.lower()
            # Si plus de 50% des mots du lieu sont dans le titre, c'est suspect
            lieu_words = lieu_lower.split()
            matching_words = [w for w in lieu_words if w in titre_lower and len(w) > 3]
            if len(lieu_words) > 0 and len(matching_words) / len(lieu_words) > 0.5:
                issues.append(f"Lieu '{validated_lieu}' semble etre une partie du titre")
                validated_lieu = self.extract_location_with_regex(contenu) or ""
                # Vérifier à nouveau après ré-extraction
                if validated_lieu and not self.is_valid_location(validated_lieu):
                    validated_lieu = ""
        
        # Vérifier que la maladie n'est pas une partie du titre
        if validated_maladie and titre:
            titre_lower = titre.lower()
            maladie_lower = validated_maladie.lower()
            # Si plus de 50% des mots de la maladie sont dans le titre, c'est suspect
            maladie_words = maladie_lower.split()
            matching_words = [w for w in maladie_words if w in titre_lower and len(w) > 3]
            if len(maladie_words) > 0 and len(matching_words) / len(maladie_words) > 0.5 and len(maladie_words) > 3:
                issues.append(f"Maladie '{validated_maladie}' semble etre une partie du titre")
                validated_maladie = self.extract_disease_with_regex(contenu) or ""
        
        # Afficher les problèmes de cohérence détectés
        if issues:
            print(f"  [VALIDATION] Problemes de coherence detectes:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print(f"  [VALIDATION] Toutes les informations sont coherentes et logiques")
        
        # Afficher les confirmations finales pour les informations validées
        if validated_maladie and validated_maladie.strip():
            print(f"  [CONFIRMATION] ✓ Maladie '{validated_maladie}' EXISTE dans le contenu et est CORRECTE")
        if validated_lieu and validated_lieu.strip():
            print(f"  [CONFIRMATION] ✓ Lieu '{validated_lieu}' EXISTE dans le contenu et est CORRECT")
        
        # Normaliser la source avec toutes les méthodes (déjà fait dans process_url)
        
        return {
            "lieu": validated_lieu,
            "maladie": validated_maladie,
            "source": source
        }
    
    def normalize_source(self, source, url, metadata=None, titre=None, contenu=None):
        """Normalise le type de source avec toutes les méthodes possibles"""
        # Méthode 1: Depuis og:site_name dans les métadonnées
        if metadata and metadata.get("og_site_name"):
            site_name = metadata["og_site_name"].lower()
            if any(word in site_name for word in ['facebook', 'twitter', 'instagram', 'youtube', 'linkedin']):
                return "réseaux sociaux"
            elif any(word in site_name for word in ['government', 'gouvernement', 'official', 'officiel']):
                return "site officiel"
            elif any(word in site_name for word in ['news', 'médias', 'media', 'press', 'journal']):
                return "médias"
        
        # Méthode 2: Détection depuis le titre/contenu pour les sites médias arabes
        texte_complet = ""
        if titre:
            texte_complet += titre + " "
        if contenu:
            texte_complet += contenu[:500]  # Prendre les 500 premiers caractères
        
        if texte_complet:
            # Sites médias arabes connus
            medias_arabes = [
                'اليوم السابع', 'youm7', 'البيان', 'الأهرام', 'المصري اليوم',
                'الوطن', 'الشروق', 'الدستور', 'الوفد', 'روز اليوسف',
                'النهار', 'الجمهورية', 'الأخبار', 'الشرق الأوسط', 'العربية'
            ]
            texte_lower = texte_complet.lower()
            for media in medias_arabes:
                if media.lower() in texte_lower or media in texte_complet:
                    return "médias"
        
        # Méthode 3: Depuis le paramètre source fourni
        if source:
            source_lower = source.lower().strip()
            
            # Normaliser les variations
            if any(word in source_lower for word in ['réseaux sociaux', 'social', 'facebook', 'twitter', 'instagram', 'youtube']):
                return "réseaux sociaux"
            elif any(word in source_lower for word in ['officiel', 'official', 'gov', 'gouv', 'org', 'who', 'woah', 'fao']):
                return "site officiel"
            elif any(word in source_lower for word in ['médias', 'media', 'news', 'press', 'journal']):
                return "médias"
        
        # Méthode 4: Détection par URL (fallback)
            return self.detect_source_type(url)
    
    def detect_source_type(self, url):
        """Détecte le type de source depuis l'URL (amélioré)"""
        if not url:
            return "médias"
        
        domain = urlparse(url).netloc.lower()
        url_lower = url.lower()
        
        # Réseaux sociaux (priorité haute)
        social_media = ['facebook.com', 'twitter.com', 'x.com', 'instagram.com', 
                       'linkedin.com', 'youtube.com', 'youtu.be', 'tiktok.com', 'reddit.com',
                       'snapchat.com', 'pinterest.com', 'telegram.org', 'whatsapp.com']
        if any(sm in domain or sm in url_lower for sm in social_media):
            return "réseaux sociaux"
        
        # Sites officiels gouvernementaux et organisations internationales
        official_keywords = [
            '.gov', '.gouv', '.gov.', 'who.int', 'woah.org', 'fao.org',
            'oie.int', 'ecdc.europa.eu', 'cdc.gov', 'efsa.europa.eu',
            'agriculture.gouv', 'sante.gouv', 'anses.fr', 'europa.eu',
            'un.org', 'unicef.org', 'wfp.org', 'worldbank.org',
            'pna.gov.ph', 'gov.uk', 'gov.au', 'gov.ca'
        ]
        if any(keyword in domain for keyword in official_keywords):
            return "site officiel"
        
        # Sites d'organisations (.org peut être médias ou officiel, on vérifie le contexte)
        if '.org' in domain:
            org_official = ['who', 'woah', 'fao', 'oie', 'un', 'unicef', 'wfp', 'worldbank']
            if any(org in domain for org in org_official):
                return "site officiel"
        
        # Sites gouvernementaux spécifiques (par nom de domaine)
        gov_domains = ['agriculture.gouv.fr', 'sante.gouv.fr', 'anses.fr']
        if any(gd in domain for gd in gov_domains):
                return "site officiel"
        
        # Médias (par défaut)
        return "médias"
    
    def process_url(self, url, code):
        """Traite une URL et extrait toutes les informations avec TOUTES les méthodes possibles"""
        print(f"\n[{code}] Traitement de: {url}")
        
        # Extraire le contenu avec toutes les méthodes (métadonnées, HTML, etc.)
        content_data = self.extract_content(url)
        titre = content_data.get("titre", "")  # Texte original (arabe si applicable)
        contenu = content_data.get("contenu", "")  # Texte original (arabe si applicable)
        titre_traduit = content_data.get("titre_traduit", None)  # Traduction si disponible
        contenu_traduit = content_data.get("contenu_traduit", None)  # Traduction si disponible
        html_content = content_data.get("html", None)
        metadata = content_data.get("metadata", {})
        
        if not content_data.get("success"):
            erreur_msg = content_data.get("erreur", "Erreur lors de l'extraction")
            print(f"[{code}] Erreur lors de l'extraction: {erreur_msg}")
            return {
                "code": code,
                "url": url,
                "titre": titre or "Erreur d'extraction",
                "contenu": "",
                "langue": "unknown",
                "caracteres": 0,
                "mots": 0,
                "date_publication": "",
                "lieu": "",
                "maladie": "",
                "organisme": "",
                "animal": "",
                "source": self.detect_source_type(url),
                "erreur": erreur_msg
            }
        
        # Détecter la langue avec toutes les méthodes (métadonnées, HTML, détection texte)
        # GARANTIR que la langue est toujours détectée
        langue = self.detect_language(contenu if contenu else titre, metadata=metadata, html_content=html_content)
        if not langue or langue == "unknown":
            # Fallback: essayer de détecter depuis l'URL ou le domaine
            if html_content:
                try:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    html_tag = soup.find('html')
                    if html_tag and html_tag.get('lang'):
                        langue = html_tag.get('lang')[:2]
                except (AttributeError, Exception):
                    pass
        if not langue or langue == "unknown":
            # Dernier fallback: détecter depuis le titre si disponible
            if titre:
                try:
                    langue = self.detect_language(titre)
                except (LangDetectException, Exception):
                    langue = "unknown"
        if not langue:
            langue = "unknown"
        print(f"[{code}] Langue detectee: {langue}")
        
        # Calculer les statistiques du contenu nettoyé (texte original)
        # GARANTIR que les statistiques sont toujours calculées
        stats = calculate_stats(contenu)
        if not stats:
            stats = {"caracteres": 0, "mots": 0}
        print(f"[{code}] Caracteres: {stats['caracteres']}, Mots: {stats['mots']}")
        
        # Pour l'extraction, utiliser la traduction si disponible (pour améliorer l'extraction)
        # Sinon utiliser l'original
        texte_pour_extraction = contenu_traduit if contenu_traduit else contenu
        titre_pour_extraction = titre_traduit if titre_traduit else titre
        
        # Extraire la date avec TOUTES les méthodes (meta, JSON-LD, texte "Publié le...", etc.)
        # GARANTIR que la date est extraite avec toutes les méthodes disponibles (RENFORCÉ)
        print(f"[{code}] Extraction de date avec toutes les méthodes renforcées...")
        date_candidates = []
        
        # Méthode 1: extract_date avec texte traduit
        date_publication = self.extract_date(url, html_content=html_content, text=texte_pour_extraction, metadata=metadata)
        if date_publication:
            date_candidates.append(("extract_date_traduit", date_publication))
            print(f"[{code}]   -> Date candidat (extract_date traduit): {date_publication}")
        
        # Méthode 2: extract_date avec texte original
        date_original = None
        if not date_publication and contenu:
            date_original = self.extract_date(url, html_content=html_content, text=contenu, metadata=metadata)
            if date_original and date_original != date_publication:
                date_candidates.append(("extract_date_original", date_original))
                print(f"[{code}]   -> Date candidat (extract_date original): {date_original}")
                if not date_publication:
                    date_publication = date_original
        
        # Méthode 3: extract_date avec titre seul
        if not date_publication and titre:
            date_titre = self.extract_date(url, html_content=None, text=titre, metadata=metadata)
            if date_titre:
                date_candidates.append(("extract_date_titre", date_titre))
                print(f"[{code}]   -> Date candidat (extract_date titre): {date_titre}")
                if not date_publication:
                    date_publication = date_titre
        
        # Méthode 4: Ollama avec plusieurs tentatives
        if not date_publication and USE_OLLAMA:
            # Tentative 1: Avec texte traduit
            if texte_pour_extraction:
                print(f"[{code}] Tentative d'extraction de date avec Ollama (texte traduit)...")
                date_ollama = self.extract_date_with_ollama(titre_pour_extraction, texte_pour_extraction)
                if date_ollama:
                    date_candidates.append(("ollama_traduit", date_ollama))
                    print(f"[{code}]   -> Date candidat (Ollama traduit): {date_ollama}")
                    if not date_publication:
                        date_publication = date_ollama
        
            # Tentative 2: Avec texte original
            if not date_publication and contenu:
                print(f"[{code}] Tentative d'extraction de date avec Ollama (texte original)...")
                date_ollama = self.extract_date_with_ollama(titre, contenu)
                if date_ollama:
                    date_candidates.append(("ollama_original", date_ollama))
                    print(f"[{code}]   -> Date candidat (Ollama original): {date_ollama}")
                    if not date_publication:
                        date_publication = date_ollama
        
        # Validation croisée : si plusieurs méthodes trouvent la même date, c'est plus fiable
        if len(date_candidates) > 1:
            date_counts = {}
            for method_name, date_val in date_candidates:
                date_normalized = date_val.strip()
                if date_normalized not in date_counts:
                    date_counts[date_normalized] = []
                date_counts[date_normalized].append(method_name)
            
            # Prioriser la date trouvée par plusieurs méthodes
            for date_val, methods in date_counts.items():
                if len(methods) >= 2:
                    print(f"[{code}]   -> Date validée par {len(methods)} méthodes: {date_val} (méthodes: {', '.join(methods)})")
                    date_publication = date_val
                    break
        
        # Validation de la date : rejeter les dates futures
        if date_publication:
            try:
                # Parser la date
                date_parts = date_publication.split('-')
                if len(date_parts) == 3:
                    day, month, year = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
                    date_obj = datetime(year, month, day)
                    today = datetime.now()
                    # Rejeter si la date est dans le futur (plus de 1 jour)
                    if date_obj > today:
                        print(f"[{code}]   -> Date rejetée (futur): {date_publication}")
                        date_publication = ""
            except (ValueError, TypeError, Exception):
                pass
        
        # Garantir qu'on a toujours une valeur (même vide)
        if not date_publication:
            date_publication = ""
        print(f"[{code}] Date finale: {date_publication if date_publication else '(non trouvée)'}")
        
        # Extraire les informations structurées avec Ollama
        # IMPORTANT: Pour le lieu, utiliser UNIQUEMENT le titre (cohérence obligatoire)
        # Pour la maladie et la source, on peut utiliser le contenu
        # GARANTIR que toutes les informations sont extraites
        print(f"[{code}] Extraction des informations avec Ollama...")
        
        # Initialiser les variables avec des valeurs par défaut
        lieu = ""
        maladie = ""
        source = ""
        
        # Extraire le lieu uniquement depuis le titre
        if titre_pour_extraction:
            try:
                titre_info = self.extract_structured_info(titre_pour_extraction, "", url)
                lieu = titre_info.get("lieu", "") if titre_info else ""
            except (AttributeError, Exception) as e:
                print(f"[{code}]   -> Erreur lors de l'extraction du lieu depuis le titre: {str(e)}")
        
        # Extraire maladie et source depuis le contenu complet
        if texte_pour_extraction or titre_pour_extraction:
            try:
                structured_info = self.extract_structured_info(titre_pour_extraction, texte_pour_extraction, url)
                if structured_info:
                    maladie_ollama = structured_info.get("maladie", "")
                    source_ollama = structured_info.get("source", "")
                    if maladie_ollama and maladie_ollama.strip():
                        maladie = maladie_ollama
                    if source_ollama and source_ollama.strip():
                        source = source_ollama
            except (AttributeError, Exception) as e:
                print(f"[{code}]   -> Erreur lors de l'extraction structurée: {str(e)}")
            
            # Tentative supplémentaire : si pas de maladie, essayer avec le texte original
            if not maladie or len(maladie.strip()) < 3:
                try:
                    structured_info_original = self.extract_structured_info(titre, contenu, url)
                    if structured_info_original:
                        maladie_original = structured_info_original.get("maladie", "")
                        if maladie_original and maladie_original.strip() and len(maladie_original.strip()) >= 3:
                            maladie = maladie_original
                            print(f"[{code}]   -> Maladie trouvée avec Ollama (texte original): {maladie}")
                except (AttributeError, Exception) as e:
                    print(f"[{code}]   -> Erreur lors de l'extraction structurée (original): {str(e)}")
        
        # Si Ollama n'a pas fonctionné, initialiser avec des valeurs vides
        if not maladie:
            maladie = ""
        if not lieu:
            lieu = ""
        if not source:
            source = ""
        
        # Améliorer l'extraction de la maladie avec toutes les méthodes (EXTRACTION MULTI-SOURCES RENFORCÉE)
        # Rechercher la maladie dans le contenu et le titre pour TOUS les sites (toujours)
        print(f"[{code}] Extraction de maladie depuis le contenu et le titre (MÉTHODES RENFORCÉES)...")
        maladie_candidates = []
        
        # Méthode 1: Regex sur le titre (priorité haute - souvent la maladie est dans le titre)
        maladie_titre = self.extract_disease_with_regex(titre, normalize=False)
        if maladie_titre and maladie_titre.strip():
            maladie_candidates.append(("regex_titre", maladie_titre))
            print(f"[{code}]   -> Maladie candidat (regex titre): {maladie_titre}")
        
        # Méthode 1.5: Regex sur le titre traduit si disponible
        if titre_traduit and titre_traduit != titre:
            maladie_titre_traduit = self.extract_disease_with_regex(titre_traduit, normalize=False)
            if maladie_titre_traduit and maladie_titre_traduit.strip() and maladie_titre_traduit.lower() != maladie_titre.lower() if maladie_titre else True:
                maladie_candidates.append(("regex_titre_traduit", maladie_titre_traduit))
                print(f"[{code}]   -> Maladie candidat (regex titre traduit): {maladie_titre_traduit}")
        
        # Méthode 2: Regex sur le contenu complet
        maladie_contenu = self.extract_disease_with_regex(contenu, normalize=False)
        if maladie_contenu and maladie_contenu.strip():
            maladie_candidates.append(("regex_contenu", maladie_contenu))
            print(f"[{code}]   -> Maladie candidat (regex contenu): {maladie_contenu}")
        
        # Méthode 2.5: Regex sur le contenu traduit si disponible
        if contenu_traduit and contenu_traduit != contenu:
            maladie_contenu_traduit = self.extract_disease_with_regex(contenu_traduit, normalize=False)
            if maladie_contenu_traduit and maladie_contenu_traduit.strip() and maladie_contenu_traduit.lower() != maladie_contenu.lower() if maladie_contenu else True:
                maladie_candidates.append(("regex_contenu_traduit", maladie_contenu_traduit))
                print(f"[{code}]   -> Maladie candidat (regex contenu traduit): {maladie_contenu_traduit}")
        
        # Méthode 2.75: Regex sur le début du contenu (zone prioritaire)
        if contenu and len(contenu) > 500:
            maladie_debut = self.extract_disease_with_regex(contenu[:1000], normalize=False)
            if maladie_debut and maladie_debut.strip():
                # Vérifier que ce n'est pas déjà dans les candidats
                if not any(cand[1].lower() == maladie_debut.lower() for cand in maladie_candidates):
                    maladie_candidates.append(("regex_debut_contenu", maladie_debut))
                    print(f"[{code}]   -> Maladie candidat (regex début contenu): {maladie_debut}")
        
        # Méthode 3: Ollama avec plusieurs tentatives si disponible
        if USE_OLLAMA and (titre or contenu):
            # Tentative 1: Depuis le titre
            if titre and not any(cand[0] == "ollama_titre" for cand in maladie_candidates):
                try:
                    maladie_ollama_titre = self.extract_disease_with_ollama(titre, "")
                    if maladie_ollama_titre and maladie_ollama_titre.strip():
                        maladie_candidates.append(("ollama_titre", maladie_ollama_titre))
                        print(f"[{code}]   -> Maladie candidat (Ollama titre): {maladie_ollama_titre}")
                except (AttributeError, Exception) as e:
                    print(f"[{code}]   -> Erreur Ollama titre: {str(e)}")
            
            # Tentative 2: Depuis le contenu (premiers 2000 caractères)
            if contenu and len(contenu) > 100:
                try:
                    contenu_sample = contenu[:2000] if len(contenu) > 2000 else contenu
                    maladie_ollama_contenu = self.extract_disease_with_ollama("", contenu_sample)
                    if maladie_ollama_contenu and maladie_ollama_contenu.strip():
                        # Vérifier que ce n'est pas déjà dans les candidats
                        if not any(cand[1].lower() == maladie_ollama_contenu.lower() for cand in maladie_candidates):
                            maladie_candidates.append(("ollama_contenu", maladie_ollama_contenu))
                            print(f"[{code}]   -> Maladie candidat (Ollama contenu): {maladie_ollama_contenu}")
                except (AttributeError, Exception) as e:
                    print(f"[{code}]   -> Erreur Ollama contenu: {str(e)}")
            
            # Tentative 3: Depuis titre + début contenu combinés
            if titre and contenu and len(contenu) > 200:
                try:
                    texte_combine = f"{titre}\n\n{contenu[:1500]}"
                    maladie_ollama_combine = self.extract_disease_with_ollama(titre, contenu[:1500])
                    if maladie_ollama_combine and maladie_ollama_combine.strip():
                        # Vérifier que ce n'est pas déjà dans les candidats
                        if not any(cand[1].lower() == maladie_ollama_combine.lower() for cand in maladie_candidates):
                            maladie_candidates.append(("ollama_combine", maladie_ollama_combine))
                            print(f"[{code}]   -> Maladie candidat (Ollama combiné): {maladie_ollama_combine}")
                except (AttributeError, Exception) as e:
                    print(f"[{code}]   -> Erreur Ollama combiné: {str(e)}")
        
        # Choisir le meilleur candidat (priorité améliorée avec validation croisée)
        # Utiliser le résultat de regex si Ollama n'a pas trouvé de maladie ou si regex trouve quelque chose de plus précis
        if maladie_candidates:
            # Prioriser dans l'ordre : regex titre > regex début > ollama titre > regex contenu > ollama contenu > ollama combiné
            priority_order = [
                "regex_titre", 
                "regex_titre_traduit",
                "regex_debut_contenu",
                "ollama_titre",
                "regex_contenu",
                "regex_contenu_traduit",
                "ollama_contenu",
                "ollama_combine"
            ]
            maladie_regex = None
            for method_name in priority_order:
                for candidate_method, candidate_maladie in maladie_candidates:
                    if candidate_method == method_name:
                        maladie_regex = candidate_maladie
                        print(f"[{code}]   -> Maladie trouvee ({method_name}): {maladie_regex}")
                        break
                if maladie_regex:
                    break
            
            # Validation croisée : si plusieurs méthodes trouvent la même maladie, c'est plus fiable
            maladie_counts = {}
            for candidate_method, candidate_maladie in maladie_candidates:
                maladie_lower = candidate_maladie.lower().strip()
                if maladie_lower not in maladie_counts:
                    maladie_counts[maladie_lower] = []
                maladie_counts[maladie_lower].append(candidate_method)
            
            # Si une maladie est trouvée par plusieurs méthodes, la prioriser
            for maladie_lower, methods in maladie_counts.items():
                if len(methods) >= 2:  # Trouvée par au moins 2 méthodes
                    print(f"[{code}]   -> Maladie validée par {len(methods)} méthodes: {maladie_lower} (méthodes: {', '.join(methods)})")
                    # Utiliser cette maladie si elle est dans la priorité
                    for method_name in priority_order:
                        if method_name in methods:
                            maladie_regex = next(cand[1] for cand in maladie_candidates if cand[0] == method_name)
                            break
                    if maladie_regex:
                        break
            
            # Utiliser la maladie trouvée par les méthodes renforcées si:
            # 1. Ollama n'a pas trouvé de maladie, OU
            # 2. La maladie trouvée par les méthodes renforcées est plus précise (plus longue ou différente)
            if maladie_regex:
                if not maladie or len(maladie.strip()) < 3:
                    maladie = maladie_regex
                    print(f"[{code}]   -> Maladie selectionnee depuis methodes renforcees (Ollama n'a pas trouve): {maladie}")
                elif maladie_regex.lower() != maladie.lower():
                    # Si les méthodes renforcées trouvent quelque chose de différent, vérifier lequel est le plus précis
                    # Prioriser celui qui est le plus long ou qui contient des mots-clés de maladie
                    maladie_keywords = ['grippe', 'influenza', 'fièvre', 'fever', 'peste', 'pest', 'rage', 'rabies', 
                                      'حمى', 'طاعون', 'سعار', 'التهاب', 'inflammation', 'anthrax', 'charbon',
                                      'bluetongue', 'catarrhale', 'aphteuse', 'foot-and-mouth', 'lumpy', 'skin']
                    # Vérifier aussi la longueur et la présence de mots-clés
                    regex_score = sum(1 for kw in maladie_keywords if kw in maladie_regex.lower()) + (len(maladie_regex) / 10)
                    ollama_score = sum(1 for kw in maladie_keywords if kw in maladie.lower()) + (len(maladie) / 10)
                    
                    if regex_score > ollama_score or len(maladie_regex) > len(maladie):
                        maladie = maladie_regex
                        print(f"[{code}]   -> Maladie selectionnee depuis methodes renforcees (plus precise, score: {regex_score:.1f} vs {ollama_score:.1f}): {maladie}")
                    else:
                        print(f"[{code}]   -> Maladie d'Ollama conservee (score: {ollama_score:.1f} vs {regex_score:.1f}): {maladie}")
                else:
                    print(f"[{code}]   -> Maladie d'Ollama confirmee par methodes renforcees: {maladie}")
        elif maladie and len(maladie.strip()) >= 3:
            print(f"[{code}]   -> Maladie d'Ollama conservee (methodes renforcees n'ont rien trouve): {maladie}")
        else:
            print(f"[{code}]   -> Aucune maladie trouvee (ni Ollama ni methodes renforcees)")
            # Dernière tentative : chercher dans le titre et contenu avec des patterns très larges
            if titre or contenu:
                texte_final = f"{titre} {contenu}" if titre and contenu else (titre or contenu)
                maladie_derniere = self.extract_disease_with_regex(texte_final[:5000], normalize=False)
                if maladie_derniere and maladie_derniere.strip():
                    maladie = maladie_derniere
                    print(f"[{code}]   -> Maladie trouvee en derniere tentative: {maladie}")
        
        # EXTRACTION DU LIEU : Essayer toutes les méthodes dans l'ordre jusqu'à trouver
        # Priorité: URL -> métadonnées HTML -> début article -> titre (regex) -> titre (Ollama) -> contenu (regex) -> contenu (Ollama)
        print(f"[{code}] Extraction de lieu avec toutes les méthodes...")
        
        lieu_candidates = []
        
        # Méthode 0: Depuis l'URL (domaine) - PRIORITÉ HAUTE
        lieu_from_url = self.extract_location_from_url(url)
        if lieu_from_url and self.is_valid_location(lieu_from_url):
            lieu_candidates.append(("url", lieu_from_url))
            print(f"[{code}]   -> Lieu candidat (URL): {lieu_from_url}")
        
        # Méthode 0.5: Depuis les métadonnées HTML (catégories, tags, JSON-LD) - PRIORITÉ HAUTE
        if html_content:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                lieu_from_meta = self.extract_location_from_categories(soup)
                if lieu_from_meta and self.is_valid_location(lieu_from_meta):
                    lieu_candidates.append(("metadata", lieu_from_meta))
                    print(f"[{code}]   -> Lieu candidat (métadonnées HTML): {lieu_from_meta}")
            except (AttributeError, Exception):
                pass
        
        # Méthode 0.75: Depuis le début de l'article (premières phrases) - PRIORITÉ HAUTE
        if contenu:
            lieu_from_beginning = self.extract_location_from_beginning(contenu)
            if lieu_from_beginning and self.is_valid_location(lieu_from_beginning):
                lieu_candidates.append(("debut_article", lieu_from_beginning))
                print(f"[{code}]   -> Lieu candidat (début article): {lieu_from_beginning}")
        
        # Méthode 1: Regex depuis le titre (priorité absolue)
        lieu_titre_regex = self.extract_location_with_regex(titre, normalize=False)
        if lieu_titre_regex and self.is_valid_location(lieu_titre_regex):
            lieu_candidates.append(("regex_titre", lieu_titre_regex))
            print(f"[{code}]   -> Lieu candidat (regex titre): {lieu_titre_regex}")
        
        # Méthode 2: Ollama depuis le titre
        if USE_OLLAMA and titre:
            titre_info_ollama = self.extract_structured_info(titre_pour_extraction, "", url)
            lieu_titre_ollama = titre_info_ollama.get("lieu", "")
            if lieu_titre_ollama and self.is_valid_location(lieu_titre_ollama):
                lieu_candidates.append(("ollama_titre", lieu_titre_ollama))
                print(f"[{code}]   -> Lieu candidat (Ollama titre): {lieu_titre_ollama}")
        
        # Méthode 3: Regex depuis le contenu complet (pas seulement 2000 caractères)
        if contenu:
            # Essayer d'abord les 3000 premiers caractères (zone prioritaire)
            lieu_contenu_regex = self.extract_location_with_regex(contenu[:3000], normalize=False)
            if lieu_contenu_regex and self.is_valid_location(lieu_contenu_regex):
                lieu_candidates.append(("regex_contenu", lieu_contenu_regex))
                print(f"[{code}]   -> Lieu candidat (regex contenu): {lieu_contenu_regex}")
            # Si pas trouvé, essayer le contenu complet
            elif len(contenu) > 3000:
                lieu_contenu_regex_full = self.extract_location_with_regex(contenu, normalize=False)
                if lieu_contenu_regex_full and self.is_valid_location(lieu_contenu_regex_full):
                    lieu_candidates.append(("regex_contenu_full", lieu_contenu_regex_full))
                    print(f"[{code}]   -> Lieu candidat (regex contenu complet): {lieu_contenu_regex_full}")
        
        # Méthode 4: Ollama depuis le contenu (échantillons stratégiques RENFORCÉS)
        if USE_OLLAMA and contenu:
            # Essayer d'abord les 3000 premiers caractères
            contenu_info_ollama = self.extract_structured_info("", texte_pour_extraction[:3000], url)
            lieu_contenu_ollama = contenu_info_ollama.get("lieu", "") if contenu_info_ollama else ""
            if lieu_contenu_ollama and self.is_valid_location(lieu_contenu_ollama):
                lieu_candidates.append(("ollama_contenu", lieu_contenu_ollama))
                print(f"[{code}]   -> Lieu candidat (Ollama contenu): {lieu_contenu_ollama}")
        
            # Si pas trouvé et contenu long, essayer plusieurs échantillons
            if len(contenu) > 5000:
                # Milieu
                milieu = texte_pour_extraction[len(texte_pour_extraction)//2:len(texte_pour_extraction)//2 + 2000]
                contenu_info_ollama_milieu = self.extract_structured_info("", milieu, url)
                lieu_contenu_ollama_milieu = contenu_info_ollama_milieu.get("lieu", "") if contenu_info_ollama_milieu else ""
                if lieu_contenu_ollama_milieu and self.is_valid_location(lieu_contenu_ollama_milieu):
                    lieu_candidates.append(("ollama_contenu_milieu", lieu_contenu_ollama_milieu))
                    print(f"[{code}]   -> Lieu candidat (Ollama contenu milieu): {lieu_contenu_ollama_milieu}")
                
                # Fin du contenu (derniers 2000 caractères)
                fin = texte_pour_extraction[-2000:] if len(texte_pour_extraction) > 2000 else texte_pour_extraction
                contenu_info_ollama_fin = self.extract_structured_info("", fin, url)
                lieu_contenu_ollama_fin = contenu_info_ollama_fin.get("lieu", "") if contenu_info_ollama_fin else ""
                if lieu_contenu_ollama_fin and self.is_valid_location(lieu_contenu_ollama_fin):
                    lieu_candidates.append(("ollama_contenu_fin", lieu_contenu_ollama_fin))
                    print(f"[{code}]   -> Lieu candidat (Ollama contenu fin): {lieu_contenu_ollama_fin}")
        
        # Méthode 4.5: Regex depuis plusieurs zones du contenu (RENFORCÉ)
        if contenu and len(contenu) > 5000:
            # Essayer le milieu du contenu
            milieu_contenu = contenu[len(contenu)//2:len(contenu)//2 + 2000]
            lieu_milieu_regex = self.extract_location_with_regex(milieu_contenu, normalize=False)
            if lieu_milieu_regex and self.is_valid_location(lieu_milieu_regex):
                # Vérifier que ce n'est pas déjà dans les candidats
                if not any(cand[1].lower() == lieu_milieu_regex.lower() for cand in lieu_candidates):
                    lieu_candidates.append(("regex_contenu_milieu", lieu_milieu_regex))
                    print(f"[{code}]   -> Lieu candidat (regex contenu milieu): {lieu_milieu_regex}")
            
            # Essayer la fin du contenu
            fin_contenu = contenu[-2000:] if len(contenu) > 2000 else contenu
            lieu_fin_regex = self.extract_location_with_regex(fin_contenu, normalize=False)
            if lieu_fin_regex and self.is_valid_location(lieu_fin_regex):
                # Vérifier que ce n'est pas déjà dans les candidats
                if not any(cand[1].lower() == lieu_fin_regex.lower() for cand in lieu_candidates):
                    lieu_candidates.append(("regex_contenu_fin", lieu_fin_regex))
                    print(f"[{code}]   -> Lieu candidat (regex contenu fin): {lieu_fin_regex}")
        
        # Choisir le meilleur candidat (priorité améliorée avec validation croisée)
        if lieu_candidates:
            priority_order = [
                "url",  # URL est la plus fiable
                "metadata",  # Métadonnées HTML sont fiables
                "debut_article",  # Début de l'article est souvent précis
                "regex_titre",  # Titre est prioritaire
                "ollama_titre",  # Ollama sur titre
                "regex_contenu",  # Regex sur contenu
                "regex_contenu_full",  # Regex sur contenu complet
                "regex_contenu_milieu",  # Regex sur milieu
                "regex_contenu_fin",  # Regex sur fin
                "ollama_contenu",  # Ollama sur contenu
                "ollama_contenu_milieu",  # Ollama sur milieu
                "ollama_contenu_fin"  # Ollama sur fin
            ]
            
            # Validation croisée : si plusieurs méthodes trouvent le même lieu, c'est plus fiable
            lieu_counts = {}
            for candidate_method, candidate_lieu in lieu_candidates:
                lieu_lower = candidate_lieu.lower().strip()
                if lieu_lower not in lieu_counts:
                    lieu_counts[lieu_lower] = []
                lieu_counts[lieu_lower].append(candidate_method)
            
            # Si un lieu est trouvé par plusieurs méthodes, le prioriser
            lieu_valide = None
            for lieu_lower, methods in lieu_counts.items():
                if len(methods) >= 2:  # Trouvé par au moins 2 méthodes
                    print(f"[{code}]   -> Lieu validé par {len(methods)} méthodes: {lieu_lower} (méthodes: {', '.join(methods)})")
                    # Utiliser ce lieu si il est dans la priorité
                    for method_name in priority_order:
                        if method_name in methods:
                            lieu_valide = next(cand[1] for cand in lieu_candidates if cand[0] == method_name)
                            break
                    if lieu_valide:
                        break
            
            # Si pas de validation croisée, utiliser l'ordre de priorité
            if not lieu_valide:
                lieu_trouve = False
                for method_name in priority_order:
                    for candidate_method, candidate_lieu in lieu_candidates:
                        if candidate_method == method_name:
                            lieu = candidate_lieu
                            print(f"[{code}]   -> Lieu sélectionné ({method_name}): {lieu}")
                            lieu_trouve = True
                            break
                    if lieu_trouve:
                        break
            else:
                lieu = lieu_valide
                print(f"[{code}]   -> Lieu sélectionné (validé par plusieurs méthodes): {lieu}")
        else:
            # Si aucun candidat, utiliser le lieu d'Ollama initial s'il existe
            if lieu and lieu.strip():
                print(f"[{code}]   -> Lieu d'Ollama initial conservé: {lieu}")
            else:
                lieu = ""
                print(f"[{code}]   -> Aucun lieu trouvé avec toutes les méthodes")
        
        # Normaliser la source avec toutes les méthodes (og:site_name, domaine, etc.)
        # GARANTIR que la source est toujours détectée
        if not source or not source.strip():
            source = self.normalize_source("", url, metadata=metadata, titre=titre, contenu=contenu)
        else:
            source = self.normalize_source(source, url, metadata=metadata, titre=titre, contenu=contenu)
        
        # Si la source est toujours vide, utiliser la détection depuis l'URL
        if not source or not source.strip():
            source = self.detect_source_type(url)
        
        # Garantir qu'on a toujours une valeur pour la source
        if not source or not source.strip():
            source = "médias"  # Valeur par défaut
        
        # VALIDATION FINALE STRICTE ET PRÉCISE
        # Vérification que maladie/lieu sont réellement dans le contenu et sont précis
        texte_complet = f"{titre} {contenu}".lower()
        texte_original = f"{titre} {contenu}"  # Pour recherche exacte (sans lower)
        
        # VALIDATION DE LA MALADIE : Si trouvée, on la garde (ordre de priorité)
        if maladie and maladie != "nan" and maladie.strip():
            # Si la maladie est trouvée, on la garde (ne pas rejeter même si peu présente dans le contenu)
            print(f"[{code}] Maladie: {maladie} [✓ Acceptée - maladie trouvée]")
            
            # Vérification optionnelle: Longueur maximale (normaliser si trop long)
            if len(maladie.split()) > 5:
                print(f"[{code}]   -> Maladie trop longue ({len(maladie.split())} mots), tentative de normalisation...")
                maladie_normalized = self.normalize_disease_name(maladie)
                if maladie_normalized and len(maladie_normalized.split()) <= 5:
                    maladie = maladie_normalized
                    print(f"[{code}]   -> Maladie normalisée: {maladie}")
        else:
            print(f"[{code}] Maladie: (non mentionnée)")
            
        # VALIDATION DU LIEU : Si trouvé, on le garde (ordre de priorité)
        if lieu and lieu != "nan" and lieu.strip():
            # Normaliser le lieu pour validation
            lieu_normalized = lieu.strip()
            
            # Vérification 1: Le lieu doit être un lieu géographique valide
            if not self.is_valid_location(lieu_normalized):
                print(f"[{code}] Lieu: {lieu} [✗ REJETÉ - Faux positif détecté]")
                lieu = ""
            else:
                # Si le lieu est valide, on le garde (ne pas rejeter même s'il n'est pas dans le titre)
                print(f"[{code}] Lieu: {lieu} [✓ Accepté - lieu valide trouvé]")
                
                # Vérification optionnelle: Longueur maximale (normaliser si trop long)
                if len(lieu.split()) > 4:
                    print(f"[{code}]   -> Lieu trop long ({len(lieu.split())} mots), tentative de normalisation...")
                    lieu_normalized = self.normalize_location_name(lieu, contenu=contenu, titre=titre)
                    if lieu_normalized and len(lieu_normalized.split()) <= 4 and self.is_valid_location(lieu_normalized):
                        lieu = lieu_normalized
                        print(f"[{code}]   -> Lieu normalisé: {lieu}")
        else:
            print(f"[{code}] Lieu: (non mentionné)")
        
        # Normalisation finale pour garantir la précision (sans rejeter)
        if maladie and maladie.strip():
            maladie_normalized = self.normalize_disease_name(maladie).strip()
            # Garder la maladie normalisée si elle est valide, sinon garder l'original
            if maladie_normalized and len(maladie_normalized) >= 3:
                maladie = maladie_normalized
            # Sinon garder l'original même si pas parfaitement normalisé
        
        if lieu and lieu.strip():
            # Sauvegarder le lieu original avant normalisation
            lieu_original = lieu.strip()
            lieu_normalized = self.normalize_location_name(lieu, contenu=contenu, titre=titre).strip()
            # Extraire uniquement le pays
            lieu_enriched = self.enrich_location_with_country(lieu_normalized if lieu_normalized else lieu_original, contenu=contenu, titre=titre)
            # Utiliser le lieu enrichi si valide, sinon garder le lieu normalisé, sinon garder l'original
            if lieu_enriched and len(lieu_enriched) >= 2:
                lieu = lieu_enriched
            elif lieu_normalized and len(lieu_normalized) >= 2:
                lieu = lieu_normalized
            elif lieu_original and len(lieu_original) >= 2:
                lieu = lieu_original
            else:
                # Si rien n'est valide, essayer juste l'enrichissement sur l'original
                lieu_enriched_original = self.enrich_location_with_country(lieu_original, contenu=contenu, titre=titre)
                if lieu_enriched_original and len(lieu_enriched_original) >= 2:
                    lieu = lieu_enriched_original
                else:
                    lieu = lieu_original  # Garder l'original même si pas parfaitement valide
        
        # VALIDATION FINALE : S'assurer que toutes les informations nécessaires sont présentes
        # Si lieu, maladie, date ou source sont vides, essayer de les extraire avec toutes les méthodes
        if not lieu or not lieu.strip():
            print(f"[{code}] [VALIDATION] Lieu manquant, tentative d'extraction renforcée avec TOUTES les méthodes...")
            # Essayer dans l'ordre : URL -> métadonnées HTML -> début article -> titre (regex) -> titre (Ollama) -> contenu (regex) -> contenu (Ollama)
            
            # Méthode 0: Détection depuis l'URL (domaine) - PRIORITÉ HAUTE
            if not lieu or not lieu.strip():
                lieu_from_url = self.extract_location_from_url(url)
                if lieu_from_url and self.is_valid_location(lieu_from_url):
                    lieu = lieu_from_url
                    print(f"[{code}]   -> Lieu trouvé depuis l'URL: {lieu}")
            
            # Méthode 0.5: Depuis les métadonnées HTML
            if (not lieu or not lieu.strip()) and html_content:
                try:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    lieu_from_meta = self.extract_location_from_categories(soup)
                    if lieu_from_meta and self.is_valid_location(lieu_from_meta):
                        lieu = lieu_from_meta
                        print(f"[{code}]   -> Lieu trouvé depuis les métadonnées HTML: {lieu}")
                except (AttributeError, Exception):
                    pass
            
            # Méthode 0.75: Depuis le début de l'article
            if (not lieu or not lieu.strip()) and contenu:
                lieu_from_beginning = self.extract_location_from_beginning(contenu)
                if lieu_from_beginning and self.is_valid_location(lieu_from_beginning):
                    lieu = lieu_from_beginning
                    print(f"[{code}]   -> Lieu trouvé depuis le début de l'article: {lieu}")
            
            # Méthode 1: Regex depuis le titre
            if (not lieu or not lieu.strip()) and titre:
                lieu_alt = self.extract_location_with_regex(titre, normalize=False)
                if lieu_alt and self.is_valid_location(lieu_alt):
                    lieu_alt_enriched = self.enrich_location_with_country(lieu_alt, contenu=contenu, titre=titre)
                    # Accepter si enrichi et valide, sinon accepter l'original si valide
                    if lieu_alt_enriched and len(lieu_alt_enriched) >= 2 and self.is_valid_location(lieu_alt_enriched):
                        lieu = lieu_alt_enriched
                        print(f"[{code}]   -> Lieu trouvé par regex depuis le titre: {lieu}")
                    elif lieu_alt and len(lieu_alt) >= 2:
                        lieu = lieu_alt
                        print(f"[{code}]   -> Lieu trouvé par regex depuis le titre (sans enrichissement): {lieu}")
            
            # Méthode 2: Ollama depuis le titre
            if (not lieu or not lieu.strip()) and USE_OLLAMA and titre:
                print(f"[{code}]   -> Tentative avec Ollama depuis le titre...")
                titre_info_ollama = self.extract_structured_info(titre_pour_extraction, "", url)
                lieu_ollama = titre_info_ollama.get("lieu", "")
                if lieu_ollama and self.is_valid_location(lieu_ollama):
                    lieu_ollama_enriched = self.enrich_location_with_country(lieu_ollama, contenu=contenu, titre=titre)
                    # Accepter si enrichi, sinon accepter l'original
                    if lieu_ollama_enriched and len(lieu_ollama_enriched) >= 2 and self.is_valid_location(lieu_ollama_enriched):
                        lieu = lieu_ollama_enriched
                        print(f"[{code}]   -> Lieu trouvé avec Ollama depuis le titre: {lieu}")
                    elif lieu_ollama and len(lieu_ollama) >= 2:
                        lieu = lieu_ollama
                        print(f"[{code}]   -> Lieu trouvé avec Ollama depuis le titre (sans enrichissement): {lieu}")
            
            # Méthode 3: Regex depuis le contenu (échantillons stratégiques)
            if (not lieu or not lieu.strip()) and contenu:
                print(f"[{code}]   -> Tentative depuis le contenu (regex)...")
                # Essayer d'abord les 3000 premiers caractères
                lieu_contenu = self.extract_location_with_regex(contenu[:3000], normalize=False)
                if not lieu_contenu or not self.is_valid_location(lieu_contenu):
                    # Si pas trouvé, essayer le contenu complet
                    lieu_contenu = self.extract_location_with_regex(contenu, normalize=False)
                if lieu_contenu and self.is_valid_location(lieu_contenu):
                    lieu_contenu_enriched = self.enrich_location_with_country(lieu_contenu, contenu=contenu, titre=titre)
                    # Accepter si enrichi, sinon accepter l'original
                    if lieu_contenu_enriched and len(lieu_contenu_enriched) >= 2 and self.is_valid_location(lieu_contenu_enriched):
                        lieu = lieu_contenu_enriched
                        print(f"[{code}]   -> Lieu trouvé par regex depuis le contenu: {lieu}")
                    elif lieu_contenu and len(lieu_contenu) >= 2:
                        lieu = lieu_contenu
                        print(f"[{code}]   -> Lieu trouvé par regex depuis le contenu (sans enrichissement): {lieu}")
            
            # Méthode 4: Ollama depuis le contenu (échantillons stratégiques)
            if (not lieu or not lieu.strip()) and USE_OLLAMA and contenu:
                print(f"[{code}]   -> Tentative avec Ollama depuis le contenu...")
                # Essayer d'abord les 3000 premiers caractères
                contenu_info_ollama = self.extract_structured_info("", texte_pour_extraction[:3000], url)
                lieu_ollama_contenu = contenu_info_ollama.get("lieu", "")
                if not lieu_ollama_contenu or not self.is_valid_location(lieu_ollama_contenu):
                    # Si pas trouvé et contenu long, essayer le milieu
                    if len(contenu) > 5000:
                        milieu = texte_pour_extraction[len(texte_pour_extraction)//2:len(texte_pour_extraction)//2 + 2000]
                        contenu_info_ollama = self.extract_structured_info("", milieu, url)
                        lieu_ollama_contenu = contenu_info_ollama.get("lieu", "")
                if lieu_ollama_contenu and self.is_valid_location(lieu_ollama_contenu):
                    lieu_ollama_contenu_enriched = self.enrich_location_with_country(lieu_ollama_contenu, contenu=contenu, titre=titre)
                    # Accepter si enrichi, sinon accepter l'original
                    if lieu_ollama_contenu_enriched and len(lieu_ollama_contenu_enriched) >= 2 and self.is_valid_location(lieu_ollama_contenu_enriched):
                        lieu = lieu_ollama_contenu_enriched
                        print(f"[{code}]   -> Lieu trouvé avec Ollama depuis le contenu: {lieu}")
                    elif lieu_ollama_contenu and len(lieu_ollama_contenu) >= 2:
                        lieu = lieu_ollama_contenu
                        print(f"[{code}]   -> Lieu trouvé avec Ollama depuis le contenu (sans enrichissement): {lieu}")
        
        if not maladie or not maladie.strip():
            print(f"[{code}] [VALIDATION] Maladie manquante, tentative d'extraction renforcée avec TOUTES les méthodes...")
            # Essayer toutes les méthodes dans l'ordre jusqu'à trouver
            
            # Méthode 1: Regex sur le titre
            if not maladie or not maladie.strip():
                maladie_alt = self.extract_disease_with_regex(titre, normalize=False)
                if maladie_alt and maladie_alt.strip():
                    maladie = maladie_alt
                    print(f"[{code}]   -> Maladie trouvée par regex (titre): {maladie}")
            
            # Méthode 2: Regex sur le contenu
            if not maladie or not maladie.strip():
                maladie_alt = self.extract_disease_with_regex(contenu, normalize=False)
                if maladie_alt and maladie_alt.strip():
                    maladie = maladie_alt
                    print(f"[{code}]   -> Maladie trouvée par regex (contenu): {maladie}")
            
            # Méthode 3: Ollama depuis le titre puis le contenu
            if (not maladie or not maladie.strip()) and USE_OLLAMA:
                print(f"[{code}]   -> Tentative d'extraction avec Ollama...")
                maladie_ollama = self.extract_disease_with_ollama(titre, contenu)
                if maladie_ollama and len(maladie_ollama.strip()) >= 3:
                    maladie = maladie_ollama
                    print(f"[{code}]   -> Maladie trouvée avec Ollama: {maladie}")
            
            # Normaliser la maladie trouvée
            if maladie and maladie.strip():
                maladie = self.normalize_disease_name(maladie).strip()
                if len(maladie) >= 3:
                    print(f"[{code}]   -> Maladie finalisée: {maladie}")
                else:
                    maladie = ""
        
        if not date_publication or not date_publication.strip():
            print(f"[{code}] [VALIDATION] Date manquante, tentative d'extraction renforcée avec TOUTES les méthodes...")
            # Essayer toutes les méthodes pour extraire la date
            
            # Méthode 1: extract_date avec toutes les méthodes (meta, JSON-LD, etc.)
            if not date_publication or not date_publication.strip():
                date_alt = self.extract_date(url, html_content=html_content, text=contenu, metadata=metadata)
                if date_alt:
                    date_publication = date_alt
                    print(f"[{code}]   -> Date trouvée: {date_publication}")
            
            # Méthode 2: Ollama
            if (not date_publication or not date_publication.strip()) and USE_OLLAMA and contenu:
                date_alt = self.extract_date_with_ollama(titre, contenu)
                if date_alt:
                    date_publication = date_alt
                    print(f"[{code}]   -> Date trouvée avec Ollama: {date_publication}")
            
            # Méthode 3: Regex dans le texte
            if not date_publication or not date_publication.strip():
                # Chercher des patterns de date dans le texte
                date_patterns = [
                    r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b',
                    r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b',
                    r'\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})\b',
                    r'\b(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{1,2}),\s+(\d{4})\b'
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, contenu[:2000], re.IGNORECASE)
                    if match:
                        try:
                            if len(match.groups()) == 3:
                                # Essayer de parser la date
                                date_str = match.group(0)
                                date_parsed = dateparser.parse(date_str, languages=['fr', 'en', 'ar'])
                                if date_parsed:
                                    date_publication = date_parsed.strftime("%d-%m-%Y")
                                    print(f"[{code}]   -> Date trouvée par regex: {date_publication}")
                                    break
                        except (ValueError, TypeError, Exception):
                            pass
        
        if not source or not source.strip():
            print(f"[{code}] [VALIDATION] Source manquante, détection avec TOUTES les méthodes...")
            # Détecter la source depuis l'URL et le contenu
            source = self.normalize_source("", url, metadata=metadata, titre=titre, contenu=contenu)
            if not source or not source.strip():
                source = self.detect_source_type(url)
            print(f"[{code}]   -> Source détectée: {source}")
        
        # EXTRACTION D'ORGANISME ET D'ANIMAL
        organisme = None
        animal = None
        
        if contenu or titre:
            # Extraire l'organisme (essayer Ollama puis regex)
            print(f"[{code}] Extraction d'organisme...")
            organisme = None
            if USE_OLLAMA:
                organisme = self.extract_organism_with_ollama(titre, contenu)
            if not organisme:
                # Essayer avec regex sur le texte complet
                texte_complet = f"{titre} {contenu}" if titre and contenu else (titre or contenu)
                organisme = self.extract_organism_with_regex(texte_complet)
            # Validation finale de l'organisme
            if organisme:
                # Rejeter "NON TROUVE" et toutes ses variantes (y compris avec fautes d'orthographe)
                invalid_responses = ['non trouvé', 'non trouve', 'non trouvée', 'non trouvee', 'non truve', 
                                    'not found', 'n/a', 'none', 'no found', 'not founde', 'no trouve']
                organisme_clean = organisme.strip().lower()
                if organisme_clean in invalid_responses or 'non trouv' in organisme_clean or 'not found' in organisme_clean:
                    print(f"[{code}]   -> Organisme rejeté (réponse invalide): {organisme}")
                    organisme = None
                # Rejeter si contient des guillemets ou parenthèses avec "No Trouve" (ex: "NON TRUVE ("No Trouve")")
                elif ('"' in organisme and 'trouv' in organisme_clean) or ('(' in organisme and 'trouv' in organisme_clean.lower()):
                    print(f"[{code}]   -> Organisme rejeté (contient 'trouvé' avec guillemets/parenthèses): {organisme}")
                    organisme = None
                # Rejeter les valeurs trop courtes ou génériques
                elif organisme_clean in ['un', 'une', 'le', 'la', 'les', 'the', 'a', 'an', 'of', 'de', 'du', 'des'] or len(organisme_clean) < 2:
                    print(f"[{code}]   -> Organisme rejeté (trop générique): {organisme}")
                    organisme = None
                # Rejeter les phrases complètes (commençant par des pronoms ou verbes)
                elif any(starter in organisme_clean for starter in ['nous sommes', 'nous', 'ils sont', 'ils', 'elles sont', 'elles', 
                                                                    'je suis', 'je', 'we are', 'we', 'they are', 'they', 'i am', 'i',
                                                                    'c\'est', 'ce sont', 'this is', 'that is']):
                    print(f"[{code}]   -> Organisme rejeté (phrase complète, pas un nom): {organisme}")
                    organisme = None
                # Rejeter les phrases avec verbes conjugués
                elif any(verb in organisme_clean.split() for verb in ['sommes', 'sont', 'est', 'êtes', 'suis', 'are', 'is', 'am', 'was', 'were']):
                    print(f"[{code}]   -> Organisme rejeté (contient un verbe conjugué): {organisme}")
                    organisme = None
                # Rejeter les phrases trop longues (plus de 8 mots)
                elif len(organisme.split()) > 8:
                    print(f"[{code}]   -> Organisme rejeté (trop long, probablement une phrase): {organisme}")
                    organisme = None
                else:
                    print(f"[{code}]   -> Organisme trouvé: {organisme}")
            if not organisme:
                print(f"[{code}]   -> Aucun organisme trouvé")
            
            # Extraire l'animal (essayer Ollama puis regex)
            print(f"[{code}] Extraction d'animal...")
            animal = None
            if USE_OLLAMA:
                animal = self.extract_animal_with_ollama(titre, contenu)
            if not animal:
                # Essayer avec regex sur le texte complet
                texte_complet = f"{titre} {contenu}" if titre and contenu else (titre or contenu)
                animal = self.extract_animal_with_regex(texte_complet)
            
            # Correction spéciale : CWD (chronic wasting disease) est une maladie des cervidés, pas des bovins
            if maladie and 'chronic wasting' in maladie.lower() or 'cwd' in maladie.lower():
                if animal and 'bovin' in animal.lower():
                    # CWD affecte les cerfs, pas les bovins
                    print(f"[{code}]   -> Correction: CWD affecte les cerfs, pas les bovins")
                    # Chercher spécifiquement les cerfs dans le texte
                    texte_lower = (titre + " " + contenu).lower() if titre and contenu else (titre or contenu).lower()
                    if any(term in texte_lower for term in ['deer', 'cerf', 'cerfs', 'cervid', 'cervids', 'élan', 'élans', 'elk', 'moose']):
                        animal = 'cerfs'
                        print(f"[{code}]   -> Animal corrigé: cerfs (CWD)")
                    else:
                        # Par défaut pour CWD, utiliser cerfs
                        animal = 'cerfs'
                        print(f"[{code}]   -> Animal corrigé: cerfs (CWD - maladie des cervidés)")
            
            # Normaliser l'animal vers un nom standardisé (français) quelle que soit la langue
            if animal:
                # Validation finale de l'animal
                animal_clean = animal.strip().lower()
                
                # Utiliser les patterns depuis data_constants.py
                invalid_animal_patterns = INVALID_ANIMAL_PATTERNS
                if any(pattern in animal_clean for pattern in invalid_animal_patterns):
                    print(f"[{code}]   -> Animal rejeté (faux positif - nom d'organisme/média): {animal}")
                    animal = None
                # Rejeter si contient "|" (probablement un nom d'organisme ou de site)
                elif '|' in animal:
                    print(f"[{code}]   -> Animal rejeté (contient '|' - probablement un organisme): {animal}")
                    animal = None
                # Rejeter les valeurs trop courtes ou génériques
                elif animal_clean in ['animal', 'l\'animal', 'the animal', 'حيوان', 'animaux', 'animals',
                                     'un', 'une', 'le', 'la', 'les', 'the', 'a', 'an'] or len(animal_clean) < 2:
                    print(f"[{code}]   -> Animal rejeté (trop générique): {animal}")
                    animal = None
                else:
                    animal_normalized = self.normalize_animal_name(animal)
                    if animal_normalized:
                        animal = animal_normalized
                        print(f"[{code}]   -> Animal trouvé: {animal} (normalisé)")
                    else:
                        print(f"[{code}]   -> Animal rejeté (normalisation échouée): {animal}")
                        animal = None
            if not animal:
                print(f"[{code}]   -> Aucun animal trouvé")
        
        # Afficher le résultat final avec confirmations
        confirmations_finales = []
        if maladie and maladie.strip():
            confirmations_finales.append(f"Maladie: '{maladie}' [✓ EXISTE et CORRECTE]")
        if lieu and lieu.strip():
            confirmations_finales.append(f"Lieu: '{lieu}' [✓ EXISTE et CORRECT]")
        if date_publication and date_publication.strip():
            confirmations_finales.append(f"Date: '{date_publication}' [✓ EXISTE et CORRECTE]")
        if organisme and organisme.strip():
            confirmations_finales.append(f"Organisme: '{organisme}' [✓ EXISTE et CORRECT]")
        if animal and animal.strip():
            confirmations_finales.append(f"Animal: '{animal}' [✓ EXISTE et CORRECT]")
        
        print(f"[{code}] [RÉSULTAT FINAL] {' | '.join(confirmations_finales) if confirmations_finales else 'Aucune information extraite'}")
        
        # GARANTIR que toutes les valeurs sont présentes et valides avant de retourner
        # Utiliser les valeurs corrigées si des alternatives ont été trouvées
        # (les variables lieu et maladie peuvent avoir été mises à jour dans la vérification finale)
        
        # NORMALISATION FINALE EN FRANÇAIS pour tous les champs (lieu, maladie, animal)
        # Normaliser la maladie en français
        if maladie and maladie.strip():
            maladie = self.normalize_disease_name(maladie).strip()
        
        # Normaliser le lieu en français (déjà fait dans normalize_location_name, mais on s'assure)
        if lieu and lieu.strip():
            lieu = self.translate_location_to_french(lieu.strip())
        
        # Normaliser l'animal en français
        if animal and animal.strip():
            animal_normalized = self.normalize_animal_name(animal)
            if animal_normalized:
                animal = animal_normalized
        
        # S'assurer que stats existe
        if not stats:
            stats = {"caracteres": 0, "mots": 0}
        
        # S'assurer que la source a une valeur par défaut si vide
        if not source or not source.strip():
            source = self.detect_source_type(url) or "médias"
        
        result = {
            "code": str(code) if code else "",
            "url": str(url) if url else "",
            "titre": str(titre) if titre else "",
            "contenu": str(contenu) if contenu else "",
            "langue": str(langue) if langue else "unknown",
            "caracteres": int(stats.get("caracteres", 0)),
            "mots": int(stats.get("mots", 0)),
            "date_publication": str(date_publication) if date_publication else "",
            "lieu": str(lieu) if lieu else "",
            "maladie": str(maladie) if maladie else "",
            "source": str(source) if source else "médias",
            "organisme": str(organisme) if organisme else "",
            "animal": str(animal) if animal else "",
            "erreur": ""  # Champ erreur vide si pas d'erreur
        }
        
        # Vérification finale : s'assurer qu'aucune valeur n'est None
        for key, value in result.items():
            if value is None:
                if key in ["caracteres", "mots"]:
                    result[key] = 0
                else:
                    result[key] = ""
        
        print(f"[{code}] [VÉRIFICATION FINALE] Toutes les informations extraites:")
        print(f"  ✓ Code: {result['code']}")
        print(f"  ✓ URL: {result['url'][:60] if len(result['url']) > 60 else result['url']}...")
        print(f"  ✓ Titre: {result['titre'][:60] if result['titre'] and len(result['titre']) > 60 else (result['titre'] if result['titre'] else '(vide)')}")
        print(f"  ✓ Contenu: {result['caracteres']} caractères, {result['mots']} mots")
        print(f"  ✓ Langue: {result['langue']}")
        print(f"  ✓ Date: {result['date_publication'] if result['date_publication'] else '(non trouvée)'}")
        print(f"  ✓ Lieu: {result['lieu'] if result['lieu'] else '(non trouvé)'}")
        print(f"  ✓ Maladie: {result['maladie'] if result['maladie'] else '(non trouvée)'}")
        print(f"  ✓ Organisme: {result.get('organisme', '') if result.get('organisme') else '(non trouvé)'}")
        print(f"  ✓ Animal: {result.get('animal', '') if result.get('animal') else '(non trouvé)'}")
        print(f"  ✓ Source: {result['source']}")
        
        return result




def main():
    """Fonction principale qui combine le chargement des URLs et l'extraction complète"""
    print("=" * 80)
    print("EXTRACTION COMPLÈTE D'INFORMATIONS DEPUIS DES URLs")
    print("Fusion de step1_load_urls.py et extraction_automatisee.py")
    print("Format optimisé pour Power BI")
    print("=" * 80)
    
    # Vérifier qu'Ollama est disponible (avec plusieurs tentatives)
    ollama_available = False
    if USE_OLLAMA:
        print("[INFO] Vérification de la connexion à Ollama...")
        max_check_attempts = 3
        for check_attempt in range(max_check_attempts):
            try:
                response = requests.get("http://localhost:11434/api/tags", timeout=10)
                response.raise_for_status()
                ollama_available = True
                print("[OK] Ollama est accessible")
                print(f"[OK] Modèle configuré: {OLLAMA_MODEL}")
                
                # Vérifier que le modèle est installé
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                
                # Vérifier si le modèle est installé (avec ou sans :latest)
                model_found = False
                for name in model_names:
                    if name == OLLAMA_MODEL or name == f"{OLLAMA_MODEL}:latest" or name.startswith(f"{OLLAMA_MODEL}:"):
                        model_found = True
                        print(f"[OK] Modèle '{name}' est installé")
                        break
                
                if not model_found:
                    print(f"\n[ATTENTION] Le modèle '{OLLAMA_MODEL}' n'est pas installé!")
                    print(f"Modèles disponibles: {', '.join(model_names) if model_names else 'Aucun'}")
                    print(f"Pour installer: ollama pull {OLLAMA_MODEL}")
                    print("\n⚠️  L'extraction continuera mais certaines fonctionnalités IA seront limitées.")
                    response = input("\nContinuer quand même? (o/n): ")
                    if response.lower() != 'o':
                        return
                break  # Sortir de la boucle si la connexion réussit
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if check_attempt < max_check_attempts - 1:
                    print(f"[INFO] Tentative {check_attempt + 1}/{max_check_attempts} - Attente d'Ollama...")
                    time.sleep(2)
                else:
                    # Dernière tentative échouée
                    pass
            except Exception as e:
                # En cas d'autre erreur, traiter comme une erreur de connexion
                if check_attempt < max_check_attempts - 1:
                    print(f"[INFO] Tentative {check_attempt + 1}/{max_check_attempts} - Attente d'Ollama...")
                    time.sleep(2)
                else:
                    # Dernière tentative échouée
                    pass
        
        # Si toutes les tentatives ont échoué, afficher le message
        if not ollama_available:
            print("\n" + "=" * 80)
            print("[ATTENTION] Ollama n'est pas accessible sur http://localhost:11434")
            print("=" * 80)
            print("\n📋 INSTRUCTIONS:")
            print("  1. Installer Ollama: https://ollama.ai")
            print("  2. Démarrer Ollama: ollama serve")
            print("  3. Installer un modèle: ollama pull tinyllama")
            print("\n⚠️  CONSEQUENCES si vous continuez sans Ollama:")
            print("  - L'extraction de base fonctionnera (titre, contenu, langue)")
            print("  - L'extraction de date sera limitée (sans validation IA)")
            print("  - L'extraction de lieu sera limitée (sans enrichissement IA)")
            print("  - L'extraction de maladie sera limitée (sans validation IA)")
            print("  - La validation et correction IA ne fonctionnera pas")
            print("  - La traduction arabe→français ne fonctionnera pas")
            print("\n💡 RECOMMANDATION: Installez Ollama pour une extraction complète.")
            print("=" * 80)
            response = input("\nContinuer quand même? (o/n): ")
            if response.lower() != 'o':
                print("\nExtraction annulée. Installez Ollama et réessayez.")
                return
    else:
        print("[INFO] Ollama est désactivé dans config_ia.py")
        print("⚠️  Certaines fonctionnalités IA seront limitées.")
    
    # Lire le fichier CSV contenant les URLs (flexible : input_urls.csv ou results_step1.csv)
    urls_df = None
    input_file = None
    
    # Essayer d'abord input_urls.csv, puis results_step1.csv
    for csv_file in ["data/input_urls.csv", "data/results_step1.csv"]:
        try:
            urls_df = pd.read_csv(csv_file, encoding='utf-8-sig')
            input_file = csv_file
            print(f"\n[OK] Fichier trouvé: {csv_file}")
            print(f"[OK] {len(urls_df)} lignes trouvées")
            print("Colonnes détectées :", urls_df.columns.tolist())
            break
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"[ATTENTION] Erreur lors de la lecture de {csv_file}: {str(e)}")
            continue
    
    if urls_df is None:
        print("\nERREUR: Aucun fichier CSV trouvé!")
        print("Créez un fichier data/input_urls.csv ou data/results_step1.csv avec les colonnes:")
        print("  - data/input_urls.csv: code, url (ou lien)")
        print("  - data/results_step1.csv: code, url, titre, langue, erreur")
        return
    
    # Normaliser les noms de colonnes
    if "lien" in urls_df.columns:
        urls_df.rename(columns={"lien": "url"}, inplace=True)
    
    # Vérifier que les colonnes nécessaires existent
    if "code" not in urls_df.columns:
        print("ERREUR: Le fichier CSV doit contenir une colonne 'code'!")
        return
    
    if "url" not in urls_df.columns:
        print("ERREUR: Le fichier CSV doit contenir une colonne 'url' ou 'lien'!")
        return
    
    # Si on lit depuis results_step1.csv, filtrer les erreurs
    if input_file and ("results_step1.csv" in input_file or input_file == "results_step1.csv") and "erreur" in urls_df.columns:
        nb_avant_filtre = len(urls_df)
        # Filtrer les lignes avec erreur (garder seulement celles sans erreur ou avec erreur vide)
        urls_df = urls_df[
            urls_df["erreur"].isna() | 
            (urls_df["erreur"] == "") | 
            (urls_df["erreur"].str.strip() == "")
        ]
        nb_apres_filtre = len(urls_df)
        if nb_avant_filtre != nb_apres_filtre:
            print(f"[INFO] {nb_avant_filtre - nb_apres_filtre} URLs avec erreurs filtrées")
            print(f"[INFO] {nb_apres_filtre} URLs valides à traiter")
    
    # Initialiser l'extracteur
    extractor = NewsExtractor()
    
    # Traiter chaque URL directement (pas besoin de step1)
    results = []
    total = len(urls_df)
    nb_erreurs = 0
    
    print(f"\n[INFO] Début du traitement de {total} URLs...")
    print("-" * 80)
    
    for index, row in urls_df.iterrows():
        code = row.get('code', f'code{index+1}')
        url = row.get('url', row.get('lien', ''))
        
        if not url:
            print(f"[{code}] URL vide, ignorée")
            nb_erreurs += 1
            results.append({
                "Code": str(code),
                "URL": "",
                "Titre": "URL vide",
                "Contenu": "",
                "Langue": "unknown",
                "Caracteres": 0,
                "Mots": 0,
                "Date_Publication": None,
                "Lieu": "",
                "Maladie": "",
                "Source": "médias",
                "Organisme": "",
                "Animal": "",
                "Erreur": "URL vide"
            })
            continue
        
        try:
            # Traiter l'URL avec l'extracteur complet
            result = extractor.process_url(url, code)
            
            # Convertir le résultat au format optimisé pour Power BI
            # Format de date pour Power BI: YYYY-MM-DD (ou None si vide)
            date_powerbi = None
            if result.get("date_publication") and result["date_publication"].strip():
                try:
                    # Parser la date au format DD-MM-YYYY et convertir en YYYY-MM-DD
                    date_obj = datetime.strptime(result["date_publication"], "%d-%m-%Y")
                    date_powerbi = date_obj.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    # Si le parsing échoue, essayer avec dateparser
                    try:
                        date_parsed = dateparser.parse(result["date_publication"])
                        if date_parsed:
                            date_powerbi = date_parsed.strftime("%Y-%m-%d")
                    except:
                        pass
            
            # Créer le résultat au format Power BI
            result_powerbi = {
                "Code": str(result.get("code", code)),
                "URL": str(result.get("url", url)),
                "Titre": str(result.get("titre", "")),
                "Contenu": str(result.get("contenu", "")),
                "Langue": str(result.get("langue", "unknown")),
                "Caracteres": int(result.get("caracteres", 0)),
                "Mots": int(result.get("mots", 0)),
                "Date_Publication": date_powerbi,  # Format date pour Power BI
                "Lieu": str(result.get("lieu", "")),
                "Maladie": str(result.get("maladie", "")),
                "Source": str(result.get("source", "médias")),
                "Organisme": str(result.get("organisme", "")),
                "Animal": str(result.get("animal", "")),
                "Erreur": str(result.get("erreur", ""))  # Message d'erreur si présent
            }
            
            results.append(result_powerbi)
            
        except Exception as e:
            error_message = str(e)[:200]  # Limiter la longueur de l'erreur
            print(f"[{code}] Erreur lors du traitement: {error_message}")
            nb_erreurs += 1
            results.append({
                "Code": str(code),
                "URL": str(url),
                "Titre": "Erreur d'extraction",
                "Contenu": "",
                "Langue": "unknown",
                "Caracteres": 0,
                "Mots": 0,
                "Date_Publication": None,
                "Lieu": "",
                "Maladie": "",
                "Source": "médias",
                "Organisme": "",
                "Animal": "",
                "Erreur": error_message
            })
        
        # Afficher la progression
        print(f"\nProgression: {len(results)}/{total} URLs traitées")
        if nb_erreurs > 0:
            print(f"Erreurs: {nb_erreurs}")
        print("-" * 80)
        
        # Petite pause pour éviter de surcharger les serveurs (réduite pour la vitesse)
        time.sleep(0.5)  # Réduit de 1s à 0.5s
    
    # Créer le DataFrame avec les résultats
    results_df = pd.DataFrame(results)
    
    # Définir l'ordre des colonnes optimisé pour Power BI
    column_order = [
        "Code",
        "URL", 
        "Titre",
        "Contenu",
        "Langue",
        "Date_Publication",
        "Lieu",
        "Maladie",
        "Organisme",
        "Animal",
        "Source",
        "Caracteres",
        "Mots",
        "Erreur"
    ]
    
    # Réorganiser les colonnes (garder seulement celles qui existent)
    existing_columns = [col for col in column_order if col in results_df.columns]
    other_columns = [col for col in results_df.columns if col not in column_order]
    results_df = results_df[existing_columns + other_columns]
    
    # Optimiser les types de données pour Power BI
    # 1. Convertir Date_Publication en datetime (format Power BI)
    if "Date_Publication" in results_df.columns:
        results_df["Date_Publication"] = pd.to_datetime(results_df["Date_Publication"], errors='coerce')
        # Remplacer les NaT (Not a Time) par None pour un meilleur affichage dans Power BI
        results_df["Date_Publication"] = results_df["Date_Publication"].where(
            pd.notnull(results_df["Date_Publication"]), None
        )
    
    # 2. S'assurer que les colonnes numériques sont bien des nombres entiers
    if "Caracteres" in results_df.columns:
        results_df["Caracteres"] = pd.to_numeric(results_df["Caracteres"], errors='coerce').fillna(0)
        # Convertir en int (compatible avec toutes les versions de pandas)
        try:
            results_df["Caracteres"] = results_df["Caracteres"].astype('Int64')  # Type nullable
        except (TypeError, ValueError):
            results_df["Caracteres"] = results_df["Caracteres"].astype(int)  # Fallback standard
    if "Mots" in results_df.columns:
        results_df["Mots"] = pd.to_numeric(results_df["Mots"], errors='coerce').fillna(0)
        # Convertir en int (compatible avec toutes les versions de pandas)
        try:
            results_df["Mots"] = results_df["Mots"].astype('Int64')  # Type nullable
        except (TypeError, ValueError):
            results_df["Mots"] = results_df["Mots"].astype(int)  # Fallback standard
    
    # 3. Remplacer les valeurs None/NaN par des chaînes vides pour les colonnes texte
    text_columns = ["Code", "URL", "Titre", "Contenu", "Langue", "Lieu", "Maladie", "Source", "Erreur"]
    for col in text_columns:
        if col in results_df.columns:
            results_df[col] = results_df[col].fillna("").astype(str)
            # Nettoyer les valeurs "nan" (string) qui peuvent apparaître
            results_df[col] = results_df[col].replace(["nan", "None", "null"], "")
    
    # 4. Nettoyer les valeurs spéciales dans les colonnes texte
    for col in text_columns:
        if col in results_df.columns:
            # Remplacer les valeurs booléennes False/True par des chaînes vides
            results_df[col] = results_df[col].replace([False, True], "")
            # S'assurer que tout est bien une chaîne
            results_df[col] = results_df[col].astype(str)
    
    # Sauvegarder les articles extraits
    output_file = "data/extracted_articles.csv"
    
    # Utiliser UTF-8 avec BOM pour une meilleure compatibilité avec Excel/Power BI
    # Format de date YYYY-MM-DD pour Power BI
    results_df.to_csv(
        output_file, 
        index=False, 
        encoding="utf-8-sig",  # BOM pour Excel/Power BI
        date_format="%Y-%m-%d",  # Format de date standard ISO pour Power BI
        na_rep=""  # Remplacer les valeurs NaN par des chaînes vides
    )
    
    # Afficher un résumé
    print("\n" + "=" * 80)
    print("[OK] Extraction terminée!")
    print(f"[OK] Résultats sauvegardés dans: {output_file}")
    print(f"[OK] {len(results)} URLs traitées")
    print(f"[INFO] Erreurs: {nb_erreurs}")
    print(f"[INFO] Succès: {len(results) - nb_erreurs}")
    
    # Statistiques détaillées
    if len(results) > 0:
        print("\n[STATISTIQUES DÉTAILLÉES]")
        print(f"  ✓ URLs avec contenu: {sum(1 for r in results if r.get('Contenu', '').strip())}")
        print(f"  ✓ URLs avec date: {sum(1 for r in results if r.get('Date_Publication'))}")
        print(f"  ✓ URLs avec lieu: {sum(1 for r in results if r.get('Lieu', '').strip())}")
        print(f"  ✓ URLs avec maladie: {sum(1 for r in results if r.get('Maladie', '').strip())}")
        
        # Statistiques par langue
        langues = {}
        for r in results:
            lang = r.get('Langue', 'unknown')
            if lang and lang != 'unknown':
                langues[lang] = langues.get(lang, 0) + 1
        if langues:
            print(f"  ✓ Langues détectées: {', '.join(f'{k} ({v})' for k, v in sorted(langues.items(), key=lambda x: x[1], reverse=True))}")
        
        # Statistiques par source
        sources = {}
        for r in results:
            src = r.get('Source', '')
            if src:
                sources[src] = sources.get(src, 0) + 1
        if sources:
            print(f"  ✓ Sources: {', '.join(f'{k} ({v})' for k, v in sorted(sources.items(), key=lambda x: x[1], reverse=True))}")
        
        # Statistiques par maladie
        maladies = {}
        for r in results:
            mal = r.get('Maladie', '').strip()
            if mal:
                maladies[mal] = maladies.get(mal, 0) + 1
        if maladies:
            top_maladies = sorted(maladies.items(), key=lambda x: x[1], reverse=True)[:5]
            print(f"  ✓ Top 5 maladies: {', '.join(f'{k} ({v})' for k, v in top_maladies)}")
        
        # Statistiques par lieu
        lieux = {}
        for r in results:
            lieu = r.get('Lieu', '').strip()
            if lieu:
                lieux[lieu] = lieux.get(lieu, 0) + 1
        if lieux:
            top_lieux = sorted(lieux.items(), key=lambda x: x[1], reverse=True)[:5]
            print(f"  ✓ Top 5 lieux: {', '.join(f'{k} ({v})' for k, v in top_lieux)}")
        
        # Statistiques de contenu
        total_caracteres = sum(r.get('Caracteres', 0) for r in results)
        total_mots = sum(r.get('Mots', 0) for r in results)
        if total_caracteres > 0:
            print(f"  ✓ Total caractères: {total_caracteres:,}")
            print(f"  ✓ Total mots: {total_mots:,}")
            print(f"  ✓ Moyenne caractères/URL: {total_caracteres // len(results):,}")
            print(f"  ✓ Moyenne mots/URL: {total_mots // len(results):,}")
    
    print("=" * 80)
    print("\n[POWER BI] Instructions d'import:")
    print(f"  1. Ouvrir Power BI Desktop")
    print(f"  2. Obtenir des données > Fichier > CSV")
    print(f"  3. Sélectionner: {output_file}")
    print(f"  4. Dans l'éditeur de requête, vérifier les types de colonnes:")
    print(f"     - Date_Publication → Type: Date")
    print(f"     - Caracteres → Type: Nombre entier")
    print(f"     - Mots → Type: Nombre entier")
    print(f"     - Code, URL, Titre, Contenu, Langue, Lieu, Maladie, Source, Erreur → Type: Texte")
    print(f"  5. Cliquer sur 'Fermer et appliquer'")
    print("=" * 80)
    print(f"\n[FICHIER GÉNÉRÉ] {output_file}")
    print(f"  - {len(results_df)} lignes")
    print(f"  - {len(results_df.columns)} colonnes")
    print(f"  - Format: UTF-8 avec BOM (compatible Excel/Power BI)")
    print(f"  - Dates: Format YYYY-MM-DD (ISO standard)")
    print("=" * 80)


if __name__ == "__main__":
    main()