"""
Script de test pour diagnostiquer les problèmes de TTS et microphone
"""
import sys

print("="*60)
print("TEST 1: Vérification des bibliothèques installées")
print("="*60)

# Test 1: Import des bibliothèques
try:
    import pyttsx3
    print("✅ pyttsx3 installé")
except ImportError:
    print("❌ pyttsx3 manquant - Installez: pip install pyttsx3")
    sys.exit(1)

try:
    import speech_recognition as sr
    print("✅ speech_recognition installé")
except ImportError:
    print("❌ speech_recognition manquant - Installez: pip install SpeechRecognition")

try:
    import pyaudio
    print("✅ pyaudio installé")
except ImportError:
    print("❌ pyaudio manquant - Installez: pip install pyaudio")

print("\n" + "="*60)
print("TEST 2: Test du moteur de synthèse vocale (TTS)")
print("="*60)

try:
    engine = pyttsx3.init()
    print("✅ Moteur TTS initialisé")
    
    # Afficher les voix disponibles
    voices = engine.getProperty('voices')
    print(f"\n📢 Voix disponibles: {len(voices)}")
    for i, voice in enumerate(voices):
        print(f"  {i}: {voice.name} ({voice.id})")
    
    # Test de volume
    volume = engine.getProperty('volume')
    print(f"\n🔊 Volume actuel: {volume}")
    
    # Test de vitesse
    rate = engine.getProperty('rate')
    print(f"⚡ Vitesse actuelle: {rate}")
    
    # Configuration optimale
    engine.setProperty('volume', 1.0)
    engine.setProperty('rate', 150)
    
    print("\n🎤 Test vocal en cours...")
    print("Vous devriez entendre: 'Bonjour, je suis Bono, ton ingénieur de course'")
    
    engine.say("Bonjour, je suis Bono, ton ingénieur de course")
    engine.runAndWait()
    
    print("✅ Test vocal terminé")
    
    # Demander à l'utilisateur
    response = input("\n❓ Avez-vous entendu le message? (o/n): ").lower()
    
    if response == 'o':
        print("✅ Le TTS fonctionne!")
    else:
        print("❌ Problème de TTS détecté")
        print("\n💡 Solutions possibles:")
        print("  1. Vérifiez que vos haut-parleurs sont allumés")
        print("  2. Vérifiez le volume Windows")
        print("  3. Essayez de changer la voix dans le script principal")
        print("  4. Sur Windows: Paramètres → Système → Son → Sortie")

except Exception as e:
    print(f"❌ Erreur TTS: {e}")
    print("\n💡 Solutions:")
    print("  - Réinstallez: pip uninstall pyttsx3 && pip install pyttsx3")
    print("  - Windows: Vérifiez que SAPI5 est installé")

print("\n" + "="*60)
print("TEST 3: Test du microphone")
print("="*60)

try:
    import speech_recognition as sr
    import pyaudio
    
    recognizer = sr.Recognizer()
    
    # Lister les micros disponibles
    print("\n🎤 Microphones disponibles:")
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        print(f"  {index}: {name}")
    
    # Test d'enregistrement
    print("\n📝 Test d'enregistrement...")
    print("Parlez maintenant (5 secondes)...")
    
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("🎙️ Écoute en cours...")
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
        print("✅ Audio capturé")
        
        try:
            text = recognizer.recognize_google(audio, language='fr-FR')
            print(f"📝 Vous avez dit: '{text}'")
            print("✅ La reconnaissance vocale fonctionne!")
        except sr.UnknownValueError:
            print("⚠️ Je n'ai pas compris ce que vous avez dit")
            print("💡 Parlez plus fort et plus clairement")
        except sr.RequestError as e:
            print(f"❌ Erreur service Google: {e}")
            print("💡 Vérifiez votre connexion internet")

except ImportError as e:
    print(f"❌ Bibliothèque manquante: {e}")
    print("💡 Installez: pip install SpeechRecognition pyaudio")
except Exception as e:
    print(f"❌ Erreur microphone: {e}")
    print("\n💡 Solutions:")
    print("  1. Vérifiez qu'un micro est branché")
    print("  2. Windows: Paramètres → Confidentialité → Microphone → Activé")
    print("  3. Autorisez Python à accéder au microphone")

print("\n" + "="*60)
print("TEST 4: Test complet 'Hey Bono'")
print("="*60)

try:
    import speech_recognition as sr
    
    recognizer = sr.Recognizer()
    
    print("\n🎤 Dites 'Hey Bono' suivi de votre question...")
    print("(Exemple: 'Hey Bono état des pneus')")
    print("\nÉcoute en cours (10 secondes)...")
    
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        audio = recognizer.listen(source, timeout=10, phrase_time_limit=8)
        
        try:
            text = recognizer.recognize_google(audio, language='fr-FR').lower()
            print(f"\n📝 Vous avez dit: '{text}'")
            
            if 'hey bono' in text or 'bono' in text:
                print("✅ 'Hey Bono' détecté!")
                command = text.split('bono', 1)[1].strip() if 'bono' in text else text
                print(f"📋 Commande extraite: '{command}'")
            else:
                print("⚠️ 'Hey Bono' non détecté dans votre phrase")
                print("💡 Assurez-vous de bien dire 'Hey Bono'")
                
        except sr.UnknownValueError:
            print("❌ Rien compris - Parlez plus fort")
        except sr.RequestError as e:
            print(f"❌ Erreur: {e}")
            
except Exception as e:
    print(f"❌ Erreur: {e}")

print("\n" + "="*60)
print("RÉSUMÉ DES TESTS")
print("="*60)
print("\nSi tous les tests sont ✅, l'application devrait fonctionner.")
print("\nSinon, suivez les solutions proposées pour chaque erreur ❌")
print("\n💡 Conseil: Exécutez ce script avant de lancer l'application principale")
print("="*60)
