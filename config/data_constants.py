# data_constants.py
# Fichier centralisé pour toutes les données de référence : listes, dictionnaires, patterns regex

import re

# ============================================================================
# LIEUX GÉOGRAPHIQUES
# ============================================================================

# Liste étendue de villes et pays pour l'extraction de lieux
COMMON_LOCATIONS_EXTENDED = [
    # Pays (anglais)
    'USA', 'United States', 'America', 'US', 'France', 'Germany', 'Spain', 'Italy', 
    'UK', 'United Kingdom', 'Britain', 'China', 'Japan', 'South Korea', 'North Korea', 
    'India', 'Brazil', 'Argentina', 'Canada', 'Mexico', 'Australia', 'New Zealand', 
    'South Africa', 'Egypt', 'Morocco', 'Algeria', 'Tunisia', 'Libya', 'Syria', 
    'Iraq', 'Iran', 'Turkey', 'Russia', 'Kazakhstan', 'Uzbekistan', 'Paraguay', 
    'Chile', 'Colombia', 'Venezuela', 'Peru', 'Ecuador', 'Uruguay', 'Bolivia',
    'Belgium', 'Netherlands', 'Switzerland', 'Austria', 'Sweden', 'Norway', 
    'Denmark', 'Finland', 'Poland', 'Czech Republic', 'Greece', 'Ireland',
    'Portugal', 'Romania', 'Bulgaria', 'Hungary', 'Croatia', 'Serbia',
    'Philippines', 'Indonesia', 'Thailand', 'Vietnam', 'Malaysia', 'Singapore',
    'Bangladesh', 'Pakistan', 'Afghanistan', 'Saudi Arabia', 'UAE', 'Qatar',
    'Kuwait', 'Jordan', 'Lebanon', 'Yemen', 'Oman', 'Bahrain',
    # Pays (français)
    'États-Unis', 'Royaume-Uni', 'Corée du Sud', 'Corée du Nord', 'Afrique du Sud',
    'Belgique', 'Pays-Bas', 'Suisse', 'Autriche', 'Suède', 'Norvège', 'Danemark',
    'Finlande', 'Pologne', 'République tchèque', 'Grèce', 'Irlande', 'Portugal',
    # Villes majeures (internationales)
    'Paris', 'London', 'New York', 'Los Angeles', 'Chicago', 'Moscow', 'Tokyo',
    'Beijing', 'Shanghai', 'Cairo', 'Casablanca', 'Algiers', 'Tunis', 'Damascus',
    'Baghdad', 'Tehran', 'Istanbul', 'Berlin', 'Madrid', 'Rome', 'Amsterdam',
    'Bruxelles', 'Brussels', 'Vienna', 'Prague', 'Warsaw', 'Athens', 'Lisbon', 
    'Dublin', 'Stockholm', 'Oslo', 'Copenhagen', 'Helsinki', 'Reykjavik', 'Riga', 
    'Tallinn', 'Vilnius', 'Bucharest', 'Sofia', 'Budapest', 'Zagreb', 'Belgrade', 
    'Sarajevo', 'Skopje', 'Tirana', 'Podgorica', 'Pristina', 'Kiev', 'Minsk', 
    'Chisinau', 'Bangkok', 'Manila', 'Jakarta', 'Singapore', 'Kuala Lumpur',
    'Ho Chi Minh City', 'Hanoi', 'Seoul', 'Busan', 'Mumbai', 'Delhi', 'Bangalore',
    'Sydney', 'Melbourne', 'Auckland', 'Wellington', 'Johannesburg', 'Cape Town',
    'São Paulo', 'Rio de Janeiro', 'Buenos Aires', 'Lima', 'Santiago', 'Bogota',
    'Caracas', 'Montevideo', 'La Paz', 'Quito', 'Riyadh', 'Dubai', 'Abu Dhabi',
    'Doha', 'Kuwait City', 'Amman', 'Beirut', 'Sanaa', 'Muscat', 'Manama',
    # Villes USA (états et comtés)
    'New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia',
    'San Antonio', 'San Diego', 'Dallas', 'San Jose', 'Austin', 'Jacksonville',
    'Fort Worth', 'Columbus', 'Charlotte', 'San Francisco', 'Indianapolis',
    'Seattle', 'Denver', 'Boston', 'El Paso', 'Detroit', 'Nashville', 'Portland',
    'Oklahoma City', 'Las Vegas', 'Memphis', 'Louisville', 'Baltimore', 'Milwaukee',
    # États USA
    'California', 'Texas', 'Florida', 'New York', 'Pennsylvania', 'Illinois',
    'Ohio', 'Georgia', 'North Carolina', 'Michigan', 'New Jersey', 'Virginia',
    'Washington', 'Arizona', 'Massachusetts', 'Tennessee', 'Indiana', 'Missouri',
    'Maryland', 'Wisconsin', 'Colorado', 'Minnesota', 'South Carolina', 'Alabama',
    'Louisiana', 'Kentucky', 'Oregon', 'Oklahoma', 'Connecticut', 'Utah',
    # Villes/régions arabes
    'القاهرة', 'Cairo', 'الإسكندرية', 'Alexandria', 'الجيزة', 'Giza',
    'الدار البيضاء', 'Casablanca', 'الرباط', 'Rabat', 'فاس', 'Fez',
    'الجزائر', 'Algiers', 'وهران', 'Oran', 'تونس', 'Tunis', 'صفاقس', 'Sfax',
    'دمشق', 'Damascus', 'حلب', 'Aleppo', 'بغداد', 'Baghdad', 'البصرة', 'Basra',
    'طهران', 'Tehran', 'مشهد', 'Mashhad', 'إسطنبول', 'Istanbul', 'أنقرة', 'Ankara',
    'الرياض', 'Riyadh', 'جدة', 'Jeddah', 'الدمام', 'Dammam', 'دبي', 'Dubai',
    'أبو ظبي', 'Abu Dhabi', 'الدوحة', 'Doha', 'الكويت', 'Kuwait City',
    'عمان', 'Amman', 'بيروت', 'Beirut', 'صنعاء', 'Sanaa', 'مسقط', 'Muscat',
    # Régions/provinces arabes
    'قنا', 'Qena', 'أسيوط', 'Asyut', 'سوهاج', 'Sohag', 'المنيا', 'Minya',
    'المنطقة الشرقية', 'Eastern Province', 'المنطقة الغربية', 'Western Province',
    # Arabe (pays)
    'مصر', 'المغرب', 'الجزائر', 'تونس', 'ليبيا', 'سوريا', 'العراق', 'إيران',
    'السعودية', 'الإمارات', 'قطر', 'الكويت', 'الأردن', 'لبنان', 'اليمن', 'عمان',
    'البحرين', 'فلسطين', 'Misr', 'Al-Maghrib', 'Al-Jaza\'ir', 'Tunis', 'Libya', 
    'Suriya', 'Al-Iraq', 'Iran', 'Saudi Arabia', 'UAE', 'Qatar', 'Kuwait',
    'Jordan', 'Lebanon', 'Yemen', 'Oman', 'Bahrain', 'Palestine'
]

# Mots à EXCLURE (faux positifs pour les lieux)
EXCLUDED_WORDS = [
    # Organisations gouvernementales
    'agriculture', 'environment', 'department', 'ministry', 'ministère', 'office', 'bureau',
    'ministry of', 'department of', 'office of', 'ministère de', 'ministère des',
    'health', 'santé', 'food', 'alimentation', 'rural', 'development', 'développement',
    'affairs', 'affaires', 'services', 'authority', 'autorité', 'agency', 'agence',
    'organization', 'organisation', 'institute', 'institut', 'center', 'centre',
    'laboratory', 'laboratoire', 'hospital', 'hôpital', 'clinic', 'clinique',
    'school', 'école', 'university', 'université', 'college', 'collège',
    'company', 'société', 'corporation', 'corp', 'inc', 'ltd', 'sarl',
    # Mots génériques arabes (faux positifs)
    'جهاز', 'وزارة', 'مكتب', 'مكتبة', 'مستشفى', 'مدرسة', 'جامعة', 'مصادر', 'أفادت',
    '،في', '،في', 'الحيواني،', 'الحيواني', 'الوبائي', 'الوبائي،',
    # Descriptions de maladies comme lieux
    'تفشي', 'مرض', 'الالتهاب', 'العقدي', 'بالأبقار', 'النزف', 'الوبائي',
    'outbreak', 'disease', 'maladie', 'infection', 'epidemic', 'épidémie',
    # Actions/verbes arabes et phrases incomplètes
    'يقرر', 'منع', 'استيراد', 'يرصد', 'إصابات', 'توطن', 'سلالات', 'جديدة',
    'إطار', 'خطة', 'الهيئة', 'العامة', 'بسبب', 'مخاوف', 'من', 'إقدام', 'السلطات', 'على',
    'أبقار', 'مستوردة', 'الحر', 'الدافئة', 'التي',
    'decide', 'ban', 'import', 'detect', 'cases', 'outbreak', 'new', 'strains',
    # Noms de personnes (à exclure des lieux)
    'muhadjir', 'effendy', 'elvi', 'martina', 'muhammad', 'ahmed', 'ali', 'hassan', 'fatima',
    # Dates arabes
    'يوم', 'الأحد', 'المقبل', 'الجاري', 'القادم', 'اليوم', 'أمس', 'غداً',
    # Mots génériques français/anglais
    'jour', 'journée', 'day', 'semaine', 'week', 'mois', 'month', 'année', 'year',
    'dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi',
    'sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday',
    # Autres faux positifs
    'november', 'novembre', 'october', 'octobre', 'september', 'septembre',
    'january', 'janvier', 'february', 'février', 'march', 'mars',
    'april', 'avril', 'may', 'mai', 'june', 'juin', 'july', 'juillet',
    'august', 'août', 'december', 'décembre',
]

# Patterns de faux positifs à exclure complètement
EXCLUDED_PATTERNS = [
    r'^(agriculture|environment|department|ministry|office|bureau|ministère)',
    r'(agriculture|environment|department|ministry|office|bureau|ministère)$',
    r'^(جهاز|وزارة|مكتب|مصادر|أفادت)',
    r'(،في|،في|الحيواني،|الوبائي،)$',
    r'^(jour|day|semaine|week|mois|month)',
    r'^(november|novembre|october|octobre)',
]

# Patterns pour les lieux géographiques (multilingue)
LOCATION_PATTERNS = [
    # Format anglais: "in/at/from [Lieu], [Pays]" - avec validation
    r'\b(in|at|from|near|around|located in|based in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
    # Format: "[Lieu] County, [État]" - format très spécifique
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+County\s*,\s*([A-Z]{2})\b',  # Ex: "Rockland County, NY"
    # Format: "[Lieu], [Pays]" - mais exclure les faux positifs
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
    # Format: "[Lieu] Region/Province/State/District" - mais exclure "Department"
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(Region|Province|State|County|District|Prefecture)\b',
    # Format français: "en [Pays]", "dans [Région]", "à [Ville]" - mais exclure les ministères
    r'\b(en|dans|à|au|aux|depuis|vers)\s+([A-ZÉÀÈÙ][a-zéàèù]+(?:\s+[A-ZÉÀÈÙ][a-zéàèù]+)*)\b',
    # Format arabe: "في [مكان]", "من [مكان]", "إلى [مكان]" - mais exclure les faux positifs
    r'(?:في|ب|من|إلى|على|قرب|حول)\s+([\u0600-\u06FF]+(?:\s+[\u0600-\u06FF]+){0,4})\b',
    # Pays seuls en majuscules ou format standard
    r'\b([A-Z][a-z]+\s+(?:County|Region|Province|State|District|Région|Province|État|Département))\b',
    # Noms de pays arabes en transcription
    r'\b(Al-[A-Z][a-z]+|El-[A-Z][a-z]+|As-[A-Z][a-z]+)\b',
    # Format avec "of": "City of [Lieu]", "State of [Lieu]"
    r'\b(City|State|Province|Region|County|District)\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
    # Format avec parenthèses: "[Lieu] ([Pays])"
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\(([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\)\b',
    # États USA avec format: "[État] state"
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+state\b',
    # Villes avec "City": "[Lieu] City"
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+City\b',
    # Format avec tirets: "New-York", "Saint-Denis"
    r'\b([A-Z][a-z]+-[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
    # Codes postaux/états: "NY", "CA", "TX", etc. (seulement si précédés d'un lieu)
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*([A-Z]{2})\b',
]

# Dictionnaire de traduction de lieux (anglais/arabe -> français)
LOCATION_TRANSLATION = {
    # Pays en anglais -> français
    'usa': 'États-Unis', 'united states': 'États-Unis', 'us': 'États-Unis', 'america': 'États-Unis',
    'uk': 'Royaume-Uni', 'united kingdom': 'Royaume-Uni', 'britain': 'Royaume-Uni',
    'south korea': 'Corée du Sud', 'korea': 'Corée du Sud', 'south korean': 'Corée du Sud',
    'north korea': 'Corée du Nord',
    'kazakhstan': 'Kazakhstan',
    'afghanistan': 'Afghanistan',
    'pakistan': 'Pakistan',
    'zambia': 'Zambie',
    'botswana': 'Botswana',
    'philippines': 'Philippines',
    'indonesia': 'Indonésie', 'indonésie': 'Indonésie',
    'uganda': 'Ouganda',
    'brazil': 'Brésil', 'brésil': 'Brésil',
    "côte d'ivoire": "Côte d'Ivoire", "cote d'ivoire": "Côte d'Ivoire",
    'paraguay': 'Paraguay',
    'south africa': 'Afrique du Sud',
    'africa': 'Afrique', 'afrique': 'Afrique',
    'australia': 'Australie',
    'ireland': 'Irlande',
    'belgium': 'Belgique', 'belgique': 'Belgique',
    'netherlands': 'Pays-Bas',
    'germany': 'Allemagne',
    'spain': 'Espagne',
    'italy': 'Italie',
    'portugal': 'Portugal',
    'greece': 'Grèce',
    'poland': 'Pologne',
    'czech republic': 'République tchèque',
    'hungary': 'Hongrie',
    'romania': 'Roumanie',
    'bulgaria': 'Bulgarie',
    'croatia': 'Croatie',
    'serbia': 'Serbie',
    'switzerland': 'Suisse',
    'austria': 'Autriche',
    'sweden': 'Suède',
    'norway': 'Norvège',
    'denmark': 'Danemark',
    'finland': 'Finlande',
    'china': 'Chine',
    'japan': 'Japon',
    'india': 'Inde',
    'thailand': 'Thaïlande',
    'vietnam': 'Vietnam',
    'malaysia': 'Malaisie',
    'singapore': 'Singapour',
    'bangladesh': 'Bangladesh',
    'saudi arabia': 'Arabie saoudite',
    'uae': 'Émirats arabes unis',
    'qatar': 'Qatar',
    'kuwait': 'Koweït',
    'jordan': 'Jordanie',
    'lebanon': 'Liban',
    'yemen': 'Yémen',
    'oman': 'Oman',
    'bahrain': 'Bahreïn',
    'iraq': 'Irak',
    'iran': 'Iran',
    'syria': 'Syrie',
    'turkey': 'Turquie',
    'russia': 'Russie',
    'ukraine': 'Ukraine',
    # Pays en arabe -> français
    'مصر': 'Égypte',
    'المغرب': 'Maroc',
    'تونس': 'Tunisie',
    'الجزائر': 'Algérie',
    'لبنان': 'Liban',
    'الأردن': 'Jordanie',
    'السعودية': 'Arabie saoudite',
    'الإمارات': 'Émirats arabes unis',
    'قطر': 'Qatar',
    'الكويت': 'Koweït',
    'العراق': 'Irak',
    'إيران': 'Iran',
    'سوريا': 'Syrie',
    'ليبيا': 'Libye',
    'فرنسا': 'France',
}

# Dictionnaire de correspondances villes/régions -> pays
CITY_TO_COUNTRY = {
    # Villes/régions arabes -> pays
    'قنا': 'مصر', 'القاهرة': 'مصر', 'الإسكندرية': 'مصر', 'الجيزة': 'مصر', 'المنطقة الشرقية': 'السعودية',
    'المغرب': 'المغرب', 'الرباط': 'المغرب', 'الدار البيضاء': 'المغرب', 'فاس': 'المغرب',
    'تونس': 'تونس', 'الجزائر': 'الجزائر', 'لبنان': 'لبنان', 'الأردن': 'الأردن',
    'السعودية': 'السعودية', 'الإمارات': 'الإمارات', 'قطر': 'قطر', 'الكويت': 'الكويت',
    'فرنسا': 'France',
    # Villes/régions françaises -> pays
    'Corse': 'France', 'Corrèze': 'France', 'Allier': 'France', 'Vendée': 'France',
    'Indre-et-Loire': 'France', 'Paris': 'France', 'Lyon': 'France', 'Marseille': 'France',
    # Villes/régions anglaises -> pays
    'Kent': 'UK', 'Rockland County': 'USA', 'Rockland County, NY': 'USA', 'NY': 'USA', 'New York': 'USA',
    'Orange County': 'USA', 'Orange, County': 'USA', 'Orange County, NC': 'USA',
    'Chatham County': 'USA', 'Chatham, County': 'USA', 'Chatham County, GA': 'USA',
    'Burnham Woods Community': 'USA', 'Danville': 'USA', 'Kentucky': 'USA', 'Keeneland Race Course': 'USA',
    'Keen Lake': 'USA', 'Yellowstone National Park': 'USA', 'Yellowstone': 'USA', 'Coody Lake': 'USA',
    'Phala-Phala': 'South Africa', 'Limpopo': 'South Africa',
    'Belgium': 'Belgium', 'Belgique': 'Belgium',
    'Karaganda': 'Kazakhstan', 'South Korea': 'South Korea', 'Korea': 'South Korea',
    # Autres pays/régions
    'Afghanistan': 'Afghanistan', 'Pakistan': 'Pakistan', 'Zambia': 'Zambia',
    'Botswana': 'Botswana', 'Philippines': 'Philippines', 'Paraguay': 'Paraguay',
    'Indonesia': 'Indonesia', 'Pinrang': 'Indonesia', 'East Nusa Tenggara': 'Indonesia', 'NTT': 'Indonesia',
    'Uganda': 'Uganda', 'Ibanda': 'Uganda',
    'Brazil': 'Brazil', 'Ceará': 'Brazil', 'Ceara': 'Brazil', 'Piaui': 'Brazil', 'Paraiba': 'Brazil', 'São Paulo': 'Brazil',
    "Côte d'Ivoire": "Côte d'Ivoire", 'Wyoming': 'USA', 'Limpopo': 'South Africa', 'Polokwane': 'South Africa',
    'North Carolina': 'USA', 'NC': 'USA', 'Savannah': 'USA', 'Georgia': 'USA', 'GA': 'USA',
    'Danville': 'USA', 'Virginia': 'USA', 'VA': 'USA', 'NSW': 'Australia', 'Australia': 'Australia',
    'Ireland': 'Ireland', 'Kent': 'UK', 'UK': 'UK', 'United Kingdom': 'UK'
}

# Liste de pays connus
PAYS_CONNUS = [
    'France', 'USA', 'UK', 'Kazakhstan', 'South Korea', 'Afghanistan', 'Pakistan', 
    'Zambia', 'Botswana', 'Philippines', 'Indonesia', 'Uganda', 'Brazil', 
    "Côte d'Ivoire", 'Paraguay', 'South Africa', 'Australia', 'Ireland',
    'Belgium', 'Belgique', 'Netherlands', 'Switzerland', 'Austria', 'Sweden', 
    'Norway', 'Denmark', 'Finland', 'Poland', 'Czech Republic', 'Greece', 
    'Portugal', 'Romania', 'Bulgaria', 'Hungary', 'Croatia', 'Serbia',
    'Germany', 'Spain', 'Italy', 'China', 'Japan', 'India', 'Thailand', 
    'Vietnam', 'Malaysia', 'Singapore', 'Bangladesh', 'Saudi Arabia', 
    'UAE', 'Qatar', 'Kuwait', 'Jordan', 'Lebanon', 'Yemen', 'Oman', 'Bahrain',
    'Iraq', 'Iran', 'Syria', 'Turkey', 'Russia', 'Ukraine', 'Egypt', 'Morocco',
    'Algeria', 'Tunisia', 'Libya', 'Afrique', 'Africa'
]

# Codes d'état USA (2 lettres)
USA_STATE_CODES = [
    'NY', 'NC', 'GA', 'VA', 'CA', 'TX', 'FL', 'IL', 'PA', 'OH', 'MI', 'SC', 
    'WA', 'OR', 'AZ', 'NV', 'CO', 'UT', 'NM', 'OK', 'AR', 'LA', 'MS', 'AL', 
    'TN', 'KY', 'WV', 'MD', 'DE', 'NJ', 'CT', 'RI', 'MA', 'VT', 'NH', 'ME', 
    'AK', 'HI', 'ID', 'MT', 'WY', 'ND', 'SD', 'NE', 'KS', 'MO', 'IA', 'MN', 
    'WI', 'IN'
]

# ============================================================================
# ANIMAUX
# ============================================================================

# Dictionnaire d'animaux par langue
ANIMAUX = {
    'en': [
        # Farm animals
        'cattle', 'cows', 'cow', 'bull', 'bulls', 'ox', 'oxen', 'calf', 'calves',
        'poultry', 'chickens', 'chicken', 'ducks', 'duck', 'geese', 'goose', 'turkeys', 'turkey',
        'sheep', 'lamb', 'lambs', 'ewe', 'ewes', 'ram', 'rams',
        'pigs', 'pig', 'swine', 'boar', 'boars', 'sow', 'sows',
        'horses', 'horse', 'mare', 'mares', 'stallion', 'stallions', 'pony', 'ponies',
        'goats', 'goat', 'billy', 'nanny', 'kid', 'kids',
        'rabbits', 'rabbit', 'bunny', 'bunnies',
        'donkeys', 'donkey', 'mule', 'mules',
        # Wild animals
        'deer', 'doe', 'buck', 'bucks', 'fawn', 'fawns',
        'wild boar', 'wild boars', 'boar',
        'foxes', 'fox', 'vixen', 'vixens',
        'wolves', 'wolf', 'pack',
        'bears', 'bear', 'cub', 'cubs',
        # Pets
        'dogs', 'dog', 'puppy', 'puppies',
        'cats', 'cat', 'kitten', 'kittens',
        # Aquatic animals
        'fish', 'fishes',
        # Exotic animals
        'camel', 'camels', 'dromedary', 'dromedaries',
        'llama', 'llamas', 'alpaca', 'alpacas',
        'ostrich', 'ostriches',
        # Birds
        'bird', 'birds', 'swan', 'swans', 'eagle', 'eagles', 'falcon', 'falcons',
        'vulture', 'vultures', 'crow', 'crows', 'raven', 'ravens', 'magpie', 'magpies',
        'sparrow', 'sparrows', 'blackbird', 'blackbirds', 'robin', 'robins',
        # Rodents
        'mouse', 'mice', 'rat', 'rats', 'hamster', 'hamsters', 'guinea pig', 'guinea pigs',
        # Others
        'hedgehog', 'hedgehogs', 'squirrel', 'squirrels', 'hare', 'hares'
    ],
    'fr': [
        # Animaux de ferme
        'bovins', 'vaches', 'vache', 'taureaux', 'taureau', 'bœuf', 'bœufs', 'veau', 'veaux',
        'volailles', 'poulets', 'poulet', 'canards', 'canard', 'oies', 'oie', 'dindes', 'dinde',
        'ovins', 'moutons', 'mouton', 'brebis', 'agneaux', 'agneau', 'bélier', 'béliers',
        'porcins', 'porcs', 'porc', 'cochons', 'cochon', 'truie', 'truies', 'verrat', 'verrats',
        'chevaux', 'cheval', 'jument', 'juments', 'étalon', 'étalons', 'poney', 'poneys',
        'caprins', 'chèvres', 'chèvre', 'bouc', 'boucs', 'chevreau', 'chevreaux',
        'lapins', 'lapin', 'lapereau', 'lapereaux',
        'ânes', 'âne', 'mule', 'mules',
        # Animaux sauvages
        'cerfs', 'cerf', 'biche', 'biches', 'faon', 'faons',
        'sangliers', 'sanglier',
        'renards', 'renard', 'renarde', 'renardes',
        'loups', 'loup', 'meute',
        'ours', 'ourson', 'oursons',
        # Animaux de compagnie
        'chiens', 'chien', 'chiot', 'chiots',
        'chats', 'chat', 'chaton', 'chatons',
        # Animaux aquatiques
        'poissons', 'poisson',
        # Animaux exotiques
        'chameaux', 'chameau', 'dromadaire', 'dromadaires',
        'lama', 'lamas', 'alpaga', 'alpagas',
        'autruche', 'autruches',
        # Oiseaux
        'oiseaux', 'oiseau', 'cygne', 'cygnes', 'aigle', 'aigles', 'faucon', 'faucons',
        'vautour', 'vautours', 'corbeau', 'corbeaux', 'pie', 'pies',
        'moineau', 'moineaux', 'merle', 'merles', 'rouge-gorge', 'rouges-gorges',
        # Rongeurs
        'souris', 'rat', 'rats', 'hamster', 'hamsters', 'cochon d\'Inde', 'cochons d\'Inde',
        # Autres
        'hérisson', 'hérissons', 'écureuil', 'écureuils', 'lièvre', 'lièvres'
    ],
    'ar': [
        # حيوانات المزرعة
        'أبقار', 'بقرة', 'عجول', 'عجل', 'ثيران', 'ثور', 'بقرة', 'أبقار',
        'دواجن', 'دجاج', 'دجاجة', 'بط', 'بطة', 'ديوك', 'ديك', 'أوز', 'أوزة',
        'أغنام', 'خروف', 'خرفان', 'نعاج', 'نعجة', 'كبش', 'أكباش',
        'خنازير', 'خنزير', 'خنزيرة',
        'خيول', 'حصان', 'فرس', 'مهر', 'مهرة',
        'ماعز', 'معزة', 'جدي', 'جدية',
        'أرانب', 'أرنب', 'أرنبة',
        'حمير', 'حمار', 'حمارة',
        # حيوانات برية
        'غزلان', 'غزال', 'غزالة',
        'خنازير برية', 'خنزير بري',
        'ثعالب', 'ثعلب', 'ذئاب', 'ذئب',
        'دببة', 'دب', 'دبة',
        # حيوانات أليفة
        'كلاب', 'كلب', 'كلبة', 'جرو', 'جراء',
        'قطط', 'قطة', 'قط', 'هرة', 'هر',
        # حيوانات مائية
        'أسماك', 'سمك',
        # حيوانات exotiques
        'جمال', 'جمل', 'جملة', 'إبل',
        'لاما', 'ألبكة',
        'نعام', 'نعامة',
        # طيور
        'طيور', 'طائر', 'بجعة', 'بجع', 'نسور', 'نسر', 'صقور', 'صقر',
        'غربان', 'غراب', 'عقبان', 'عقاب',
        # قوارض
        'فئران', 'فأر', 'جرذان', 'جرذ', 'هامستر',
        # أخرى
        'قنافذ', 'قنفذ', 'سنجاب', 'سناجب', 'أرانب برية', 'أرنب بري'
    ]
}

# Patterns d'animaux invalides (faux positifs)
INVALID_ANIMAL_PATTERNS = [
    'zoutnet', 'news', 'oms', 'who', 'fao', 'oie', 'woah', 'cdc', 'efsa', 'anses', 'ecdc',
    'usda', 'aphis', 'defra', 'dgal', 'non trouvé', 'non trouve', 'not found', 'n/a', 'none',
    'ministère', 'ministry', 'وزارة', 'organisme', 'organization', 'منظمة', 'agence', 'agency',
    'site', 'web', 'page', 'article', 'source', 'médias', 'media', 'press', 'journal',
    # Rejeter les lieux (pas des animaux)
    'lieu', 'lieux', 'place', 'places', 'location', 'locations', 'nouveau', 'nouveaux',
    'new', 'ville', 'city', 'pays', 'country', 'région', 'region', 'état', 'state',
    'ville', 'village', 'town', 'city', 'country', 'pays', 'region', 'région',
    'continent', 'afrique', 'africa'
]

# Dictionnaire de correspondance : nom dans n'importe quelle langue -> nom standardisé (français)
ANIMAL_MAPPING = {
    # Bovins / Cattle
    'cattle': 'bovins', 'cow': 'bovins', 'cows': 'bovins', 'bull': 'bovins', 'bulls': 'bovins',
    'ox': 'bovins', 'oxen': 'bovins', 'bovin': 'bovins', 'vache': 'bovins', 'vaches': 'bovins',
    'bœuf': 'bovins', 'bœufs': 'bovins', 'taureau': 'bovins', 'taureaux': 'bovins',
    'أبقار': 'bovins', 'بقرة': 'bovins', 'عجول': 'bovins', 'عجل': 'bovins', 'ثيران': 'bovins', 'ثور': 'bovins',
    # Volailles / Poultry
    'poultry': 'volailles', 'chicken': 'volailles', 'chickens': 'volailles', 'duck': 'volailles', 'ducks': 'volailles',
    'turkey': 'volailles', 'turkeys': 'volailles', 'poulet': 'volailles', 'poulets': 'volailles',
    'canard': 'volailles', 'canards': 'volailles', 'dinde': 'volailles', 'dindes': 'volailles',
    'دواجن': 'volailles', 'دجاج': 'volailles', 'دجاجة': 'volailles', 'بط': 'volailles', 'بطة': 'volailles', 'ديوك': 'volailles', 'ديك': 'volailles',
    # Ovins / Sheep
    'sheep': 'ovins', 'lamb': 'ovins', 'lambs': 'ovins', 'ewe': 'ovins', 'ewes': 'ovins',
    'mouton': 'ovins', 'moutons': 'ovins', 'brebis': 'ovins', 'agneau': 'ovins', 'agneaux': 'ovins',
    'أغنام': 'ovins', 'خروف': 'ovins', 'خرفان': 'ovins', 'نعاج': 'ovins', 'نعجة': 'ovins',
    # Porcins / Pigs
    'pig': 'porcins', 'pigs': 'porcins', 'swine': 'porcins', 'boar': 'porcins', 'boars': 'porcins',
    'porc': 'porcins', 'porcs': 'porcins', 'cochon': 'porcins', 'cochons': 'porcins',
    'خنازير': 'porcins', 'خنزير': 'porcins',
    # Chevaux / Horses
    'horse': 'chevaux', 'horses': 'chevaux', 'mare': 'chevaux', 'mares': 'chevaux',
    'cheval': 'chevaux', 'jument': 'chevaux', 'juments': 'chevaux',
    'خيول': 'chevaux', 'حصان': 'chevaux', 'فرس': 'chevaux',
    # Caprins / Goats
    'goat': 'caprins', 'goats': 'caprins', 'chèvre': 'caprins', 'chèvres': 'caprins', 'caprin': 'caprins',
    'ماعز': 'caprins', 'معزة': 'caprins',
    # Oiseaux / Birds
    'bird': 'oiseaux', 'birds': 'oiseaux', 'swan': 'oiseaux', 'swans': 'oiseaux',
    'oiseau': 'oiseaux', 'cygne': 'oiseaux', 'cygnes': 'oiseaux',
    'eagle': 'oiseaux', 'eagles': 'oiseaux', 'aigle': 'oiseaux', 'aigles': 'oiseaux',
    'falcon': 'oiseaux', 'falcons': 'oiseaux', 'faucon': 'oiseaux', 'faucons': 'oiseaux',
    'vulture': 'oiseaux', 'vultures': 'oiseaux', 'vautour': 'oiseaux', 'vautours': 'oiseaux',
    'crow': 'oiseaux', 'crows': 'oiseaux', 'corbeau': 'oiseaux', 'corbeaux': 'oiseaux',
    'raven': 'oiseaux', 'ravens': 'oiseaux', 'magpie': 'oiseaux', 'magpies': 'oiseaux',
    'sparrow': 'oiseaux', 'sparrows': 'oiseaux', 'blackbird': 'oiseaux', 'blackbirds': 'oiseaux',
    'robin': 'oiseaux', 'robins': 'oiseaux', 'moineau': 'oiseaux', 'moineaux': 'oiseaux',
    'merle': 'oiseaux', 'merles': 'oiseaux', 'rouge-gorge': 'oiseaux', 'rouges-gorges': 'oiseaux',
    'طيور': 'oiseaux', 'طائر': 'oiseaux', 'بجعة': 'oiseaux', 'بجع': 'oiseaux',
    'نسور': 'oiseaux', 'نسر': 'oiseaux', 'صقور': 'oiseaux', 'صقر': 'oiseaux',
    'غربان': 'oiseaux', 'غراب': 'oiseaux', 'عقبان': 'oiseaux', 'عقاب': 'oiseaux',
    # Lapins / Rabbits
    'rabbit': 'lapins', 'rabbits': 'lapins', 'bunny': 'lapins', 'bunnies': 'lapins',
    'lapin': 'lapins', 'lapins': 'lapins', 'lapereau': 'lapins', 'lapereaux': 'lapins',
    'أرانب': 'lapins', 'أرنب': 'lapins', 'أرنبة': 'lapins',
    # Chiens / Dogs
    'dog': 'chiens', 'dogs': 'chiens', 'puppy': 'chiens', 'puppies': 'chiens',
    'chien': 'chiens', 'chiens': 'chiens', 'chiot': 'chiens', 'chiots': 'chiens',
    'كلاب': 'chiens', 'كلب': 'chiens', 'كلبة': 'chiens', 'جرو': 'chiens', 'جراء': 'chiens',
    # Chats / Cats
    'cat': 'chats', 'cats': 'chats', 'kitten': 'chats', 'kittens': 'chats',
    'chat': 'chats', 'chats': 'chats', 'chaton': 'chats', 'chatons': 'chats',
    'قطط': 'chats', 'قطة': 'chats', 'قط': 'chats', 'هرة': 'chats', 'هر': 'chats',
    # Cerfs / Deer
    'deer': 'cerfs', 'doe': 'cerfs', 'buck': 'cerfs', 'bucks': 'cerfs', 'fawn': 'cerfs', 'fawns': 'cerfs',
    'cerf': 'cerfs', 'cerfs': 'cerfs', 'biche': 'cerfs', 'biches': 'cerfs', 'faon': 'cerfs', 'faons': 'cerfs',
    'غزلان': 'cerfs', 'غزال': 'cerfs', 'غزالة': 'cerfs',
    # Sangliers / Wild boar
    'wild boar': 'sangliers', 'wild boars': 'sangliers', 'boar': 'sangliers', 'boars': 'sangliers',
    'sanglier': 'sangliers', 'sangliers': 'sangliers',
    'خنازير برية': 'sangliers', 'خنزير بري': 'sangliers',
    # Renards / Foxes
    'fox': 'renards', 'foxes': 'renards', 'vixen': 'renards', 'vixens': 'renards',
    'renard': 'renards', 'renards': 'renards', 'renarde': 'renards', 'renardes': 'renards',
    'ثعالب': 'renards', 'ثعلب': 'renards',
    # Loups / Wolves
    'wolf': 'loups', 'wolves': 'loups', 'pack': 'loups',
    'loup': 'loups', 'loups': 'loups', 'meute': 'loups',
    'ذئاب': 'loups', 'ذئب': 'loups',
    # Ours / Bears
    'bear': 'ours', 'bears': 'ours', 'cub': 'ours', 'cubs': 'ours',
    'ours': 'ours', 'ourson': 'ours', 'oursons': 'ours',
    'دببة': 'ours', 'دب': 'ours', 'دبة': 'ours',
    # Poissons / Fish
    'fish': 'poissons', 'fishes': 'poissons',
    'poisson': 'poissons', 'poissons': 'poissons',
    'أسماك': 'poissons', 'سمك': 'poissons',
    # Chameaux / Camels
    'camel': 'chameaux', 'camels': 'chameaux', 'dromedary': 'chameaux', 'dromedaries': 'chameaux',
    'chameau': 'chameaux', 'chameaux': 'chameaux', 'dromadaire': 'chameaux', 'dromadaires': 'chameaux',
    'جمال': 'chameaux', 'جمل': 'chameaux', 'جملة': 'chameaux', 'إبل': 'chameaux',
    # Lamas
    'llama': 'lamas', 'llamas': 'lamas', 'alpaca': 'lamas', 'alpacas': 'lamas',
    'lama': 'lamas', 'lamas': 'lamas', 'alpaga': 'lamas', 'alpagas': 'lamas',
    'لاما': 'lamas', 'ألبكة': 'lamas',
    # Autruches / Ostriches
    'ostrich': 'autruches', 'ostriches': 'autruches',
    'autruche': 'autruches', 'autruches': 'autruches',
    'نعام': 'autruches', 'نعامة': 'autruches',
    # Rongeurs / Rodents
    'mouse': 'rongeurs', 'mice': 'rongeurs', 'rat': 'rongeurs', 'rats': 'rongeurs',
    'hamster': 'rongeurs', 'hamsters': 'rongeurs', 'guinea pig': 'rongeurs', 'guinea pigs': 'rongeurs',
    'souris': 'rongeurs', 'rat': 'rongeurs', 'rats': 'rongeurs', 'hamster': 'rongeurs', 'hamsters': 'rongeurs',
    'cochon d\'Inde': 'rongeurs', 'cochons d\'Inde': 'rongeurs',
    'فئران': 'rongeurs', 'فأر': 'rongeurs', 'جرذان': 'rongeurs', 'جرذ': 'rongeurs', 'هامستر': 'rongeurs',
    # Hérissons / Hedgehogs
    'hedgehog': 'hérissons', 'hedgehogs': 'hérissons',
    'hérisson': 'hérissons', 'hérissons': 'hérissons',
    'قنافذ': 'hérissons', 'قنفذ': 'hérissons',
    # Écureuils / Squirrels
    'squirrel': 'écureuils', 'squirrels': 'écureuils',
    'écureuil': 'écureuils', 'écureuils': 'écureuils',
    'سنجاب': 'écureuils', 'سناجب': 'écureuils',
    # Lièvres / Hares
    'hare': 'lièvres', 'hares': 'lièvres',
    'lièvre': 'lièvres', 'lièvres': 'lièvres',
    'أرانب برية': 'lièvres', 'أرنب بري': 'lièvres',
    # Ânes / Donkeys
    'donkey': 'ânes', 'donkeys': 'ânes', 'mule': 'ânes', 'mules': 'ânes',
    'âne': 'ânes', 'ânes': 'ânes', 'mule': 'ânes', 'mules': 'ânes',
    'حمير': 'ânes', 'حمار': 'ânes', 'حمارة': 'ânes',
}

# ============================================================================
# VALIDATION ET FILTRAGE
# ============================================================================

# Réponses invalides pour les organismes
INVALID_RESPONSES = [
    'NON TROUVE', 'NON TROUVEE', 'NON TRUVE', 'NON TROUVÉ', 'NON TROUVÉE',
    'NOT FOUND', 'N/A', 'NONE', 'NO FOUND', 'NOT FOUNDE', 'NO TROUVE'
]

# Patterns invalides pour les organismes
INVALID_PATTERNS = [
    'assistant', 'helpful', 'extract', 'you are', 'tu es', 'expert', 'citation', '...', 
    'minimalism', 'uniqueent', 'absolute', 'revised', 'here\'s', 'answer', 'sure', 'correct',
    'question:', 'question', 'suggested', 'changes', 'updated', 'version'
]

# Débuts de phrases à rejeter (indicateurs de phrases complètes)
PHRASE_STARTERS = [
    'nous sommes', 'nous', 'ils sont', 'ils', 'elles sont', 'elles', 'je suis', 'je',
    'tu es', 'tu', 'il est', 'il', 'elle est', 'elle', 'c\'est', 'ce sont',
    'we are', 'we', 'they are', 'they', 'i am', 'i', 'you are', 'you', 'it is', 'it',
    'this is', 'that is', 'these are', 'those are'
]

# Verbes conjugués (indicateurs de phrases complètes)
CONJUGATED_VERBS = [
    'sommes', 'sont', 'est', 'sont', 'êtes', 'suis', 'are', 'is', 'am', 'was', 'were',
    'serons', 'seront', 'sera', 'serai', 'seras', 'will be', 'would be',
    'avons', 'ont', 'a', 'as', 'ai', 'have', 'has', 'had', 'will have',
    'faisons', 'font', 'fait', 'fais', 'faire', 'do', 'does', 'did', 'will do',
    'pouvons', 'peuvent', 'peut', 'peux', 'can', 'could', 'may', 'might'
]

# Termes génériques à rejeter
GENERIC_TERMS = [
    'l\'organisation', 'the organization', 'l\'institution', 'the institution', 
    'le ministère', 'the ministry', 'المنظمة', 'المؤسسة', 'الوزارة',
    'un', 'une', 'le', 'la', 'les', 'the', 'a', 'an', 'of', 'de', 'du', 'des'
]

# Préfixes à supprimer des réponses Ollama
PREFIXES_TO_REMOVE = [
    'nom du organisme:', 'nom de l\'organisme:', 'nom de l\'organisation:',
    'organization name:', 'organization:', 'organisme:', 'organisation:',
    'nom:', 'name:', 'institution:', 'ministry:', 'ministère:'
]

# Acronymes connus d'organismes
KNOWN_ACRONYMS = [
    'OMS', 'WHO', 'FAO', 'OIE', 'WOAH', 'CDC', 'EFSA', 'ANSES', 'ECDC', 
    'USDA', 'APHIS', 'DEFRA', 'DGAL', 'UN', 'EU'
]

