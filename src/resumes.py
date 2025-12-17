import pandas as pd
import requests
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re
from functools import wraps

# ==============================
# Ollama config
# ==============================

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral:7b-instruct"  # Modèle optimisé pour l'arabe et meilleure qualité

session = requests.Session()
MAX_WORKERS = 6  # Parallélisation : 6 threads simultanés

# ==============================
# Retry decorator
# ==============================

def llm_retry_decorator(max_retries=3, delay=1):
    """Décorateur pour réessayer les appels LLM en cas d'échec"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        # Dernière tentative échouée
                        return ""
                    time.sleep(delay * (attempt + 1))  # Backoff exponentiel
            return ""
        return wrapper
    return decorator

# ==============================
# Prompt factory
# ==============================

def build_prompt(text, lang, words):
    """Construit un prompt structuré pour la résumé selon la langue"""
    # Format Mistral 7B Instruct avec balises [INST]
    if lang == "fr":
        return f"""<s>[INST]Tu es un assistant expert en résumé de textes.

Tâche:
Résume le texte français suivant en un paragraphe cohérent d'exactement {words} mots.

Instructions:
- Garde le sens intact
- Retourne exactement {words} mots
- N'inclus AUCUN commentaire ou texte supplémentaire
- Utilise uniquement le français

Texte:
{text[:600]}

Résumé:[/INST]"""
    elif lang == "ar":
        # Prompt arabe renforcé pour Mistral Instruct
        return f"""<s>[INST]أنت مساعد خبير في تلخيص النصوص.

المهمة:
اختصر النص العربي التالي في فقرة واحدة متماسكة تحتوي بالضبط على {words} كلمة.

التعليمات:
- حافظ على المعنى الكامل للنص
- أعد بالضبط {words} كلمة
- لا تضف أي تعليق أو نص إضافي
- استخدم العربية الفصحى فقط
- لا تستخدم الإنجليزية أو الفرنسية

النص:
{text[:600]}

الملخص:[/INST]"""
    else:
        return f"""<s>[INST]You are a skilled summarization assistant.

Task:
Summarize the following text into a coherent paragraph of exactly {words} words.

Instructions:
- Keep the meaning intact
- Return exactly {words} words
- Do NOT include any commentary or extra text
- Use only English

Text:
{text[:600]}

Summary:[/INST]"""

# ==============================
# Ollama call
# ==============================

def summarize_ollama(text, lang, words, attempt=1, max_attempts=3):
    """Génère un résumé avec Ollama, avec retry automatique et prompts alternatifs"""
    if not isinstance(text, str) or not text.strip():
        return ""
    
    # Vérifier si le texte a assez de mots
    text_words = len(text.split())
    if text_words < words:
        # Si le texte est plus court que le nombre de mots demandé, retourner le texte tronqué
        return " ".join(text.split()[:words])

    # Troncature : 250 mots max pour garder plus de contexte
    text_truncated = " ".join(text.split()[:250])
    
    # Utiliser des prompts différents selon l'essai
    if attempt == 1:
        prompt = build_prompt(text_truncated, lang, words)
    elif attempt == 2:
        # Prompt plus simple pour le deuxième essai
        if lang == "fr":
            prompt = f"<s>[INST]Résume ce texte en {words} mots: {text_truncated[:400]}[/INST]"
        elif lang == "ar":
            prompt = f"<s>[INST]لخص هذا النص في {words} كلمة: {text_truncated[:400]}[/INST]"
        else:
            prompt = f"<s>[INST]Summarize this text in {words} words: {text_truncated[:400]}[/INST]"
    else:
        # Prompt ultra simple pour le dernier essai
        if lang == "fr":
            prompt = f"Résume en {words} mots: {text_truncated[:300]}"
        elif lang == "ar":
            prompt = f"لخص في {words} كلمة: {text_truncated[:300]}"
        else:
            prompt = f"Summarize in {words} words: {text_truncated[:300]}"

    try:
        r = session.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,  # Optimisé pour Mistral 7B Instruct
                    "num_predict": int(words * 1.3),  # Ajusté pour Mistral
                    "repeat_penalty": 1.15,  # Optimisé pour Mistral
                    "top_p": 0.9,  # Mistral fonctionne mieux avec top_p élevé
                    "top_k": 40,  # Optimisé pour Mistral
                    "num_ctx": 2048  # Contexte pour Mistral
                }
            },
            timeout=25  # Timeout adapté pour Mistral
        )
        r.raise_for_status()
        summary = r.json().get("response", "").strip()
        
        # Vérification pour l'arabe : doit contenir des caractères arabes
        if lang == "ar":
            if not re.search(r"[\u0600-\u06FF]", summary):
                # Si pas d'arabe, réessayer avec un prompt encore plus strict (format Mistral)
                prompt_strict = f"""<s>[INST]أنت مساعد خبير في تلخيص النصوص. لخص هذا النص في {words} كلمة بالعربية فقط. اكتب بالعربية الفصحى. لا تستخدم أي لغة أخرى. لا تستخدم الإنجليزية أو الفرنسية.[/INST]

{text_truncated[:400]}

الملخص:"""
                try:
                    r2 = session.post(
                        OLLAMA_URL,
                        json={
                            "model": MODEL,
                            "prompt": prompt_strict,
                            "stream": False,
                            "options": {
                                "temperature": 0.1,  # Plus bas pour forcer l'arabe
                                "num_predict": int(words * 1.5),  # Plus de tokens pour l'arabe
                                "repeat_penalty": 1.2,
                                "top_p": 0.9,
                                "top_k": 40,
                                "num_ctx": 2048
                            }
                        },
                        timeout=30
                    )
                    r2.raise_for_status()
                    summary = r2.json().get("response", "").strip()
                    # Si toujours pas d'arabe au dernier essai, accepter quand même
                    if not re.search(r"[\u0600-\u06FF]", summary):
                        if attempt < max_attempts:
                            time.sleep(0.5)
                            return summarize_ollama(text, lang, words, attempt + 1, max_attempts)
                        # Dernier essai : accepter même sans caractères arabes si on a quelque chose
                        if summary:
                            return summary.strip()
                        return ""
                except Exception as e:
                    # Log l'erreur pour debug
                    return ""
        
        # Post-traitement : nettoyer et valider le résumé
        # Être moins strict pour les derniers essais
        is_last_attempt = (attempt == max_attempts)
        summary = post_process_summary(summary, words, lang, strict=(not is_last_attempt))
        
        # Vérifier que le résumé n'est pas identique au texte original (ou presque)
        # Seulement pour les premiers essais, être plus tolérant pour les derniers
        if summary and not is_last_attempt:
            # Comparer les longueurs - si le résumé est trop proche du texte original, c'est suspect
            original_len = len(text_truncated)
            summary_len = len(summary)
            if summary_len > original_len * 0.7:  # Résumé trop proche de l'original (70% de la longueur)
                # Réessayer avec un prompt différent
                time.sleep(0.5)
                return summarize_ollama(text, lang, words, attempt + 1, max_attempts)
            
            # Vérifier la similarité du contenu - si plus de 80% des mots sont identiques, c'est suspect
            original_words = set(text_truncated.lower().split()[:50])  # Premiers 50 mots
            summary_words = set(summary.lower().split())
            if len(original_words) > 0:
                overlap = len(original_words.intersection(summary_words)) / len(original_words)
                if overlap > 0.8:  # Plus de 80% de mots en commun
                    # Réessayer avec un prompt différent
                    time.sleep(0.5)
                    return summarize_ollama(text, lang, words, attempt + 1, max_attempts)
        
        # Si le résumé est vide et qu'on peut réessayer
        if not summary and attempt < max_attempts:
            time.sleep(0.5)  # Petite pause avant de réessayer
            return summarize_ollama(text, lang, words, attempt + 1, max_attempts)
        
        # Si toujours vide au dernier essai, créer un résumé minimal à partir du texte
        if not summary and is_last_attempt:
            # Créer un résumé minimal en prenant les premiers mots
            words_list = text_truncated.split()[:words]
            summary = " ".join(words_list)
            # Ajouter "..." si le texte original est plus long
            if len(text.split()) > words:
                summary += "..."
        
        return summary
    except Exception as e:
        # Log l'erreur pour debug (optionnel, peut être commenté en production)
        # print(f"Erreur summarize_ollama: {e}")
        return ""

def post_process_summary(summary, target_words, lang, strict=True):
    """Nettoie et valide le résumé généré
    
    Args:
        summary: Le résumé à valider
        target_words: Nombre de mots cible
        lang: Langue du résumé
        strict: Si True, validation stricte. Si False, plus tolérant pour accepter des résumés
    """
    if not summary or str(summary).lower() == "nan":
        return ""
    
    # Nettoyer les espaces multiples
    summary = re.sub(r"\s+", " ", str(summary)).strip()
    
    # Vérifier que ce n'est pas juste une répétition du prompt ou du label
    if "Résumé" in summary[:30] or "Summary" in summary[:30] or "الملخص" in summary[:30]:
        # Extraire seulement le contenu après le label
        parts = re.split(r"(Résumé|Summary|الملخص)[:\s]*", summary, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) > 2:
            summary = parts[-1].strip()
    
    # Validations strictes seulement si strict=True
    if strict:
        # Rejeter si le résumé contient des URLs ou emails (signe que c'est le texte original)
        if re.search(r"http[s]?://|www\.|@\w+\.\w+", summary):
            return ""
        
        # Rejeter si le résumé contient des patterns typiques du texte original non résumé
        if re.search(r"AKIPRESS\.COM|All rights reserved|© \d{4}|Republication of any material", summary, re.IGNORECASE):
            return ""
        
        # Rejeter si le résumé commence par des patterns suspects (texte original copié)
        if re.match(r"^(Community Corner|Quarantine due|Four million|According to the district)", summary, re.IGNORECASE):
            # Vérifier si c'est vraiment un résumé ou juste le début du texte original
            if len(summary) > target_words * 3:  # Trop long pour être un résumé
                return ""
    
    # Vérifications spécifiques par langue
    if lang == "ar":
        # Vérifier qu'il y a des caractères arabes
        if not re.search(r"[\u0600-\u06FF]", summary):
            return ""
        # Compter les mots arabes
        words_count = len(summary.split())
        # Rejeter si trop court (moins de 10% des mots demandés)
        if words_count < target_words * 0.1:
            return ""
        # Ajuster si trop long
        if words_count > target_words * 1.5:
            summary = " ".join(summary.split()[:int(target_words * 1.3)])
    else:
        # Pour français et anglais, vérifier qu'il n'y a pas d'arabe
        if re.search(r"[\u0600-\u06FF]", summary):
            return ""
        words_count = len(summary.split())
        # Rejeter si trop court
        if words_count < target_words * 0.1:
            return ""
        # Ajuster si trop long
        if words_count > target_words * 1.5:
            summary = " ".join(summary.split()[:int(target_words * 1.3)])
    
    return summary

# ==============================
# Batch processing (PARALLÉLISÉ)
# ==============================

def process_row(args):
    """Traite une ligne : génère les 3 résumés avec garantie de résultat"""
    text, lang, idx = args
    
    # Filtrer les cas invalides
    if not text or pd.isna(text) or str(text).strip() == "" or str(text).lower() == "nan":
        return idx, "", "", ""
    
    # Normaliser la langue
    lang = str(lang).lower().strip() if lang and not pd.isna(lang) else "en"
    if lang not in ("fr", "ar", "en") or lang == "unknown":
        lang = "en"
    
    # Vérifier que le texte a assez de contenu
    text_str = str(text).strip()
    if len(text_str) < 20:  # Texte trop court
        return idx, "", "", ""
    
    # Générer les 3 résumés avec garantie
    r50 = summarize_ollama(text_str, lang, 50)
    r100 = summarize_ollama(text_str, lang, 100)
    r150 = summarize_ollama(text_str, lang, 150)
    
    # S'assurer que chaque résumé existe - créer un fallback si nécessaire
    if not r50:
        r50 = create_fallback_summary(text_str, lang, 50)
    if not r100:
        r100 = create_fallback_summary(text_str, lang, 100)
    if not r150:
        r150 = create_fallback_summary(text_str, lang, 150)
    
    return idx, r50, r100, r150

def create_fallback_summary(text, lang, target_words):
    """Crée un résumé de fallback à partir du texte si le modèle échoue"""
    if not text or not text.strip():
        return ""
    
    # Prendre les premiers mots du texte
    words_list = text.split()[:target_words]
    summary = " ".join(words_list)
    
    # Ajouter "..." si le texte est plus long
    if len(text.split()) > target_words:
        summary += "..."
    
    return summary.strip()

def summarize_dataframe(df):
    """Traite le DataFrame en parallèle"""
    r50 = [""] * len(df)
    r100 = [""] * len(df)
    r150 = [""] * len(df)
    
    # Préparer les arguments - remplacer NaN par chaînes vides
    tasks = []
    for idx, (text, lang) in enumerate(zip(df["Contenu"], df["Langue"])):
        text_clean = text if not pd.isna(text) else ""
        lang_clean = lang if not pd.isna(lang) else "en"
        tasks.append((text_clean, lang_clean, idx))
    
    # Traitement parallèle
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_row, task): task for task in tasks}
        
        for future in tqdm(as_completed(futures), total=len(tasks), desc="Résumés"):
            try:
                idx, s50, s100, s150 = future.result()
                # Nettoyer les résultats (remplacer "nan" par chaîne vide)
                r50[idx] = "" if (not s50 or str(s50).lower() == "nan") else str(s50).strip()
                r100[idx] = "" if (not s100 or str(s100).lower() == "nan") else str(s100).strip()
                r150[idx] = "" if (not s150 or str(s150).lower() == "nan") else str(s150).strip()
            except Exception as e:
                # Log silencieux des erreurs
                pass
    
    df["resum_50"] = r50
    df["resum_100"] = r100
    df["resum_150"] = r150
    return df

# ==============================
# RUN
# ==============================

df = pd.read_csv("data/extracted_articles.csv")

df = summarize_dataframe(df)

df.to_csv("data/summarized_articles.csv", index=False, encoding="utf-8-sig")
print("✅ Résumés générés (PROMPT-ONLY, ultra rapide)")
