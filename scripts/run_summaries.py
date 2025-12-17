#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script d'exécution pour la génération de résumés
Exécute src/resumes.py depuis la racine du projet
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

# Importer et exécuter le script de résumés
if __name__ == "__main__":
    import importlib.util
    spec = importlib.util.spec_from_file_location("resumes", project_root / "src" / "resumes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

