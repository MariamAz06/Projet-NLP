#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script d'exécution pour l'extraction de contenu
Exécute src/extraction_complete.py depuis la racine du projet
"""

import sys
from pathlib import Path

# Obtenir le répertoire racine du projet (parent de scripts/)
project_root = Path(__file__).parent.parent

# Ajouter le répertoire racine au PYTHONPATH
sys.path.insert(0, str(project_root))

# Changer le répertoire de travail vers la racine
import os
os.chdir(project_root)

# Importer et exécuter le script d'extraction
from src.extraction_complete import main

if __name__ == "__main__":
    main()

