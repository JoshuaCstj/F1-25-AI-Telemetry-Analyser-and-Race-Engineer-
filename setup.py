"""
F1 25 Race Engineer - Installation Automatique
Installe toutes les dépendances nécessaires
"""

import subprocess
import sys
import os
from pathlib import Path

def print_header(text):
    """Affiche un en-tête stylé"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")

def print_step(number, text):
    """Affiche une étape"""
    print(f"\n🔧 Étape {number}: {text}")
    print("-" * 70)

def run_command(command, description):
    """Exécute une commande et affiche le résultat"""
    print(f"⏳ {description}...")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✅ {description} - Terminé!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur: {e}")
        print(f"   Sortie: {e.stdout}")
        print(f"   Erreur: {e.stderr}")
        return False

def check_python_version():
    """Vérifie la version de Python"""
    version = sys.version_info
    print(f"🐍 Python {version.major}.{version.minor}.{version.micro} détecté")
    
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print("❌ Python 3.7 ou supérieur est requis!")
        print("   Téléchargez-le sur: https://www.python.org/downloads/")
        return False
    
    print("✅ Version de Python compatible")
    return True

def install_dependencies():
    """Installe toutes les dépendances"""
    print_step(1, "Installation des bibliothèques Python")
    
    dependencies = [
        ("requests", "Appels API"),
        ("pyttsx3", "Synthèse vocale"),
        ("SpeechRecognition", "Reconnaissance vocale"),
        ("pywin32", "Windows COM (TTS amélioré)"),
        ("pyaudio", "Capture audio microphone")
    ]
    
    failed = []
    
    for package, description in dependencies:
        print(f"\n📦 Installation de {package} ({description})...")
        
        if package == "pyaudio":
            # pyaudio est parfois difficile sur Windows
            if not run_command(f'pip install {package}', f"Installation de {package}"):
                print(f"⚠️ {package} a échoué avec pip, essai avec pipwin...")
                if not run_command('pip install pipwin', "Installation de pipwin"):
                    failed.append(package)
                    continue
                if not run_command(f'pipwin install {package}', f"Installation de {package} via pipwin"):
                    failed.append(package)
                    print(f"⚠️ {package} optionnel - Les commandes vocales pourraient ne pas fonctionner")
        else:
            if not run_command(f'pip install {package}', f"Installation de {package}"):
                failed.append(package)
    
    if failed:
        print(f"\n⚠️ Packages qui ont échoué: {', '.join(failed)}")
        if 'pyaudio' in failed:
            print("💡 pyaudio est optionnel - L'app fonctionnera sans commandes vocales")
        return len(failed) <= 1  # OK si seulement pyaudio a échoué
    
    print("\n✅ Toutes les dépendances sont installées!")
    return True

def create_launcher_scripts():
    """Crée des scripts de lancement faciles"""
    print_step(2, "Création des raccourcis de lancement")
    
    # Script batch Windows
    batch_content = """@echo off
title F1 25 Race Engineer
echo.
echo ========================================
echo   F1 25 RACE ENGINEER
echo ========================================
echo.
echo Demarrage de l'application...
echo.
python f1_analyzer.py
pause
"""
    
    batch_file = Path("Lancer F1 Race Engineer.bat")
    with open(batch_file, 'w', encoding='utf-8') as f:
        f.write(batch_content)
    
    print(f"✅ Créé: {batch_file}")
    
    # Script PowerShell
    ps_content = """Write-Host ""
Write-Host "========================================"
Write-Host "  F1 25 RACE ENGINEER"
Write-Host "========================================"
Write-Host ""
Write-Host "Demarrage de l'application..." -ForegroundColor Green
Write-Host ""
python f1_analyzer.py
Read-Host -Prompt "Appuyez sur Entree pour fermer"
"""
    
    ps_file = Path("Lancer F1 Race Engineer.ps1")
    with open(ps_file, 'w', encoding='utf-8') as f:
        f.write(ps_content)
    
    print(f"✅ Créé: {ps_file}")
    
    return True

def create_desktop_shortcut():
    """Tente de créer un raccourci sur le bureau"""
    print_step(3, "Création du raccourci bureau (optionnel)")
    
    try:
        import win32com.client
        
        desktop = Path.home() / "Desktop"
        shortcut_path = desktop / "F1 25 Race Engineer.lnk"
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        
        current_dir = Path.cwd()
        bat_file = current_dir / "Lancer F1 Race Engineer.bat"
        
        shortcut.Targetpath = str(bat_file)
        shortcut.WorkingDirectory = str(current_dir)
        shortcut.IconLocation = "shell32.dll,13"  # Icône de voiture
        shortcut.Description = "F1 25 Race Engineer - Ingénieur IA"
        shortcut.save()
        
        print(f"✅ Raccourci créé sur le bureau: {shortcut_path}")
        return True
        
    except Exception as e:
        print(f"⚠️ Impossible de créer le raccourci bureau: {e}")
        print("   Ce n'est pas grave, utilisez le fichier .bat à la place")
        return False

def install_french_voice():
    """Guide pour installer une voix française"""
    print_step(4, "Installation de la voix française (optionnel)")
    
    print("""
Pour avoir une voix française naturelle, installez Hortense:

1. Ouvrez: Paramètres Windows → Heure et langue
2. Cliquez sur: Langue et région
3. Ajoutez: Français (France)
4. Cliquez sur les 3 points → Options linguistiques
5. Téléchargez: Synthèse vocale (Hortense)

Ou tapez simplement dans la recherche Windows: "Voix"

L'application détectera automatiquement la voix française!
""")
    
    response = input("Voulez-vous ouvrir les paramètres de langue maintenant? (o/n): ").lower()
    
    if response == 'o':
        try:
            subprocess.run('start ms-settings:regionlanguage', shell=True)
            print("✅ Paramètres ouverts!")
        except:
            print("⚠️ Impossible d'ouvrir automatiquement")
    
    return True

def create_readme():
    """Crée un fichier README avec les instructions"""
    print_step(5, "Création du guide d'utilisation")
    
    readme_content = """# 🏎️ F1 25 RACE ENGINEER

## 🚀 Lancement rapide

**Double-cliquez sur:** `Lancer F1 Race Engineer.bat`

Ou utilisez le raccourci sur votre bureau.

---

## ⚙️ Configuration F1 25

1. Lancez F1 25
2. Allez dans: **Options → Paramètres → Télémétrie**
3. Activez: **UDP Telemetry ON**
4. Port: **20777**

---

## 🔑 Configuration des clés API

1. Lancez l'application
2. Cliquez sur: **⚙️ Config API**
3. Ajoutez au moins une clé (recommandé: Mistral - gratuit)

### Obtenir les clés gratuites:

**Mistral AI (GRATUIT - Recommandé):**
- https://console.mistral.ai/
- Créez un compte → API Keys

**NVIDIA Nemotron (GRATUIT):**
- https://build.nvidia.com/nvidia/llama-3_1-nemotron-70b-instruct

---

## 🎤 Commandes vocales

1. Cliquez sur: **🎤 Voice: OFF** pour activer
2. Dites: **"Bono"** + votre question

**Exemples:**
- "Bono, état des pneus"
- "Bono, quelle position"
- "Bono, stratégie"
- "Bono, aide"

---

## 🔊 Problème de son?

Si vous n'entendez pas Bono:

1. **Vérifiez le mixeur Windows:** Clic droit sur volume → Ouvrir le mélangeur
2. **Montez le volume de l'app à 100%**
3. **Vérifiez vos haut-parleurs**

---

## 📋 Modes supportés

✅ Course en ligne
✅ Contre-la-montre
✅ Mode carrière
✅ Essais libres

---

## ❓ Besoin d'aide?

Lancez l'application et tapez "Bono, aide" pour la liste des commandes.

---

**Bon pilotage! 🏁**
"""
    
    readme_file = Path("README.md")
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"✅ Guide créé: {readme_file}")
    return True

def main():
    """Programme principal d'installation"""
    print_header("🏎️ F1 25 RACE ENGINEER - INSTALLATION AUTOMATIQUE")
    
    print("Ce script va installer tout ce qui est nécessaire pour")
    print("faire fonctionner F1 25 Race Engineer.")
    print("\nCela peut prendre quelques minutes...")
    
    input("\nAppuyez sur Entrée pour commencer l'installation...")
    
    # Vérification de Python
    print_header("Vérification du système")
    if not check_python_version():
        input("\nAppuyez sur Entrée pour quitter...")
        sys.exit(1)
    
    # Installation des dépendances
    print_header("Installation des dépendances")
    if not install_dependencies():
        print("\n⚠️ Certaines dépendances n'ont pas pu être installées")
        print("L'application fonctionnera mais certaines fonctionnalités pourraient manquer")
        response = input("\nContinuer quand même? (o/n): ").lower()
        if response != 'o':
            sys.exit(1)
    
    # Création des lanceurs
    print_header("Configuration des lanceurs")
    create_launcher_scripts()
    create_desktop_shortcut()
    
    # Voix française
    print_header("Voix française")
    install_french_voice()
    
    # Guide d'utilisation
    print_header("Documentation")
    create_readme()
    
    # Fin
    print_header("✅ INSTALLATION TERMINÉE!")
    
    print("""
🎉 Tout est prêt!

📋 Prochaines étapes:

1. Lancez F1 25 et activez la télémétrie UDP (Port 20777)

2. Double-cliquez sur: "Lancer F1 Race Engineer.bat"
   (ou utilisez le raccourci sur votre bureau)

3. Configurez une clé API gratuite dans l'application

4. Amusez-vous bien! 🏁

💡 Consultez README.md pour plus d'informations
""")
    
    response = input("\nVoulez-vous lancer l'application maintenant? (o/n): ").lower()
    
    if response == 'o':
        print("\n🚀 Lancement de l'application...")
        try:
            subprocess.Popen(['python', 'f1_analyzer.py'])
        except Exception as e:
            print(f"❌ Erreur au lancement: {e}")
            print("Utilisez le fichier .bat à la place")
    
    input("\nAppuyez sur Entrée pour fermer...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Installation annulée par l'utilisateur")
        input("Appuyez sur Entrée pour quitter...")
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        input("\nAppuyez sur Entrée pour quitter...")
