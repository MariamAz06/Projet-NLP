# utils.py
# Fonctions utilitaires pour le nettoyage, validation et calculs

import re


def clean_content(contenu):
    """Nettoie le contenu des éléments non pertinents"""
    if not contenu:
        return ""
    
    # Supprimer les éléments de navigation/menu courants
    unwanted_patterns = [
        r'Cookie\s*Policy|Politique\s*de\s*cookies|سياسة\s*الخصوصية',
        r'Privacy\s*Policy|Politique\s*de\s*confidentialité',
        r'Terms\s*of\s*Service|Conditions\s*d\'utilisation',
        r'Subscribe|S\'abonner|اشترك',
        r'Follow\s*us|Suivez-nous|تابعنا',
        r'Share\s*on|Partager\s*sur|شارك\s*على',
        r'Related\s*articles|Articles\s*connexes|مقالات\s*ذات\s*صلة',
        r'Advertisement|Publicité|إعلان',
        r'Click\s*here|Cliquez\s*ici|انقر\s*هنا',
        r'Read\s*more|Lire\s*la\s*suite|اقرأ\s*المزيد',
        r'Home|Accueil|الرئيسية',
        r'Menu|القائمة',
        r'Skip\s*to\s*content|Aller\s*au\s*contenu',
    ]
    
    # Supprimer les URLs
    contenu = re.sub(r'https?://\S+|www\.\S+', '', contenu)
    
    # Supprimer les emails
    contenu = re.sub(r'\S+@\S+', '', contenu)
    
    # Supprimer les patterns non pertinents
    for pattern in unwanted_patterns:
        contenu = re.sub(pattern, '', contenu, flags=re.IGNORECASE)
    
    # Nettoyer les espaces multiples
    contenu = re.sub(r'\s+', ' ', contenu)
    
    # Supprimer les lignes trop courtes (probablement des menus)
    lines = contenu.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        # Garder les lignes significatives (plus de 20 caractères ou contenant des mots-clés importants)
        if len(line) > 20 or any(keyword in line.lower() for keyword in ['disease', 'maladie', 'animal', 'health', 'santé', 'مرض', 'صحة']):
            cleaned_lines.append(line)
    
    contenu = ' '.join(cleaned_lines)
    
    return contenu.strip()


def calculate_stats(text):
    """Calcule le nombre de caractères et de mots"""
    if not text:
        return {"caracteres": 0, "mots": 0}
    
    caracteres = len(text)
    # Compter les mots (séparés par des espaces)
    mots = len(text.split())
    
    return {
        "caracteres": caracteres,
        "mots": mots
    }


def validate_content_coherence(titre, contenu):
    """Valide que le contenu est cohérent avec le titre et logiquement correct"""
    issues = []
    
    if not contenu or len(contenu.strip()) < 50:
        issues.append("Contenu trop court ou vide")
        return contenu, issues
    
    if not titre or len(titre.strip()) < 5:
        issues.append("Titre trop court ou vide")
        return contenu, issues
    
    # Vérifier que le contenu n'est pas juste une répétition du titre
    titre_words = set(titre.lower().split())
    contenu_words = set(contenu.lower().split()[:50])  # Premiers 50 mots
    
    # Si plus de 80% des mots du titre sont dans le contenu, c'est suspect
    if len(titre_words) > 0:
        overlap = len(titre_words.intersection(contenu_words)) / len(titre_words)
        if overlap > 0.8 and len(contenu.split()) < 100:
            issues.append("Contenu semble être une répétition du titre")
    
    # Vérifier que le contenu contient des mots significatifs
    significant_words = ['disease', 'maladie', 'animal', 'health', 'santé', 'outbreak', 'épidémie', 
                        'مرض', 'صحة', 'حيوان', 'تفشي', 'وباء']
    contenu_lower = contenu.lower()
    has_significant_content = any(word in contenu_lower for word in significant_words)
    
    if not has_significant_content and len(contenu.split()) < 30:
        issues.append("Contenu ne semble pas contenir d'informations pertinentes")
    
    return contenu, issues



