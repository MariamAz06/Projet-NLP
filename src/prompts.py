# prompts.py
# Fichier centralisé pour tous les prompts Ollama utilisés dans extraction_complete.py

class PromptManager:
    """Gestionnaire centralisé pour tous les prompts Ollama"""
    
    @staticmethod
    def get_translation_prompt(texte_arabe, max_length=2000):
        """Prompt pour traduire l'arabe en français"""
        texte_a_traduire = texte_arabe[:max_length] if len(texte_arabe) > max_length else texte_arabe
        return f"""Traduis ce texte arabe en français de manière précise et fidèle. 
Conserve tous les noms propres (lieux, personnes, maladies) et les dates.

Texte arabe:
{texte_a_traduire}

Traduction française:"""
    
    @staticmethod
    def get_date_extraction_prompt(titre, contenu, langue):
        """Prompt pour extraire la date de publication"""
        if langue == 'ar':
            return f"""حلل هذا النص واستخرج تاريخ النشر فقط بالتنسيق jj-mm-aaaa.

النص:
العنوان: {titre}
المحتوى: {contenu[:1000]}

أجب فقط بالتاريخ بالتنسيق jj-mm-aaaa (مثال: 15-11-2023).
إذا لم تجد تاريخاً، أجب "NON TROUVEE"."""
        elif langue == 'fr':
            return f"""Analyse ce texte d'actualité et extrais UNIQUEMENT la date de publication au format jj-mm-aaaa.

Texte:
Titre: {titre}
Contenu: {contenu[:1000]}

Réponds UNIQUEMENT avec la date au format jj-mm-aaaa (exemple: 15-11-2023). 
Si tu ne trouves pas de date, réponds "NON TROUVEE"."""
        else:  # Anglais par défaut
            return f"""Analyze this news text and extract ONLY the publication date in format dd-mm-yyyy.

Text:
Title: {titre}
Content: {contenu[:1000]}

Respond ONLY with the date in format dd-mm-yyyy (example: 15-11-2023).
If you don't find a date, respond "NON TROUVEE"."""
    
    @staticmethod
    def get_disease_extraction_prompt(texte_analyse, langue):
        """Prompt pour extraire la maladie animale"""
        if langue == 'ar':
            return f"""أنت خبير في الأمراض الحيوانية. استخرج اسم المرض الحيواني المذكور في النص.

النص:
{texte_analyse}

قواعد صارمة:
1. استخرج UNIQUEMENT اسم المرض الحيواني (2-4 كلمات كحد أقصى)
2. لا تضع كلمة "مرض" أو "داء" قبل اسم المرض
3. أجب فقط باسم المرض، بدون أي نص إضافي أو شرح
4. إذا لم تجد مرضاً، أجب فقط "NON TROUVEE"

أمثلة على الإجابات الصحيحة:
✅ "الحمى القلاعية"
✅ "حمى الطيور"
✅ "السعار"
✅ "التهاب الجلد العقدي"
✅ "الحمى القلاعية"

أمثلة على الإجابات الخاطئة (لا تفعل هذا):
❌ "مرض الحمى القلاعية" (لا تضع كلمة "مرض")
❌ "Citation: الحمى القلاعية" (لا تضع نصوص إضافية)
❌ "Très important: الحمى القلاعية" (لا تضع تعليمات)
❌ "..." (لا تضع نقاط)
❌ "NON TROUVEE" (فقط إذا لم تجد مرضاً)

اسم المرض:"""
        elif langue == 'fr':
            return f"""Tu es un expert en maladies animales. Extrais UNIQUEMENT le nom de la maladie animale mentionnée.

Texte:
{texte_analyse}

RÈGLES STRICTES:
1. Extrais UNIQUEMENT le nom de la maladie (2-4 mots maximum)
2. Ne mets PAS le mot "maladie" ou "disease" avant le nom
3. Réponds SEULEMENT avec le nom, sans texte supplémentaire
4. Si aucune maladie n'est mentionnée, réponds "NON TROUVEE"

Exemples de BONNES réponses:
✅ "fièvre aphteuse"
✅ "grippe aviaire"
✅ "rage"
✅ "dermatose nodulaire"
✅ "fièvre catarrhale ovine"

Exemples de MAUVAISES réponses (NE PAS FAIRE):
❌ "maladie de la rage" (ne pas mettre "maladie")
❌ "Citation: rage" (ne pas mettre de texte supplémentaire)
❌ "Très important: rage" (ne pas mettre d'instructions)
❌ "..." (ne pas mettre de points)
❌ "NON TROUVEE" (seulement si aucune maladie trouvée)

Nom de la maladie:"""
        else:  # Anglais par défaut
            return f"""You are an expert in animal diseases. Extract ONLY the name of the animal disease mentioned.

Text:
{texte_analyse}

STRICT RULES:
1. Extract ONLY the disease name (2-4 words maximum)
2. Do NOT include the word "disease" or "maladie" before the name
3. Answer ONLY with the disease name, no additional text
4. If no disease is mentioned, respond "NON TROUVEE"

Examples of CORRECT answers:
✅ "foot-and-mouth disease"
✅ "avian influenza"
✅ "rabies"
✅ "lumpy skin disease"
✅ "bluetongue"

Examples of WRONG answers (DO NOT DO THIS):
❌ "disease of rabies" (do not include "disease")
❌ "Citation: rabies" (do not include additional text)
❌ "Very important: rabies" (do not include instructions)
❌ "..." (do not include dots)
❌ "NON TROUVEE" (only if no disease found)

Disease name:"""
    
    @staticmethod
    def get_location_conversion_prompt(ville, langue_detectee):
        """Prompt pour convertir une ville/région en pays"""
        if langue_detectee == 'ar':
            return f"""أنت خبير في الجغرافيا. حول اسم المدينة أو المنطقة التالية إلى اسم البلد (الدولة) فقط.

المدينة/المنطقة: {ville}

مهم جداً:
- أجب فقط باسم البلد (الدولة) بدون أي نص إضافي
- إذا كانت "{ville}" هي بالفعل اسم دولة، أعدها كما هي
- إذا كانت "{ville}" هي مدينة أو منطقة، اذكر اسم البلد فقط
- أمثلة:
  * "قنا" → "مصر"
  * "المنطقة الشرقية" → "السعودية"
  * "Rockland County" → "USA"
  * "Kent" → "UK"
  * "Karaganda" → "Kazakhstan"

أجب فقط باسم البلد:"""
        elif langue_detectee == 'fr':
            return f"""Tu es un expert en géographie. Convertis le nom de ville ou région suivant en nom de pays uniquement.

Ville/Région: {ville}

Très important:
- Réponds UNIQUEMENT avec le nom du pays, sans texte supplémentaire
- Si "{ville}" est déjà un nom de pays, retourne-le tel quel
- Si "{ville}" est une ville ou région, donne UNIQUEMENT le nom du pays
- Exemples:
  * "Paris" → "France"
  * "Rockland County" → "USA"
  * "Kent" → "UK"
  * "Karaganda" → "Kazakhstan"
  * "قنا" → "مصر"

Réponds UNIQUEMENT avec le nom du pays:"""
        else:  # Anglais par défaut
            return f"""You are a geography expert. Convert the following city or region name to country name only.

City/Region: {ville}

Very important:
- Answer ONLY with the country name, no additional text
- If "{ville}" is already a country name, return it as is
- If "{ville}" is a city or region, give ONLY the country name
- Examples:
  * "Paris" → "France"
  * "Rockland County" → "USA"
  * "Kent" → "UK"
  * "Karaganda" → "Kazakhstan"
  * "قنا" → "مصر"

Answer ONLY with the country name:"""
    
    @staticmethod
    def get_organism_extraction_prompt(texte_analyse, langue):
        """Prompt pour extraire l'organisme"""
        if langue == 'ar':
            return f"""أنت خبير في تحليل النصوص. استخرج اسم المنظمة أو المؤسسة أو الوزارة المذكورة في النص.

النص:
{texte_analyse}

قواعد صارمة:
1. ابحث عن أي منظمة أو مؤسسة أو وزارة مذكورة (مثل: وزارة الزراعة، وزارة الصحة، منظمة الصحة العالمية، منظمة الأغذية والزراعة، المنظمة العالمية لصحة الحيوان)
2. استخرج UNIQUEMENT اسم المنظمة (2-6 كلمات كحد أقصى)
3. أجب فقط باسم المنظمة، بدون أي نص إضافي أو شرح
4. إذا لم تجد منظمة، أجب "NON TROUVE"

أمثلة صحيحة:
✅ "وزارة الزراعة"
✅ "منظمة الصحة العالمية"
✅ "OMS"
✅ "FAO"
✅ "OIE"
✅ "المنظمة العالمية لصحة الحيوان"
✅ "وزارة الصحة"

أمثلة خاطئة (لا تفعل هذا):
❌ "Citation: وزارة الزراعة"
❌ "Très important: OMS"
❌ "..."
❌ "المنظمة" (عام جداً - يجب أن يكون الاسم الكامل)

اسم المنظمة:"""
        elif langue == 'fr':
            return f"""Tu es un expert en analyse de textes. Extrais le nom de l'organisme, institution ou ministère mentionné.

Texte:
{texte_analyse}

RÈGLES STRICTES:
1. Cherche TOUTE organisation, institution ou ministère mentionné (exemples: Ministère de l'Agriculture, Ministère de la Santé, OMS, WHO, FAO, OIE, WOAH, CDC, EFSA, ANSES, ECDC)
2. Extrais UNIQUEMENT le nom de l'organisme (2-6 mots maximum)
3. Réponds SEULEMENT avec le nom, sans texte supplémentaire ou explication
4. Si aucune organisation n'est mentionnée, réponds "NON TROUVE"

Exemples CORRECTS:
✅ "Ministère de l'Agriculture"
✅ "OMS"
✅ "WHO"
✅ "FAO"
✅ "OIE"
✅ "WOAH"
✅ "CDC"
✅ "EFSA"
✅ "ANSES"

Exemples INCORRECTS (NE PAS FAIRE):
❌ "Citation: OMS"
❌ "Très important: FAO"
❌ "..."
❌ "l'organisation" (trop générique - doit être le nom complet)

Nom de l'organisme:"""
        else:
            return f"""You are an expert in text analysis. Extract the name of the organization, institution or ministry mentioned.

Text:
{texte_analyse}

STRICT RULES:
1. Search for ANY organization, institution or ministry mentioned (examples: Ministry of Agriculture, Ministry of Health, WHO, FAO, OIE, WOAH, CDC, EFSA, ECDC)
2. Extract ONLY the organization name (2-6 words maximum)
3. Answer ONLY with the name, no additional text or explanation
4. If no organization is mentioned, respond "NON TROUVE"

CORRECT examples:
✅ "Ministry of Agriculture"
✅ "WHO"
✅ "FAO"
✅ "OIE"
✅ "WOAH"
✅ "CDC"
✅ "EFSA"

INCORRECT examples (DO NOT DO THIS):
❌ "Citation: WHO"
❌ "Very important: FAO"
❌ "..."
❌ "the organization" (too generic - must be the full name)

Organization name:"""
    
    @staticmethod
    def get_animal_extraction_prompt(texte_analyse, langue):
        """Prompt pour extraire l'animal"""
        if langue == 'ar':
            return f"""أنت خبير في الأمراض الحيوانية. استخرج اسم الحيوان أو نوع الحيوان المذكور في النص.

النص:
{texte_analyse}

قواعد صارمة:
1. ابحث عن أي حيوان مذكور (مثل: أبقار، دواجن، أغنام، خنازير، خيول، ماعز، طيور، كلاب، قطط، غزلان، ثعالب، ذئاب، دببة، جمال، إبل، أسماك، فئران، إلخ)
2. استخرج UNIQUEMENT اسم الحيوان (1-2 كلمات كحد أقصى)
3. أجب فقط باسم الحيوان، بدون أي نص إضافي أو شرح
4. إذا لم تجد حيواناً، أجب "NON TROUVE"

أمثلة صحيحة:
✅ "أبقار"
✅ "دواجن"
✅ "أغنام"
✅ "طيور"
✅ "خنازير"
✅ "خيول"
✅ "ماعز"
✅ "كلاب"
✅ "قطط"
✅ "غزلان"

أمثلة خاطئة (لا تفعل هذا):
❌ "Citation: أبقار"
❌ "Très important: دواجن"
❌ "..."
❌ "الحيوان" (عام جداً - يجب أن يكون النوع المحدد)

اسم الحيوان:"""
        elif langue == 'fr':
            return f"""Tu es un expert en maladies animales. Extrais le nom de l'animal ou de l'espèce animale mentionnée.

Texte:
{texte_analyse}

RÈGLES STRICTES:
1. Cherche TOUT animal mentionné (exemples: bovins, vaches, volailles, poulets, ovins, moutons, porcins, porcs, chevaux, caprins, chèvres, oiseaux, lapins, ânes, cerfs, sangliers, renards, loups, ours, chiens, chats, poissons, chameaux, lamas, autruches, rongeurs, hérissons, écureuils, lièvres, etc.)
2. Extrais UNIQUEMENT le nom de l'animal (1-2 mots maximum)
3. Réponds SEULEMENT avec le nom, sans texte supplémentaire ou explication
4. Si aucun animal n'est mentionné, réponds "NON TROUVE"

Exemples CORRECTS:
✅ "bovins"
✅ "volailles"
✅ "ovins"
✅ "oiseaux"
✅ "porcins"
✅ "chevaux"
✅ "caprins"
✅ "lapins"
✅ "cerfs"
✅ "chiens"
✅ "chats"

Exemples INCORRECTS (NE PAS FAIRE):
❌ "Citation: bovins"
❌ "Très important: volailles"
❌ "..."
❌ "l'animal" (trop générique - doit être le type spécifique)

Nom de l'animal:"""
        else:
            return f"""You are an expert in animal diseases. Extract the name of the animal or animal species mentioned.

Text:
{texte_analyse}

STRICT RULES:
1. Search for ANY animal mentioned (examples: cattle, cows, poultry, chickens, sheep, pigs, horses, goats, birds, rabbits, donkeys, deer, wild boar, foxes, wolves, bears, dogs, cats, fish, camels, llamas, ostriches, rodents, hedgehogs, squirrels, hares, etc.)
2. Extract ONLY the animal name (1-2 words maximum)
3. Answer ONLY with the name, no additional text or explanation
4. If no animal is mentioned, respond "NON TROUVE"

CORRECT examples:
✅ "cattle"
✅ "poultry"
✅ "sheep"
✅ "birds"
✅ "pigs"
✅ "horses"
✅ "goats"
✅ "rabbits"
✅ "deer"
✅ "dogs"
✅ "cats"

INCORRECT examples (DO NOT DO THIS):
❌ "Citation: cattle"
❌ "Very important: poultry"
❌ "..."
❌ "the animal" (too generic - must be the specific type)

Animal name:"""
    
    @staticmethod
    def get_validation_prompt(titre, contenu, maladie, lieu, langue):
        """Prompt pour valider et corriger les informations"""
        texte_complet = f"{titre}\n\n{contenu[:2000]}" if len(contenu) > 2000 else f"{titre}\n\n{contenu}"
        
        if langue == 'ar':
            return f"""أنت خبير في التحقق من المعلومات. تحقق من المعلومات التالية وتأكد من أنها منطقية ومتسقة مع النص.

النص:
{texte_complet}

المعلومات المستخرجة حالياً:
- المرض: {maladie if maladie else "(غير محدد)"}
- المكان: {lieu if lieu else "(غير محدد)"}

المهمة:
1. تحقق من أن المرض المذكور موجود فعلاً في النص
2. تحقق من أن المكان المذكور موجود فعلاً في النص
3. إذا كانت المعلومات غير متسقة، استخرج المعلومات الصحيحة من النص
4. إذا لم تكن المعلومات موجودة في النص، اتركها فارغة

أجب بتنسيق JSON:
{{"maladie": "المرض الصحيح أو فارغ", "lieu": "المكان الصحيح أو فارغ", "coherent": true/false, "raison": "سبب التغيير إن وجد"}}"""
        elif langue == 'fr':
            return f"""Tu es un expert en validation d'informations. Vérifie les informations suivantes et assure-toi qu'elles sont logiques et cohérentes avec le texte.

Texte:
{texte_complet}

Informations actuellement extraites:
- Maladie: {maladie if maladie else "(non spécifiée)"}
- Lieu: {lieu if lieu else "(non spécifié)"}

Tâche:
1. Vérifie que la maladie mentionnée est réellement présente dans le texte
2. Vérifie que le lieu mentionné est réellement présent dans le texte
3. Si les informations sont incohérentes, extrais les informations CORRECTES et PRÉCISES du texte
4. Si les informations ne sont pas dans le texte, laisse-les vides
5. IMPORTANT: La maladie doit être le nom EXACT et COURT (max 3-4 mots), pas de phrases
6. IMPORTANT: Le lieu doit être UNIQUEMENT le lieu géographique (ville, région, pays), pas de départements ou parties de titre

Réponds en format JSON:
{{"maladie": "nom exact et court de la maladie ou vide", "lieu": "lieu géographique précis ou vide", "coherent": true/false, "raison": "raison du changement si applicable"}}"""
        else:  # Anglais
            return f"""You are an expert in information validation. Check the following information and ensure it is logical and consistent with the text.

Text:
{texte_complet}

Currently extracted information:
- Disease: {maladie if maladie else "(not specified)"}
- Location: {lieu if lieu else "(not specified)"}

Task:
1. Verify that the mentioned disease is actually present in the text
2. Verify that the mentioned location is actually present in the text
3. If the information is inconsistent, extract the CORRECT and PRECISE information from the text
4. If the information is not in the text, leave it empty
5. IMPORTANT: Disease must be the EXACT and SHORT name (max 3-4 words), no sentences
6. IMPORTANT: Location must be ONLY the geographical location (city, region, country), no departments or parts of title

Respond in JSON format:
{{"maladie": "exact and short disease name or empty", "lieu": "precise geographical location or empty", "coherent": true/false, "raison": "reason for change if applicable"}}"""
    
    @staticmethod
    def get_structured_extraction_prompt(texte_complet, langue_detectee):
        """Prompt pour extraire les informations structurées (lieu, maladie, source)"""
        if langue_detectee == 'ar':
            return f"""أنت خبير في تحليل نصوص الأخبار حول الأمراض الحيوانية.
استخرج المعلومات التالية من النص بتنسيق JSON صارم.

النص:
{texte_complet}

قواعد صارمة:
1. المكان: UNIQUEMENT البلد أو المدينة (1-3 كلمات كحد أقصى)
2. المرض: UNIQUEMENT اسم المرض (2-4 كلمات كحد أقصى، بدون كلمة "مرض")
3. المصدر: "médias" أو "réseaux sociaux" أو "site officiel"
4. أجب بتنسيق JSON فقط، بدون نص إضافي

أمثلة صحيحة:
✅ {{"lieu": "مصر", "maladie": "الحمى القلاعية", "source": "médias"}}
✅ {{"lieu": "المغرب", "maladie": "حمى الطيور", "source": "médias"}}
✅ {{"lieu": "France", "maladie": "fièvre catarrhale ovine", "source": "site officiel"}}

أمثلة خاطئة (لا تفعل هذا):
❌ {{"lieu": "يوم الأحد المقبل", "maladie": "..."}} → خطأ: "يوم الأحد المقبل" هو تاريخ وليس مكان
❌ {{"lieu": "محافظ", "maladie": "..."}} → خطأ: "محافظ" هو منصب وليس مكان
❌ {{"lieu": "مديرية", "maladie": "..."}} → خطأ: "مديرية" هي مؤسسة وليس مكان جغرافي
❌ {{"lieu": "...", "maladie": "..."}} → خطأ: لا تضع نقاط

التنسيق المطلوب: {{"lieu": "...", "maladie": "...", "source": "..."}}"""
        elif langue_detectee == 'fr':
            return f"""Tu es un expert en analyse de textes d'actualités sur les maladies animales.
Analyse ce texte et extrais UNIQUEMENT les informations demandées au format JSON strict.

⚠️ TRÈS IMPORTANT: Le lieu (lieu) doit être extrait UNIQUEMENT depuis le TITRE. Ne pas extraire un lieu depuis le contenu s'il n'est pas dans le titre.

EXEMPLES DE RÉPONSES CORRECTES:
✅ {{"lieu": "USA", "maladie": "rage", "source": "médias"}}
✅ {{"lieu": "South Korea", "maladie": "dermatose nodulaire", "source": "médias"}}
✅ {{"lieu": "Kazakhstan", "maladie": "anthrax", "source": "médias"}}
✅ {{"lieu": "UK", "maladie": "fièvre catarrhale ovine", "source": "médias"}}
✅ {{"lieu": "France", "maladie": "hémorragique épizootique", "source": "médias"}}

EXEMPLES DE RÉPONSES INCORRECTES À ÉVITER ABSOLUMENT:
❌ {{"lieu": "Agriculture, Food", "maladie": "..."}}  → INCORRECT: "Agriculture, Food" est un nom de ministère, PAS un lieu
❌ {{"lieu": "Ministry of Health", "maladie": "..."}}  → INCORRECT: "Ministry of Health" est un ministère, PAS un lieu
❌ {{"lieu": "Department of Agriculture", "maladie": "..."}}  → INCORRECT: c'est un département gouvernemental, PAS un lieu géographique
❌ {{"lieu": "جهاز, ،في", "maladie": "..."}}  → INCORRECT: ce sont des mots arabes génériques (appareil, dans), PAS un lieu
❌ {{"lieu": "France, Belgium", "maladie": "..."}}  → INCORRECT si le texte mentionne "Kent": utiliser "Kent, UK" (le lieu précis)
❌ {{"lieu": "New York State", "maladie": "..."}}  → INCORRECT si le texte mentionne "Rockland County, NY": utiliser le lieu précis
❌ {{"lieu": "يوم, الأحد", "maladie": "..."}}  → INCORRECT: ce sont des mots de date (jour, dimanche), PAS un lieu

RÈGLES STRICTES - PRECISION OBLIGATOIRE - EXTRACTION EXACTE:
- "lieu": UNIQUEMENT le PAYS (Country only) mentionné EXPLICITEMENT dans le TITRE uniquement. 
  * ⚠️ OBLIGATOIRE: Extraire UNIQUEMENT depuis le TITRE. Ne PAS extraire depuis le contenu si le lieu n'est pas dans le titre
  * Format OBLIGATOIRE: nom du pays uniquement (exemples: "France", "USA", "UK", "Kazakhstan", "South Korea", "مصر", "المغرب")
  * Si une ville ou région est mentionnée dans le titre (ex: "Rockland County", "Karaganda", "Kent", "قنا"), chercher le pays dans le titre et extraire UNIQUEMENT le pays
  * Exemples corrects: "France", "USA", "UK", "Kazakhstan", "South Korea", "مصر", "المغرب"
  * Exemples incorrects: "Rockland County, NY" (trop précis - on veut juste "USA"), "قنا, مصر" (trop précis - on veut juste "مصر")
  * Ne PAS extraire de villes, comtés, régions, provinces - UNIQUEMENT le pays
  * NE PAS inclure de parties du titre ou de phrases complètes
  * NE PAS inclure de mots comme "Agriculture", "Environment", "Department", "Ministry", "Office", "Bureau"
  * NE PAS inclure de noms de ministères, départements, organisations, institutions
  * Si plusieurs pays sont mentionnés dans le titre, extraire le pays PRINCIPAL où l'événement s'est produit
  * OBLIGATOIRE: Le lieu doit être présent dans le TITRE uniquement
  * Laisse vide "" SEULEMENT si aucun pays n'est mentionné explicitement dans le TITRE
- "maladie": UNIQUEMENT le nom EXACT et COURT de la maladie animale mentionnée EXPLICITEMENT dans le texte.
  * Format: nom simple (ex: "rage", "grippe aviaire", "fièvre aphteuse", "dermatose nodulaire", "anthrax")
  * EXTRACTION EXACTE: Copier EXACTEMENT le nom de la maladie tel qu'il apparaît dans le texte
  * NE PAS inclure de phrases complètes ou de parties du titre
  * NE PAS inclure de mots comme "shots", "outbreak", "case", "quarantine", "maladie", "disease"
  * MAXIMUM 4 mots (ex: "grippe aviaire" = 2 mots, "fièvre catarrhale ovine" = 3 mots)
  * Si le texte dit "maladie de la rage", extrais seulement "rage" (sans "maladie de")
  * Si le texte dit "مرض التهاب الجلد العقدي", extrais seulement "التهاب الجلد العقدي" (sans "مرض")
  * Maximum 3-4 mots pour le nom de la maladie
  * Laisse vide "" si non mentionnée explicitement ou si ambiguë
- "source": UNIQUEMENT "réseaux sociaux" OU "médias" OU "site officiel". Laisse vide "" si incertain.

TRÈS IMPORTANT - PRÉCISION ET CLARTÉ OBLIGATOIRES:
- Analyse TOUT le contenu fourni (début, milieu, fin) pour trouver les informations
- Extrais UNIQUEMENT les informations présentes explicitement dans le texte (titre ET contenu)
- N'invente PAS d'informations qui ne sont pas dans le texte
- Assure-toi que chaque information extraite est réellement présente dans le texte
- La maladie extraite DOIT être le nom EXACT et COURT de la maladie trouvée dans le CONTENU (pas de phrases, pas de parties de titre)
- Le lieu extrait DOIT être UNIQUEMENT le lieu géographique trouvé dans le CONTENU (pas de départements, pas de parties de titre)
- Cherche dans TOUT le contenu, pas seulement dans le titre
- Si le titre parle d'une maladie spécifique, vérifie qu'elle est dans le contenu avant de l'extraire
- Si le titre mentionne un lieu, vérifie qu'il est dans le contenu avant de l'extraire
- NE PAS extraire de phrases complètes ou de parties du titre comme lieu ou maladie
- Les informations doivent être CLAIRES, EXACTES et CONCISES
- PRIORITÉ: Chercher d'abord dans le contenu, puis dans le titre si nécessaire

Texte à analyser:
{texte_complet}

Réponds UNIQUEMENT avec un JSON valide, sans texte avant ou après.
Format: {{"lieu": "...", "maladie": "...", "source": "..."}}"""
        else:  # Anglais par défaut et autres langues
            return f"""You are an expert in analyzing news texts about animal diseases.
Analyze this text and extract ONLY the requested information in strict JSON format.

⚠️ VERY IMPORTANT: The location (lieu) must be extracted ONLY from the TITLE. Do NOT extract a location from the content if it's not in the title.

EXAMPLES OF CORRECT RESPONSES:
✅ {{"lieu": "Rockland County, NY", "maladie": "rabies", "source": "médias"}}
✅ {{"lieu": "South Korea", "maladie": "lumpy skin disease", "source": "médias"}}
✅ {{"lieu": "Kazakhstan", "maladie": "anthrax", "source": "médias"}}
✅ {{"lieu": "UK", "maladie": "bluetongue", "source": "médias"}}
✅ {{"lieu": "France", "maladie": "epizootic hemorrhagic disease", "source": "médias"}}

EXAMPLES OF INCORRECT RESPONSES TO ABSOLUTELY AVOID:
❌ {{"lieu": "Agriculture, Food", "maladie": "..."}}  → INCORRECT: "Agriculture, Food" is a ministry name, NOT a location
❌ {{"lieu": "Ministry of Health", "maladie": "..."}}  → INCORRECT: "Ministry of Health" is a ministry, NOT a location
❌ {{"lieu": "Department of Agriculture", "maladie": "..."}}  → INCORRECT: this is a government department, NOT a geographical location
❌ {{"lieu": "جهاز, ،في", "maladie": "..."}}  → INCORRECT: these are generic Arabic words (device, in), NOT a location
❌ {{"lieu": "France, Belgium", "maladie": "..."}}  → INCORRECT if text mentions "Kent": use "Kent, UK" (the precise location)
❌ {{"lieu": "New York State", "maladie": "..."}}  → INCORRECT if text mentions "Rockland County, NY": use the precise location
❌ {{"lieu": "يوم, الأحد", "maladie": "..."}}  → INCORRECT: these are date words (day, Sunday), NOT a location

STRICT RULES - MANDATORY PRECISION - EXACT EXTRACTION:
- "lieu": ONLY the COUNTRY (Country only) mentioned EXPLICITLY in the TITLE only.
  * ⚠️ MANDATORY: Extract ONLY from the TITLE. Do NOT extract from the content if the location is not in the title
  * MANDATORY format: country name only (examples: "France", "USA", "UK", "Kazakhstan", "South Korea", "مصر", "المغرب")
  * If a city or region is mentioned in the title (ex: "Rockland County", "Karaganda", "Kent", "قنا"), search for the country in the title and extract ONLY the country
  * Correct examples: "France", "USA", "UK", "Kazakhstan", "South Korea", "مصر", "المغرب"
  * Incorrect examples: "Rockland County, NY" (too precise - we want just "USA"), "قنا, مصر" (too precise - we want just "مصر")
  * Do NOT extract cities, counties, regions, provinces - ONLY the country
  * Do NOT include parts of the title or complete sentences
  * Do NOT include words like "Agriculture", "Environment", "Department", "Ministry", "Office", "Bureau"
  * Do NOT include names of ministries, departments, organizations, institutions
  * If multiple countries are mentioned in the title, extract the MAIN country where the event occurred
  * MANDATORY: The location must be present in the TITLE only
  * Leave empty "" ONLY if no country is explicitly mentioned in the TITLE
- "maladie": ONLY the EXACT and SHORT name of the animal disease mentioned EXPLICITLY in the text.
  * Format: simple name (ex: "rabies", "avian influenza", "foot-and-mouth disease", "lumpy skin disease", "anthrax")
  * EXACT EXTRACTION: Copy EXACTLY the disease name as it appears in the text
  * Do NOT include complete sentences or parts of the title
  * Do NOT include words like "shots", "outbreak", "case", "quarantine", "maladie", "disease"
  * MAXIMUM 4 words (ex: "avian influenza" = 2 words, "epizootic hemorrhagic disease" = 3 words)
  * If the text says "disease of rabies", extract only "rabies" (without "disease of")
  * If the text says "مرض التهاب الجلد العقدي", extract only "التهاب الجلد العقدي" (without "مرض")
  * Maximum 3-4 words for the disease name
  * Leave empty "" if not explicitly mentioned or if ambiguous
- "source": ONLY "réseaux sociaux" OR "médias" OR "site officiel". Leave empty "" if uncertain.

VERY IMPORTANT - MANDATORY PRECISION AND CLARITY:
- Analyze ALL the provided content (beginning, middle, end) to find the information
- Extract ONLY the information explicitly present in the text (title AND content)
- Do NOT invent information that is not in the text
- Make sure each extracted information is actually present in the text
- The extracted disease MUST be the EXACT and SHORT name of the disease found in the CONTENT (no sentences, no parts of title)
- The extracted location MUST be ONLY the geographical location found in the CONTENT (no departments, no parts of title)
- Search in ALL the content, not just in the title
- If the title talks about a specific disease, verify it's in the content before extracting it
- If the title mentions a location, verify it's in the content before extracting it
- Do NOT extract complete sentences or parts of the title as location or disease
- Information must be CLEAR, EXACT and CONCISE
- PRIORITY: Search first in the content, then in the title if necessary

Text to analyze:
{texte_complet}

Respond ONLY with valid JSON, no text before or after.
Format: {{"lieu": "...", "maladie": "...", "source": "..."}}"""
    
    @staticmethod
    def get_summary_prompt(titre, contenu, langue, target_words, maladie="", lieu=""):
        """Prompt pour générer un résumé dans la langue du contenu"""
        # Construire les informations contextuelles
        contexte_info = ""
        if maladie and maladie != "nan" and maladie.strip():
            contexte_info += f"\nMaladie mentionnee: {maladie}"
        if lieu and lieu != "nan" and lieu.strip():
            contexte_info += f"\nLieu concerne: {lieu}"
        
        # Réduire la longueur du contenu analysé pour accélérer
        contenu_sample = contenu[:2000] if len(contenu) > 2000 else contenu
        
        if langue == 'ar':
            contexte_ar = ""
            if contexte_info:
                contexte_ar = contexte_info.replace('Maladie mentionnee:', 'المرض المذكور:').replace('Lieu concerne:', 'المكان المعني:')
            return f"""تحليل المحتوى وإنتاج ملخص متماسك ومنظم وموثوق بالمحتوى الأصلي.

يجب أن يكون الملخص باللغة العربية (نفس لغة المحتوى الأصلي)، دون إضافة أي معلومات خارجية.

المتطلبات الصارمة:
- استخدم UNIQUEMENT نفس لغة النص الأصلي (العربية) فقط
- ابدأ الملخص مباشرة بالمحتوى، بدون كلمات مثل "عنوان"، "ملخص"، "هذا المقال"، "يناقش"، "يتحدث عن"، "المقال يتحدث"
- احتفظ فقط بالأفكار الأساسية من النص الأصلي
- لا تضيف أي معلومات خارجية غير موجودة في النص
- كن دقيقًا ومخلصًا للمحتوى الأصلي
- اكتب بجمل كاملة ومترابطة ومنظمة
- استخدم لغة طبيعية وواضحة
- تجنب التكرار والتفاصيل غير الضرورية
- ركز على المعلومات الجوهرية فقط
- لا تبدأ بكلمات مثل "يناقش المقال" أو "يتحدث النص عن" أو "هذا المقال"

العنوان: {titre}
{contexte_ar}

النص:
{contenu_sample}

اكتب الملخص الآن ({target_words} كلمة بالضبط). ابدأ مباشرة بالمحتوى الأصلي:"""
        elif langue == 'fr':
            return f"""Analyse le contenu et produis un résumé cohérent, structuré et fidèle au contenu original.

EXIGENCES STRICTES:
- Le résumé DOIT être en français (même langue que le contenu original)
- Le résumé DOIT être cohérent avec le contenu fourni
- Ne rajoute AUCUNE information externe qui n'est pas dans le texte original
- Garde uniquement les idées essentielles du texte original
- Reformule avec clarté et précision
- Sois fidèle au contenu original
- Écris des phrases complètes, cohérentes et structurées
- Utilise un langage naturel et clair
- Évite les répétitions et les détails inutiles
- Concentre-toi uniquement sur les informations essentielles
- Commence directement par le contenu. Ne mets pas "Titre", "Résumé", "Cet article" ou d'autres mots avant le résumé

Titre: {titre}
{contexte_info}

Texte:
{contenu_sample}

Écris le résumé maintenant ({target_words} mots exactement). Commence directement par le contenu original:"""
        else:  # Anglais par défaut
            contexte_en = ""
            if contexte_info:
                contexte_en = contexte_info.replace('Maladie mentionnee:', 'Disease mentioned:').replace('Lieu concerne:', 'Location:')
            return f"""Analyze the content and produce a coherent, structured, and faithful summary of the original content.

STRICT REQUIREMENTS:
- The summary MUST be in English (same language as the original content)
- The summary MUST be coherent with the provided content
- Do NOT add ANY external information that is not in the original text
- Keep only the essential ideas from the original text
- Reformulate with clarity and precision
- Be faithful to the original content
- Write complete, coherent, and structured sentences
- Use natural and clear language
- Avoid repetitions and unnecessary details
- Focus only on essential information
- Start directly with the content. Do not put "Title", "Summary", "This article" or other words before the summary

Title: {titre}
{contexte_en}

Text:
{contenu_sample}

Write the summary now (exactly {target_words} words). Start directly with the original content:"""
    
    @staticmethod
    def get_summary_retry_prompt(titre, contenu, langue, target_words, maladie, maladie_mentionnee=True):
        """Prompt pour régénérer un résumé avec mention obligatoire de la maladie"""
        contenu_sample = contenu[:1500] if len(contenu) > 1500 else contenu
        
        if langue == 'ar':
            contexte_ar_retry = ""
            if maladie_mentionnee:
                contexte_ar_retry = f"\nالمرض المذكور: {maladie}"
            return f"""تحليل المحتوى وإنتاج ملخص متماسك ومنظم وموثوق بالمحتوى الأصلي.

يجب أن يكون الملخص باللغة العربية (نفس لغة المحتوى الأصلي)، دون إضافة أي معلومات خارجية.

المتطلبات الصارمة:
- استخدم UNIQUEMENT نفس لغة النص الأصلي (العربية) فقط
- يجب أن يذكر الملخص مرض "{maladie}" إذا كان موجودًا في النص
- ابدأ الملخص مباشرة بالمحتوى، بدون كلمات مثل "عنوان"، "ملخص"، "هذا المقال"، "يناقش"، "يتحدث عن"
- احتفظ فقط بالأفكار الأساسية من النص الأصلي
- لا تضيف أي معلومات خارجية غير موجودة في النص
- كن دقيقًا ومخلصًا للمحتوى الأصلي
- اكتب بجمل كاملة ومترابطة ومنظمة

العنوان: {titre}
{contexte_ar_retry}

النص:
{contenu_sample}

اكتب الملخص الآن ({target_words} كلمة بالضبط). ابدأ مباشرة بالمحتوى الأصلي:"""
        elif langue == 'fr':
            return f"""Écris un résumé en français de {target_words} mots exactement. Le résumé DOIT mentionner la maladie "{maladie}".

Commence directement par le contenu. Ne mets pas "Titre", "Résumé" ou d'autres mots avant le résumé.

Titre: {titre}

Texte:
{contenu_sample}

Résumé ({target_words} mots, doit mentionner "{maladie}"):"""
        else:  # Anglais par défaut
            return f"""Write a summary in English of exactly {target_words} words. The summary MUST mention the disease "{maladie}".

Start directly with the content. Do not put "Title", "Summary" or other words before the summary.

Title: {titre}

Text:
{contenu_sample}

Summary ({target_words} words, must mention "{maladie}"):"""
    
    @staticmethod
    def get_summary_strict_arabic_prompt(titre, contenu, langue, target_words, maladie="", lieu=""):
        """Prompt strict pour forcer la génération en arabe avec exemples et préfixe"""
        contexte_ar = ""
        contexte_info = ""
        if maladie and maladie != "nan" and maladie.strip():
            contexte_info += f"\nالمرض المذكور: {maladie}"
        if lieu and lieu != "nan" and lieu.strip():
            contexte_info += f"\nالمكان المعني: {lieu}"
        if contexte_info:
            contexte_ar = contexte_info
        
        contenu_sample = contenu[:2500] if len(contenu) > 2500 else contenu
        
        return f"""أنت مساعد ذكي متخصص في كتابة الملخصات باللغة العربية فقط. مهمتك الوحيدة هي إنتاج ملخص بالعربية.

⚠️⚠️⚠️ قواعد إلزامية - يجب اتباعها بدقة:
1. اللغة: استخدم اللغة العربية فقط. ممنوع تماماً استخدام الإنجليزية أو الفرنسية أو أي لغة أخرى.
2. البداية: ابدأ الملخص مباشرة بالمحتوى. لا تضع "عنوان"، "ملخص"، "هذا المقال"، "يناقش"، "يتحدث عن"، "The article"، "Title"، "Summary".
3. المحتوى: استخدم فقط المعلومات الموجودة في النص الأصلي. لا تضيف معلومات خارجية.
4. الجمل: اكتب بجمل كاملة ومترابطة ومنظمة بالعربية فقط.
5. الدقة: كن دقيقاً ومخلصاً للمحتوى الأصلي.

أمثلة على ملخصات صحيحة:

مثال 1 (50 كلمة):
أعلنت السلطات الصحية عن تفشي مرض جديد في المنطقة. تم اتخاذ إجراءات عاجلة لمنع انتشار المرض. تم عزل المناطق المصابة وفرض قيود على حركة الحيوانات. بدأت حملة تطعيم واسعة النطاق لحماية القطعان.

مثال 2 (100 كلمة):
أعلنت السلطات الصحية عن تفشي مرض جديد في المنطقة الشرقية. تم اتخاذ إجراءات عاجلة وفورية لمنع انتشار المرض بين الماشية. تم عزل المناطق المصابة وفرض قيود صارمة على حركة الحيوانات. بدأت حملة تطعيم واسعة النطاق لحماية القطعان من الإصابة. تم إغلاق أسواق الحيوانات مؤقتاً حتى انتهاء التفشي الوبائي. تعمل السلطات بالتنسيق مع مكاتب الصحة الحيوانية والأجهزة الأمنية لاحتواء الوضع.

⚠️ أمثلة على ملخصات خاطئة (ممنوع تماماً):
❌ "Title: Disease outbreak. The article discusses a new disease."
❌ "Summary: This article talks about health measures."
❌ "The article discusses..."

العنوان: {titre}
{contexte_ar}

النص الأصلي:
{contenu_sample}

الآن اكتب الملخص ({target_words} كلمة بالضبط) بالعربية فقط. ابدأ مباشرة بالمحتوى:"""
    
    @staticmethod
    def get_summary_ultra_simple_arabic_prompt(titre, contenu, target_words):
        """Prompt ultra-simple pour forcer l'arabe - dernière tentative"""
        contenu_sample = contenu[:2000] if len(contenu) > 2000 else contenu
        return f"""اكتب ملخصاً بالعربية فقط ({target_words} كلمة).

العنوان: {titre}

النص:
{contenu_sample}

الملخص بالعربية:"""



