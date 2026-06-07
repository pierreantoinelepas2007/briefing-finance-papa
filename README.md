# 📊 Finance Newsletter — Guide d'installation

## 1. Installer les dépendances
```bash
pip install -r requirements.txt
```

## 2. Créer ta clé API Groq (gratuit)
1. Va sur https://console.groq.com
2. Crée un compte gratuit
3. Clique sur **"API Keys"** → **"Create API Key"**
4. Copie la clé dans `config.py`

## 3. Créer un mot de passe d'application Gmail
1. Va sur https://myaccount.google.com/security
2. Active la **validation en 2 étapes** si ce n'est pas fait
3. Cherche **"Mots de passe des applications"**
4. Crée un mot de passe pour "Mail" → copie les 16 caractères dans `config.py`

## 4. Remplir config.py
Ouvre `config.py` et remplis les 4 champs.

## 5. Tester le script
```bash
python newsletter.py
```

## 6. Automatiser chaque matin (cron job)

### Sur Mac/Linux (ordi du père)
```bash
crontab -e
```
Ajoute cette ligne pour envoyer chaque matin à 7h00 :
```
0 7 * * * cd /chemin/vers/finance-newsletter && python newsletter.py
```

### Sur Windows (ordi du père)
Utilise le **Planificateur de tâches Windows** :
1. Recherche "Planificateur de tâches" dans le menu Démarrer
2. "Créer une tâche de base"
3. Déclencheur : tous les jours à 7h00
4. Action : lancer `python newsletter.py`

## Sources utilisées
- Reuters Business & Commodities
- Yahoo Finance
- CoinTelegraph (crypto)
- The Economist (économie)
- MoneVox (immobilier)
- OilPrice (matières premières)
