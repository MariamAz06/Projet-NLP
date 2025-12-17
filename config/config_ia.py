# config_ia.py

USE_OLLAMA = True
# Modèles rapides recommandés (du plus rapide au plus lent) :
# - tinyllama (très rapide, ~637MB) : ollama pull tinyllama
# - phi3:mini (rapide et efficace, ~2.2GB) : ollama pull phi3:mini ✅ INSTALLÉ
# - phi3 (rapide et efficace, ~3.8GB) : ollama pull phi3
# - llama3.2 (équilibré, ~2GB) : ollama pull llama3.2
# - llama2 (plus lent mais meilleur, ~3.8GB) : ollama pull llama2 ✅ INSTALLÉ
# - mistral (bon équilibre, ~4.1GB) : ollama pull mistral
OLLAMA_MODEL = "phi3:mini"  





