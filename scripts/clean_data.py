#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de nettoyage de la base de données CSV
Règles :
- Aucune ligne ne doit être supprimée
- Aucune information ne doit être perdue
- Les valeurs manquantes doivent être traitées, pas éliminées
- Les champs vides → "non détecté"
- "unknown" → "non détecté"
- Les titres "Erreur d'extraction" → "site inaccessible"
"""

import csv
import sys
from pathlib import Path

def clean_field(value):
    """
    Nettoie un champ individuel :
    - Chaîne vide ou None → "non détecté"
    - "unknown" → "non détecté"
    - Conserve les autres valeurs
    """
    if value is None:
        return "non détecté"
    
    # Convertir en string et nettoyer les espaces
    value_str = str(value).strip()
    
    # Si vide après nettoyage, retourner "non détecté"
    if value_str == "":
        return "non détecté"
    
    # Remplacer "unknown" (insensible à la casse) par "non détecté"
    if value_str.lower() == "unknown":
        return "non détecté"
    
    return value_str

def clean_row(row, titre_index):
    """
    Nettoie une ligne :
    - Remplace les champs vides par "non détecté"
    - Remplace "Erreur d'extraction" dans le titre par "site inaccessible"
    """
    cleaned_row = []
    
    for i, field in enumerate(row):
        cleaned_field = clean_field(field)
        
        # Si c'est le champ Titre et qu'il contient "Erreur d'extraction", le remplacer
        if i == titre_index and "Erreur d'extraction" in cleaned_field:
            cleaned_field = "site inaccessible"
        
        cleaned_row.append(cleaned_field)
    
    return cleaned_row

def clean_csv(input_file, output_file):
    """
    Nettoie le fichier CSV complet
    """
    try:
        with open(input_file, 'r', encoding='utf-8', newline='') as infile:
            # Détecter le délimiteur et lire le fichier
            sample = infile.read(1024)
            infile.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.reader(infile, delimiter=delimiter)
            
            # Lire l'en-tête
            header = next(reader)
            
            # Trouver l'index de la colonne "Titre"
            try:
                titre_index = header.index("Titre")
            except ValueError:
                # Si "Titre" n'existe pas, chercher des variantes
                titre_index = None
                for i, col in enumerate(header):
                    if "Titre" in col or "titre" in col.lower():
                        titre_index = i
                        break
                if titre_index is None:
                    print("Avertissement : Colonne 'Titre' non trouvee, traitement des erreurs d'extraction ignore")
            
            # Écrire le fichier nettoyé
            with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
                writer = csv.writer(outfile, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)
                
                # Écrire l'en-tête
                writer.writerow(header)
                
                # Traiter chaque ligne
                row_count = 0
                for row in reader:
                    # S'assurer que la ligne a le bon nombre de colonnes
                    while len(row) < len(header):
                        row.append("")
                    
                    # Nettoyer la ligne
                    cleaned_row = clean_row(row, titre_index)
                    writer.writerow(cleaned_row)
                    row_count += 1
                
                print(f"Nettoyage termine : {row_count} lignes traitees")
                print(f"Fichier sauvegarde : {output_file}")
    
    except Exception as e:
        print(f"Erreur lors du nettoyage : {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Obtenir le répertoire racine du projet (parent de scripts/)
    project_root = Path(__file__).parent.parent
    
    input_file = project_root / "data" / "summarized_articles.csv"
    output_file = project_root / "data" / "final_dataset.csv"
    
    print("Debut du nettoyage de la base de donnees...")
    print(f"Fichier d'entree : {input_file}")
    print(f"Fichier de sortie : {output_file}")
    print()
    
    clean_csv(str(input_file), str(output_file))
    
    print()
    print("Nettoyage reussi !")

