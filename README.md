# FLAIR — Démo locale

Interface web de démonstration du moteur d'analyse forensique documentaire FLAIR.

---

## 📋 Prérequis

- **Système** : Windows 10/11 (8 Go de RAM suffisent amplement, l'appli est légère)
- **Deux méthodes d'installation** : choisis **UN** des deux guides ci-dessous
  - 🐳 **Avec Docker** → le plus simple, pas de Python à installer
  - 🐍 **Sans Docker** → avec Python directement

---

## 🐳 Option 1 — Installation avec Docker (recommandée)

### 1. Installer Docker Desktop

Télécharge et installe **Docker Desktop for Windows** :
👉 https://www.docker.com/products/docker-desktop/

Pendant l'installation, coche bien **"Use WSL 2 instead of Hyper-V"** (c'est mieux pour Windows).
Redémarre le PC si demandé, puis ouvre Docker Desktop une fois pour qu'il démarre en arrière-plan.

### 2. Récupérer les fichiers du projet

Copie le dossier du projet (celui qui contient `app.py`, `Dockerfile`, `requirements.txt`)
sur ton ordinateur, par exemple dans `C:\Users\TonNom\demo_flair\`.

### 3. Ouvrir un terminal

Ouvre **l'Invite de commandes (CMD)** ou **PowerShell** dans le dossier du projet :
- Dans l'explorateur de fichiers, va dans `C:\Users\TonNom\demo_flair\`
- Clique dans la barre d'adresse en haut, tape `cmd` puis appuie sur Entrée

### 4. Construire l'image Docker

Dans le terminal qui s'ouvre, exécute :

```bash
docker build --no-cache -t flair-demo .
```

⏱ Attends quelques minutes la première fois (téléchargement de Python, etc.)

### 5. Lancer le conteneur

⚠️ **Remplace `ta_cle` par ta vraie clé API FLAIR** avant d'exécuter :

```bash
docker run -p 8080:8080 -e FLAIR_API_URL="https://api.myflair.app/v1/analyze" -e FLAIR_API_KEY="ta_cle" flair-demo
```

### 6. Ouvrir l'application

Ouvre ton navigateur et va sur :
👉 **http://localhost:8080**

---

## 🐍 Option 2 — Installation sans Docker (avec Python)

### 1. Installer Python

Télécharge **Python 3.12** pour Windows :
👉 https://www.python.org/downloads/release/python-3120/

⚠️ **Très important** : pendant l'installation, **coche la case "Add Python to PATH"**
en bas de la première fenêtre, puis clique sur "Install Now".

Vérifie l'installation : ouvre un CMD et tape :
```bash
python --version
```
Ça doit afficher `Python 3.12.x`

### 2. Récupérer les fichiers du projet

Copie le dossier du projet dans `C:\Users\TonNom\demo_flair\`.

### 3. Ouvrir un terminal dans le dossier

Dans l'explorateur, va dans `C:\Users\TonNom\demo_flair\`, clique dans la barre
d'adresse, tape `cmd` puis Entrée.

### 4. Créer un environnement virtuel (recommandé)

```bash
python -m venv venv
venv\Scripts\activate
```

Tu dois voir `(venv)` apparaître en début de ligne dans le terminal.

### 5. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 6. Définir les variables d'environnement (CMD)

Si tu utilises **l'Invite de commandes (CMD)** :
```cmd
set FLAIR_API_URL=https://api.myflair.app/v1/analyze
set FLAIR_API_KEY=ta_cle
```

Si tu utilises **PowerShell** :
```powershell
$env:FLAIR_API_URL = "https://api.myflair.app/v1/analyze"
$env:FLAIR_API_KEY = "ta_cle"
```

⚠️ Remplace `ta_cle` par ta vraie clé API.

### 7. Lancer l'application

```bash
python app.py
```

### 8. Ouvrir l'application

Ouvre ton navigateur et va sur :
👉 **http://localhost:8080**

---

## ⚙️ Variables d'environnement

| Variable | Valeur par défaut | Description |
|---|---|---|
| `FLAIR_API_URL` | `https://api.myflair.app/v1/analyze` | URL de l'API FLAIR |
| `FLAIR_API_KEY` | *(vide)* | **⚠️ OBLIGATOIRE** — Ta clé d'accès à l'API |
| `PORT` | `8080` | Port du serveur web |

---

## 🧪 Utilisation

1. Sur la page d'accueil, glisse-dépose un document (PDF, JPEG, PNG) ou clique pour en sélectionner un.
2. Le pipeline d'analyse se lance automatiquement — 8 couches forensiques s'exécutent.
3. Consulte le verdict final, le score de risque et le détail de chaque couche.
4. Clique sur **"Réponse JSON de l'API"** en bas pour voir la réponse brute.

---

## 🔄 Pour arrêter l'application

- **Avec Docker** : fais `Ctrl+C` dans le terminal, ou va dans Docker Desktop → Containers → Stop
- **Sans Docker** : fais `Ctrl+C` dans le terminal

---

## 💡 Notes pour Windows 8 Go RAM

Rien de spécial à faire ! Cette appli est très légère :
- Le conteneur Docker utilise ~150-200 Mo de RAM
- Sans Docker, Python utilise ~80-120 Mo de RAM

Si Docker Desktop te semble lourd, préfère l'**Option 2 (sans Docker)**.

---

## 🆘 Erreurs courantes

| Symptôme | Solution |
|---|---|
| `docker` n'est pas reconnu | Redémarre ton PC après l'installation de Docker Desktop |
| Erreur `401 Unauthorized` | Vérifie que `FLAIR_API_KEY` contient la bonne clé (sans espace) |
| Erreur `Connection refused` | Vérifie que l'URL `FLAIR_API_URL` est correcte |
| Le navigateur affiche une page blanche | Attends 5-10 secondes, le serveur démarre doucement |