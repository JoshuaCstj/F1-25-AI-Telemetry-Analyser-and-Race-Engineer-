import socket
import struct
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict
import threading
import requests
import pyttsx3
import queue
import speech_recognition as sr

# =============================================================================
# CONFIGURATION
# =============================================================================

import os

class Config:
    """Configuration pour l'application"""
    UDP_IP = "127.0.0.1"
    UDP_PORT = 20777
    
    # Fichier de configuration pour sauvegarder les clés
    CONFIG_FILE = "f1_analyzer_config.json"
    
    # Clés API (chargées depuis le fichier)
    CLAUDE_API_KEY = ""
    OPENAI_API_KEY = ""
    GEMINI_API_KEY = ""
    NVIDIA_API_KEY = ""  # Nemotron (gratuit)
    MISTRAL_API_KEY = ""  # Mistral (gratuit)
    
    # Configuration de l'ingénieur vocal
    ENGINEER_ENABLED = True
    ENGINEER_VOICE_RATE = 180  # Vitesse de parole
    ENGINEER_AUTO_ADVICE = True  # Conseils automatiques
    ENGINEER_ADVICE_INTERVAL = 30  # Secondes entre les conseils auto
    
    # Configuration reconnaissance vocale
    VOICE_COMMAND_ENABLED = True
    WAKE_WORD = "bono"  # Mot d'activation simplifié (pas "hey")
    VOICE_LANGUAGE = "fr-FR"  # Langue pour la reconnaissance
    WAKE_WORD_ALTERNATIVES = ["bono", "bonno", "bruno", "chrono"]  # Variantes acceptées
    
    @classmethod
    def load_config(cls):
        """Charge la configuration depuis le fichier"""
        if os.path.exists(cls.CONFIG_FILE):
            try:
                with open(cls.CONFIG_FILE, 'r') as f:
                    config_data = json.load(f)
                    cls.CLAUDE_API_KEY = config_data.get('claude_api_key', '')
                    cls.OPENAI_API_KEY = config_data.get('openai_api_key', '')
                    cls.GEMINI_API_KEY = config_data.get('gemini_api_key', '')
                    cls.NVIDIA_API_KEY = config_data.get('nvidia_api_key', '')
                    cls.MISTRAL_API_KEY = config_data.get('mistral_api_key', '')
                    cls.ENGINEER_VOICE_RATE = config_data.get('voice_rate', 180)
                    cls.ENGINEER_AUTO_ADVICE = config_data.get('auto_advice', True)
                    cls.ENGINEER_ADVICE_INTERVAL = config_data.get('advice_interval', 30)
                    cls.VOICE_COMMAND_ENABLED = config_data.get('voice_enabled', True)
                    cls.WAKE_WORD = config_data.get('wake_word', 'bono')
                    cls.VOICE_LANGUAGE = config_data.get('voice_language', 'fr-FR')
            except Exception as e:
                print(f"Erreur chargement config: {e}")
    
    @classmethod
    def save_config(cls):
        """Sauvegarde la configuration dans le fichier"""
        try:
            config_data = {
                'claude_api_key': cls.CLAUDE_API_KEY,
                'openai_api_key': cls.OPENAI_API_KEY,
                'gemini_api_key': cls.GEMINI_API_KEY,
                'nvidia_api_key': cls.NVIDIA_API_KEY,
                'mistral_api_key': cls.MISTRAL_API_KEY,
                'voice_rate': cls.ENGINEER_VOICE_RATE,
                'auto_advice': cls.ENGINEER_AUTO_ADVICE,
                'advice_interval': cls.ENGINEER_ADVICE_INTERVAL,
                'voice_enabled': cls.VOICE_COMMAND_ENABLED,
                'wake_word': cls.WAKE_WORD,
                'voice_language': cls.VOICE_LANGUAGE
            }
            with open(cls.CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=2)
            return True
        except Exception as e:
            print(f"Erreur sauvegarde config: {e}")
            return False

# =============================================================================
# STRUCTURES DE DONNÉES F1 25
# =============================================================================

@dataclass
class PacketHeader:
    """En-tête commun à tous les paquets F1 25"""
    packet_format: int
    game_year: int
    game_major_version: int
    game_minor_version: int
    packet_version: int
    packet_id: int
    session_uid: int
    session_time: float
    frame_identifier: int
    overall_frame_identifier: int
    player_car_index: int
    secondary_player_car_index: int

@dataclass
class CarTelemetryData:
    """Données de télémétrie pour une voiture"""
    speed: int
    throttle: float
    steer: float
    brake: float
    clutch: int
    gear: int
    engine_rpm: int
    drs: int
    rev_lights_percent: int
    rev_lights_bit_value: int
    brakes_temperature: List[int]
    tyres_surface_temperature: List[int]
    tyres_inner_temperature: List[int]
    engine_temperature: int
    tyres_pressure: List[float]
    surface_type: List[int]

@dataclass
class LapData:
    """Données de tour"""
    last_lap_time_in_ms: int
    current_lap_time_in_ms: int
    sector1_time_in_ms: int
    sector1_time_minutes: int
    sector2_time_in_ms: int
    sector2_time_minutes: int
    delta_to_car_in_front_in_ms: int
    delta_to_race_leader_in_ms: int
    lap_distance: float
    total_distance: float
    safety_car_delta: float
    car_position: int
    current_lap_num: int
    pit_status: int
    num_pit_stops: int
    sector: int
    current_lap_invalid: int
    penalties: int
    total_warnings: int
    corner_cutting_warnings: int
    num_unserved_drive_through_pens: int
    num_unserved_stop_go_pens: int
    grid_position: int
    driver_status: int
    result_status: int
    pit_lane_timer_active: int
    pit_lane_time_in_lane_in_ms: int
    pit_stop_timer_in_ms: int
    pit_stop_should_serve_pen: int

@dataclass
class CarMotionData:
    """Données de mouvement"""
    world_position_x: float
    world_position_y: float
    world_position_z: float
    world_velocity_x: float
    world_velocity_y: float
    world_velocity_z: float
    world_forward_dir_x: int
    world_forward_dir_y: int
    world_forward_dir_z: int
    world_right_dir_x: int
    world_right_dir_y: int
    world_right_dir_z: int
    g_force_lateral: float
    g_force_longitudinal: float
    g_force_vertical: float
    yaw: float
    pitch: float
    roll: float

# =============================================================================
# DÉCODEUR DE PAQUETS F1 25
# =============================================================================

class F1PacketDecoder:
    """Décode les paquets UDP de F1 25"""
    
    # IDs des différents types de paquets
    PACKET_MOTION = 0
    PACKET_SESSION = 1
    PACKET_LAP_DATA = 2
    PACKET_EVENT = 3
    PACKET_PARTICIPANTS = 4
    PACKET_CAR_SETUPS = 5
    PACKET_CAR_TELEMETRY = 6
    PACKET_CAR_STATUS = 7
    PACKET_FINAL_CLASSIFICATION = 8
    PACKET_LOBBY_INFO = 9
    PACKET_CAR_DAMAGE = 10
    PACKET_SESSION_HISTORY = 11
    PACKET_TYRE_SETS = 12
    PACKET_MOTION_EX = 13
    
    @staticmethod
    def decode_header(data):
        """Décode l'en-tête du paquet (29 octets)"""
        try:
            header_format = '<HBBBBBQfIIBB'
            header_size = struct.calcsize(header_format)
            
            if len(data) < header_size:
                return None
            
            unpacked = struct.unpack(header_format, data[:header_size])
            
            return PacketHeader(
                packet_format=unpacked[0],
                game_year=unpacked[1],
                game_major_version=unpacked[2],
                game_minor_version=unpacked[3],
                packet_version=unpacked[4],
                packet_id=unpacked[5],
                session_uid=unpacked[6],
                session_time=unpacked[7],
                frame_identifier=unpacked[8],
                overall_frame_identifier=unpacked[9],
                player_car_index=unpacked[10],
                secondary_player_car_index=unpacked[11]
            )
        except Exception as e:
            return None
    
    @staticmethod
    def decode_car_telemetry(data, header):
        """Décode le paquet de télémétrie (packet ID 6)"""
        try:
            offset = 29  # Taille de l'en-tête
            telemetry_list = []
            
            # Format pour une voiture (60 octets par voiture)
            car_format = '<HfffBbHBBH4H4B4BH4f8B'
            car_size = struct.calcsize(car_format)
            
            # Il y a 22 voitures maximum
            for i in range(22):
                if offset + car_size > len(data):
                    break
                
                car_data = struct.unpack(car_format, data[offset:offset + car_size])
                
                telemetry = CarTelemetryData(
                    speed=car_data[0],
                    throttle=car_data[1],
                    steer=car_data[2],
                    brake=car_data[3],
                    clutch=car_data[4],
                    gear=car_data[5],
                    engine_rpm=car_data[6],
                    drs=car_data[7],
                    rev_lights_percent=car_data[8],
                    rev_lights_bit_value=car_data[9],
                    brakes_temperature=list(car_data[10:14]),
                    tyres_surface_temperature=list(car_data[14:18]),
                    tyres_inner_temperature=list(car_data[18:22]),
                    engine_temperature=car_data[22],
                    tyres_pressure=list(car_data[23:27]),
                    surface_type=list(car_data[27:35])
                )
                
                telemetry_list.append(telemetry)
                offset += car_size
            
            return telemetry_list
        
        except Exception as e:
            return None
    
    @staticmethod
    def decode_lap_data(data, header):
        """Décode le paquet de données de tour (packet ID 2)"""
        try:
            offset = 29  # Taille de l'en-tête
            lap_data_list = []
            
            # Format pour une voiture (54 octets par voiture)
            lap_format = '<IIHBHBHBfffBBBBBBBBBBBBBBHH'
            lap_size = struct.calcsize(lap_format)
            
            for i in range(22):
                if offset + lap_size > len(data):
                    break
                
                lap_unpacked = struct.unpack(lap_format, data[offset:offset + lap_size])
                
                lap = LapData(
                    last_lap_time_in_ms=lap_unpacked[0],
                    current_lap_time_in_ms=lap_unpacked[1],
                    sector1_time_in_ms=lap_unpacked[2],
                    sector1_time_minutes=lap_unpacked[3],
                    sector2_time_in_ms=lap_unpacked[4],
                    sector2_time_minutes=lap_unpacked[5],
                    delta_to_car_in_front_in_ms=lap_unpacked[6],
                    delta_to_race_leader_in_ms=lap_unpacked[7],
                    lap_distance=lap_unpacked[8],
                    total_distance=lap_unpacked[9],
                    safety_car_delta=lap_unpacked[10],
                    car_position=lap_unpacked[11],
                    current_lap_num=lap_unpacked[12],
                    pit_status=lap_unpacked[13],
                    num_pit_stops=lap_unpacked[14],
                    sector=lap_unpacked[15],
                    current_lap_invalid=lap_unpacked[16],
                    penalties=lap_unpacked[17],
                    total_warnings=lap_unpacked[18],
                    corner_cutting_warnings=lap_unpacked[19],
                    num_unserved_drive_through_pens=lap_unpacked[20],
                    num_unserved_stop_go_pens=lap_unpacked[21],
                    grid_position=lap_unpacked[22],
                    driver_status=lap_unpacked[23],
                    result_status=lap_unpacked[24],
                    pit_lane_timer_active=lap_unpacked[25],
                    pit_lane_time_in_lane_in_ms=lap_unpacked[26],
                    pit_stop_timer_in_ms=lap_unpacked[27],
                    pit_stop_should_serve_pen=lap_unpacked[28]
                )
                
                lap_data_list.append(lap)
                offset += lap_size
            
            return lap_data_list
        
        except Exception as e:
            return None
    
    @staticmethod
    def decode_motion_data(data, header):
        """Décode le paquet de mouvement (packet ID 0)"""
        try:
            offset = 29
            motion_list = []
            
            # Format pour une voiture (60 octets)
            motion_format = '<ffffffhhhhhhffffff'
            motion_size = struct.calcsize(motion_format)
            
            for i in range(22):
                if offset + motion_size > len(data):
                    break
                
                motion_unpacked = struct.unpack(motion_format, data[offset:offset + motion_size])
                
                motion = CarMotionData(
                    world_position_x=motion_unpacked[0],
                    world_position_y=motion_unpacked[1],
                    world_position_z=motion_unpacked[2],
                    world_velocity_x=motion_unpacked[3],
                    world_velocity_y=motion_unpacked[4],
                    world_velocity_z=motion_unpacked[5],
                    world_forward_dir_x=motion_unpacked[6],
                    world_forward_dir_y=motion_unpacked[7],
                    world_forward_dir_z=motion_unpacked[8],
                    world_right_dir_x=motion_unpacked[9],
                    world_right_dir_y=motion_unpacked[10],
                    world_right_dir_z=motion_unpacked[11],
                    g_force_lateral=motion_unpacked[12],
                    g_force_longitudinal=motion_unpacked[13],
                    g_force_vertical=motion_unpacked[14],
                    yaw=motion_unpacked[15],
                    pitch=motion_unpacked[16],
                    roll=motion_unpacked[17]
                )
                
                motion_list.append(motion)
                offset += motion_size
            
            return motion_list
        
        except Exception as e:
            return None

# =============================================================================
# RECONNAISSANCE VOCALE
# =============================================================================

class VoiceCommandSystem:
    """Système de commande vocale 'Hey Bono'"""
    
    def __init__(self, race_engineer, telemetry_manager):
        self.race_engineer = race_engineer
        self.telemetry_manager = telemetry_manager
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.listening = False
        self.enabled = Config.VOICE_COMMAND_ENABLED
        
        # Initialiser le micro
        try:
            self.microphone = sr.Microphone()
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        except Exception as e:
            print(f"Erreur initialisation micro: {e}")
        
        # Thread d'écoute
        self.listen_thread = None
    
    def start_listening(self):
        """Démarre l'écoute des commandes vocales"""
        if not self.microphone or not self.enabled:
            return False
        
        self.listening = True
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        return True
    
    def stop_listening(self):
        """Arrête l'écoute"""
        self.listening = False
    
    def _listen_loop(self):
        """Boucle d'écoute continue"""
        while self.listening:
            try:
                with self.microphone as source:
                    # Écoute en arrière-plan
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                    
                    try:
                        # Reconnaissance vocale
                        text = self.recognizer.recognize_google(audio, language=Config.VOICE_LANGUAGE).lower()
                        
                        print(f"🎤 Entendu: '{text}'")  # Debug
                        
                        # Détection du mot d'activation (avec variantes)
                        wake_word_detected = False
                        detected_word = None
                        
                        # Vérifier le mot principal et les alternatives
                        all_wake_words = [Config.WAKE_WORD] + Config.WAKE_WORD_ALTERNATIVES
                        
                        for wake_word in all_wake_words:
                            if wake_word in text:
                                wake_word_detected = True
                                detected_word = wake_word
                                break
                        
                        if wake_word_detected:
                            print(f"✅ Mot d'activation détecté: '{detected_word}'")
                            # Extraire la commande après le mot d'activation
                            command = text.split(detected_word, 1)[1].strip()
                            if command:
                                print(f"📋 Commande: '{command}'")
                                self._process_command(command)
                            else:
                                print("⚠️ Pas de commande après le mot d'activation")
                    
                    except sr.UnknownValueError:
                        pass  # Rien compris
                    except sr.RequestError as e:
                        print(f"Erreur service reconnaissance: {e}")
            
            except sr.WaitTimeoutError:
                pass  # Timeout normal
            except Exception as e:
                pass
    
    def _process_command(self, command):
        """Traite une commande vocale avec IA pour compréhension avancée"""
        
        # Si l'IA est disponible, utiliser l'IA pour interpréter la commande
        if self.race_engineer.analyzer and self.race_engineer.analyzer.api_key:
            response = self._process_with_ai(command)
        else:
            # Fallback sur le système de mots-clés basique
            response = self._process_basic_command(command)
        
        if response:
            self.race_engineer.speak(response, priority=True)
            return response
        
        return None
    
    def _process_with_ai(self, command):
        """Traite la commande avec l'IA pour une compréhension naturelle"""
        try:
            # Collecter les données actuelles
            telemetry_data = self._get_current_data_summary()
            
            # Créer le prompt pour l'IA
            prompt = f"""Tu es Bono, l'ingénieur de course F1. Le pilote vient de te demander:
"{command}"

Voici les données actuelles de la voiture:
{json.dumps(telemetry_data, indent=2)}

INSTRUCTIONS CRITIQUES:
1. Réponds UNIQUEMENT en français, de manière très concise (2-4 phrases maximum)
2. Sois direct et professionnel comme un vrai ingénieur de course à la radio
3. Utilise les données fournies pour répondre précisément
4. Si la question n'est pas liée aux données disponibles, dis-le simplement
5. Ne mentionne JAMAIS que tu es une IA ou un assistant
6. Parle comme si tu étais vraiment dans le garage, en radio avec le pilote
7. Utilise "on" pour parler de l'équipe (ex: "on va pitter", "on surveille")
8. Sois encourageant mais factuel

Réponds maintenant à la question du pilote:"""

            # Appeler l'IA
            if isinstance(self.race_engineer.analyzer, ClaudeAnalyzer):
                headers = {
                    "Content-Type": "application/json",
                    "x-api-key": self.race_engineer.analyzer.api_key,
                    "anthropic-version": "2023-06-01"
                }
                
                data = {
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}]
                }
                
                response = requests.post(
                    self.race_engineer.analyzer.endpoint,
                    headers=headers,
                    json=data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result['content'][0]['text'].strip()
            
            elif isinstance(self.race_engineer.analyzer, OpenAIAnalyzer):
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.race_engineer.analyzer.api_key}"
                }
                
                data = {
                    "model": "gpt-4o-mini",  # Modèle accessible
                    "messages": [
                        {"role": "system", "content": "Tu es Bono, ingénieur de course F1. Réponds de manière très concise (2-4 phrases max)."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 300,
                    "temperature": 0.7
                }
                
                response = requests.post(
                    self.race_engineer.analyzer.endpoint,
                    headers=headers,
                    json=data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result['choices'][0]['message']['content'].strip()
            
            elif isinstance(self.race_engineer.analyzer, GeminiAnalyzer):
                headers = {"Content-Type": "application/json"}
                
                data = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }]
                }
                
                response = requests.post(
                    self.race_engineer.analyzer.endpoint,
                    headers=headers,
                    json=data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        except Exception as e:
            print(f"Erreur IA: {e}")
            # Fallback sur commandes basiques
            return self._process_basic_command(command)
        
        return self._process_basic_command(command)
    
    def _get_current_data_summary(self):
        """Récupère un résumé des données actuelles"""
        data = {
            "message": "Données disponibles"
        }
        
        if self.telemetry_manager.current_telemetry:
            tel = self.telemetry_manager.current_telemetry
            data["telemetrie"] = {
                "vitesse_kmh": tel.speed,
                "rapport": tel.gear,
                "rpm": tel.engine_rpm,
                "gaz_pourcentage": round(tel.throttle * 100, 1),
                "frein_pourcentage": round(tel.brake * 100, 1),
                "drs_actif": tel.drs == 1,
                "temperature_pneus": {
                    "avant_gauche": tel.tyres_surface_temperature[0],
                    "avant_droit": tel.tyres_surface_temperature[1],
                    "arriere_gauche": tel.tyres_surface_temperature[2],
                    "arriere_droit": tel.tyres_surface_temperature[3],
                    "moyenne": round(sum(tel.tyres_surface_temperature) / 4, 1)
                },
                "temperature_freins": {
                    "avant_gauche": tel.brakes_temperature[0],
                    "avant_droit": tel.brakes_temperature[1],
                    "arriere_gauche": tel.brakes_temperature[2],
                    "arriere_droit": tel.brakes_temperature[3],
                    "moyenne": round(sum(tel.brakes_temperature) / 4, 1)
                },
                "pression_pneus": {
                    "avant_gauche": round(tel.tyres_pressure[0], 2),
                    "avant_droit": round(tel.tyres_pressure[1], 2),
                    "arriere_gauche": round(tel.tyres_pressure[2], 2),
                    "arriere_droit": round(tel.tyres_pressure[3], 2)
                },
                "temperature_moteur": tel.engine_temperature
            }
        
        if self.telemetry_manager.current_lap:
            lap = self.telemetry_manager.current_lap
            data["tour"] = {
                "numero_tour": lap.current_lap_num,
                "position": lap.car_position,
                "secteur": lap.sector,
                "distance_tour_metres": round(lap.lap_distance, 1),
                "temps_tour_actuel": self.telemetry_manager._format_time(lap.current_lap_time_in_ms),
                "temps_dernier_tour": self.telemetry_manager._format_time(lap.last_lap_time_in_ms),
                "ecart_voiture_devant_secondes": round(lap.delta_to_car_in_front_in_ms / 1000, 2),
                "ecart_leader_secondes": round(lap.delta_to_race_leader_in_ms / 1000, 2),
                "nombre_arrets": lap.num_pit_stops,
                "penalites": lap.penalties,
                "avertissements": lap.total_warnings
            }
        
        if self.telemetry_manager.current_motion:
            motion = self.telemetry_manager.current_motion
            data["forces_g"] = {
                "lateral": round(motion.g_force_lateral, 2),
                "longitudinal": round(motion.g_force_longitudinal, 2),
                "vertical": round(motion.g_force_vertical, 2)
            }
        
        return data
    
    def _process_basic_command(self, command):
        """Traitement basique par mots-clés (fallback)"""
        response = None
        
        # Commandes disponibles (mode basique)
        if any(word in command for word in ["pneu", "pneus", "température pneus", "gomme", "gommes", "rubber", "état des pneu", "état des pne"]):
            response = self._get_tyre_info()
        
        elif any(word in command for word in ["frein", "freins", "température freins", "brake", "état des frein"]):
            response = self._get_brake_info()
        
        elif any(word in command for word in ["vitesse", "quelle vitesse", "rapide", "speed", "vite"]):
            response = self._get_speed_info()
        
        elif any(word in command for word in ["position", "quelle position", "classement", "place", "où", "je suis où"]):
            response = self._get_position_info()
        
        elif any(word in command for word in ["temps", "temps au tour", "chrono", "time", "dernier tour"]):
            response = self._get_lap_time_info()
        
        elif any(word in command for word in ["stratégie", "pit", "arrêt", "quand pitter", "strategy", "boxer", "box"]):
            response = self._get_strategy_info()
        
        elif any(word in command for word in ["écart", "delta", "avance", "retard", "gap", "derrière", "devant"]):
            response = self._get_gap_info()
        
        elif any(word in command for word in ["carburant", "essence", "fuel", "autonomie"]):
            response = self._get_fuel_info()
        
        elif any(word in command for word in ["conseil", "aide", "que faire", "help", "advice"]):
            response = self._get_general_advice()
        
        elif any(word in command for word in ["drs", "aileron"]):
            response = self._get_drs_info()
        
        elif any(word in command for word in ["moteur", "engine", "température moteur"]):
            response = self._get_engine_info()
        
        elif any(word in command for word in ["météo", "pluie", "weather", "conditions"]):
            response = self._get_weather_info()
        
        elif any(word in command for word in ["pression", "psi", "bar"]):
            response = self._get_pressure_info()
        
        elif any(word in command for word in ["usure", "dégradation", "wear"]):
            response = self._get_wear_info()
        
        elif any(word in command for word in ["concurrent", "adversaire", "rival", "compétition"]):
            response = self._get_competition_info()
        
        # Questions générales sur l'état
        elif any(word in command for word in ["état", "comment va", "tout va bien", "status", "check"]):
            response = self._get_overall_status()
        
        # Liste des commandes
        elif any(word in command for word in ["commande", "liste", "help", "aide"]):
            response = self._get_commands_list()
        
        else:
            response = "Désolé, je n'ai pas compris. Dis 'Bono aide' pour la liste des commandes, ou pose une question plus précise comme 'état des pneus' ou 'quelle position'."
        
        return response
    
    def _get_tyre_info(self):
        """Info sur les pneus"""
        if not self.telemetry_manager.current_telemetry:
            return "Pas de données disponibles."
        
        temps = self.telemetry_manager.current_telemetry.tyres_surface_temperature
        avg_temp = sum(temps) / 4
        
        status = "bonne" if 80 <= avg_temp <= 100 else "attention"
        return f"Température moyenne des pneus: {avg_temp:.0f} degrés. Avant gauche {temps[0]}, avant droit {temps[1]}, arrière gauche {temps[2]}, arrière droit {temps[3]}. Température {status}."
    
    def _get_brake_info(self):
        """Info sur les freins"""
        if not self.telemetry_manager.current_telemetry:
            return "Pas de données disponibles."
        
        temps = self.telemetry_manager.current_telemetry.brakes_temperature
        avg_temp = sum(temps) / 4
        
        status = "critique" if avg_temp > 800 else "normale" if avg_temp > 400 else "froide"
        return f"Température moyenne des freins: {avg_temp:.0f} degrés. État: {status}."
    
    def _get_speed_info(self):
        """Info sur la vitesse"""
        if not self.telemetry_manager.current_telemetry:
            return "Pas de données disponibles."
        
        speed = self.telemetry_manager.current_telemetry.speed
        gear = self.telemetry_manager.current_telemetry.gear
        return f"Vitesse actuelle: {speed} kilomètres heure, vitesse {gear}."
    
    def _get_position_info(self):
        """Info sur la position"""
        if not self.telemetry_manager.current_lap:
            return "Pas de données disponibles."
        
        position = self.telemetry_manager.current_lap.car_position
        lap = self.telemetry_manager.current_lap.current_lap_num
        return f"Tu es en position {position}, tour {lap}."
    
    def _get_lap_time_info(self):
        """Info sur les temps au tour"""
        if not self.telemetry_manager.current_lap:
            return "Pas de données disponibles."
        
        current = self.telemetry_manager._format_time(self.telemetry_manager.current_lap.current_lap_time_in_ms)
        last = self.telemetry_manager._format_time(self.telemetry_manager.current_lap.last_lap_time_in_ms)
        
        if last != "N/A":
            return f"Temps actuel: {current}. Dernier tour: {last}."
        else:
            return f"Temps actuel: {current}."
    
    def _get_strategy_info(self):
        """Info stratégique"""
        if not self.telemetry_manager.current_telemetry or not self.telemetry_manager.current_lap:
            return "Pas de données disponibles."
        
        avg_tyre_temp = sum(self.telemetry_manager.current_telemetry.tyres_surface_temperature) / 4
        lap = self.telemetry_manager.current_lap.current_lap_num
        
        if avg_tyre_temp > 110:
            return f"Les pneus sont très chauds à {avg_tyre_temp:.0f} degrés. Je recommande un pit dans les 2 à 3 tours."
        elif lap > 15 and avg_tyre_temp > 100:
            return "Les pneus commencent à s'user. Surveille leur état, on pourrait pitter bientôt."
        else:
            return "Stratégie actuelle: reste en piste, les pneus sont bons."
    
    def _get_gap_info(self):
        """Info sur les écarts"""
        if not self.telemetry_manager.current_lap:
            return "Pas de données disponibles."
        
        delta_front = self.telemetry_manager.current_lap.delta_to_car_in_front_in_ms / 1000
        delta_leader = self.telemetry_manager.current_lap.delta_to_race_leader_in_ms / 1000
        
        if delta_front != 0:
            return f"Écart avec la voiture devant: {abs(delta_front):.1f} secondes. Écart avec le leader: {abs(delta_leader):.1f} secondes."
        else:
            return f"Écart avec le leader: {abs(delta_leader):.1f} secondes."
    
    def _get_fuel_info(self):
        """Info sur le carburant (simulé)"""
        if not self.telemetry_manager.current_lap:
            return "Pas de données disponibles."
        
        lap = self.telemetry_manager.current_lap.current_lap_num
        # Simulation simple
        return f"Carburant suffisant. Tu as de quoi finir la course au rythme actuel."
    
    def _get_general_advice(self):
        """Conseils généraux"""
        if not self.telemetry_manager.current_telemetry:
            return "Pas de données disponibles."
        
        advices = []
        
        avg_tyre = sum(self.telemetry_manager.current_telemetry.tyres_surface_temperature) / 4
        if avg_tyre < 70:
            advices.append("Chauffe les pneus")
        elif avg_tyre > 110:
            advices.append("Refroidis les pneus")
        
        avg_brake = sum(self.telemetry_manager.current_telemetry.brakes_temperature) / 4
        if avg_brake > 800:
            advices.append("Refroidis les freins")
        
        if advices:
            return "Conseils: " + ", ".join(advices) + "."
        else:
            return "Tout est bon, continue comme ça!"
    
    def _get_drs_info(self):
        """Info sur le DRS"""
        if not self.telemetry_manager.current_telemetry:
            return "Pas de données disponibles."
        
        drs = self.telemetry_manager.current_telemetry.drs
        if drs:
            return "DRS disponible, utilise-le!"
        else:
            return "DRS non disponible pour le moment."
    
    def _get_engine_info(self):
        """Info sur le moteur"""
        if not self.telemetry_manager.current_telemetry:
            return "Pas de données disponibles."
        
        temp = self.telemetry_manager.current_telemetry.engine_temperature
        rpm = self.telemetry_manager.current_telemetry.engine_rpm
        
        status = "critique" if temp > 120 else "normal" if temp > 90 else "optimal"
        return f"Moteur à {temp} degrés, {rpm} tours par minute. État: {status}."
    
    def _get_weather_info(self):
        """Info météo (simulé pour l'instant)"""
        return "Conditions de piste: sec. Pas de pluie prévue."
    
    def _get_pressure_info(self):
        """Info sur les pressions des pneus"""
        if not self.telemetry_manager.current_telemetry:
            return "Pas de données disponibles."
        
        pressures = self.telemetry_manager.current_telemetry.tyres_pressure
        avg = sum(pressures) / 4
        
        return f"Pression moyenne: {avg:.2f} PSI. Avant gauche {pressures[0]:.2f}, avant droit {pressures[1]:.2f}, arrière gauche {pressures[2]:.2f}, arrière droit {pressures[3]:.2f}."
    
    def _get_wear_info(self):
        """Info sur l'usure"""
        if not self.telemetry_manager.current_telemetry or not self.telemetry_manager.current_lap:
            return "Pas de données disponibles."
        
        lap = self.telemetry_manager.current_lap.current_lap_num
        temp = sum(self.telemetry_manager.current_telemetry.tyres_surface_temperature) / 4
        
        if lap < 5:
            wear = "très faible"
        elif lap < 15:
            wear = "modérée"
        elif lap < 25:
            wear = "notable"
        else:
            wear = "importante"
        
        return f"Tour {lap}, usure {wear}. Température moyenne des pneus: {temp:.0f} degrés."
    
    def _get_competition_info(self):
        """Info sur la compétition"""
        if not self.telemetry_manager.current_lap:
            return "Pas de données disponibles."
        
        position = self.telemetry_manager.current_lap.car_position
        delta_front = abs(self.telemetry_manager.current_lap.delta_to_car_in_front_in_ms / 1000)
        
        if position == 1:
            return "Tu es en tête! Gère ton avance."
        elif delta_front < 1.0:
            return f"Position {position}. La voiture devant est à moins d'une seconde. Zone d'attaque DRS possible!"
        else:
            return f"Position {position}. Continue de pousser, écart de {delta_front:.1f} secondes devant."
    
    def _get_overall_status(self):
        """État général de la voiture"""
        if not self.telemetry_manager.current_telemetry:
            return "Pas de données disponibles."
        
        tel = self.telemetry_manager.current_telemetry
        issues = []
        
        # Vérifier les pneus
        avg_tyre = sum(tel.tyres_surface_temperature) / 4
        if avg_tyre < 70:
            issues.append("Pneus froids")
        elif avg_tyre > 110:
            issues.append("Pneus chauds")
        
        # Vérifier les freins
        avg_brake = sum(tel.brakes_temperature) / 4
        if avg_brake > 800:
            issues.append("Freins très chauds")
        
        # Vérifier le moteur
        if tel.engine_temperature > 120:
            issues.append("Moteur chaud")
        
        if issues:
            return f"Attention: {', '.join(issues)}. Sinon, tout est OK."
        else:
            return f"Tout est bon! Vitesse {tel.speed} kilomètres heure, pneus à {avg_tyre:.0f} degrés, freins à {avg_brake:.0f} degrés. Continue comme ça!"
    
    def _get_commands_list(self):
        """Liste des commandes disponibles"""
        return """Commandes disponibles: état des pneus, état des freins, quelle vitesse, quelle position, temps au tour, stratégie, écart, DRS, état général, carburant, aide."""

# =============================================================================
# INGÉNIEUR DE COURSE VOCAL
# =============================================================================

class RaceEngineer:
    """Ingénieur de course qui parle et donne des conseils en temps réel"""
    
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.tts_engine = None
        self.speech_queue = queue.Queue()
        self.is_speaking = False
        self.enabled = Config.ENGINEER_ENABLED
        self.last_advice_time = datetime.now()
        self.last_advice_content = {}
        
        # FORCER l'utilisation de Windows COM (testé et fonctionne)
        self.init_windows_com()
        
        # Thread pour la parole avec COM initialisé
        self.speech_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.speech_thread.start()
    
    def init_windows_com(self):
        """Initialise Windows SAPI via COM (méthode garantie)"""
        try:
            import win32com.client
            import pythoncom
            
            # Initialiser COM pour le thread principal
            pythoncom.CoInitialize()
            
            self.tts_engine = win32com.client.Dispatch("SAPI.SpVoice")
            
            # Lister toutes les voix disponibles
            voices = self.tts_engine.GetVoices()
            print(f"\n🎤 Voix disponibles ({voices.Count}):")
            
            french_voice = None
            best_voice = None
            
            for i in range(voices.Count):
                voice = voices.Item(i)
                voice_name = voice.GetDescription()
                print(f"  {i}: {voice_name}")
                
                # Chercher une voix française
                if 'french' in voice_name.lower() or 'français' in voice_name.lower() or 'hortense' in voice_name.lower() or 'julie' in voice_name.lower():
                    french_voice = voice
                    print(f"    ✅ Voix française détectée!")
                
                # Chercher des voix plus naturelles (Microsoft David/Zira Desktop sont meilleures que Mobile)
                if 'desktop' in voice_name.lower() and not french_voice:
                    best_voice = voice
            
            # Sélectionner la meilleure voix
            if french_voice:
                self.tts_engine.Voice = french_voice
                print(f"✅ Voix française sélectionnée: {french_voice.GetDescription()}")
            elif best_voice:
                self.tts_engine.Voice = best_voice
                print(f"✅ Meilleure voix anglaise sélectionnée: {best_voice.GetDescription()}")
            else:
                print("⚠️ Utilisation de la voix par défaut")
            
            # Configuration optimale pour une voix naturelle
            self.tts_engine.Volume = 100  # Volume maximum
            self.tts_engine.Rate = 0  # Vitesse normale (entre -10 et 10, 0 = normal)
            
            print(f"🔊 Volume: 100 | Vitesse: {self.tts_engine.Rate}")
            
            # Test avec la nouvelle voix
            test_message = "Ingénieur de course prêt. Bonjour pilote!"
            self.tts_engine.Speak(test_message)
            print("✅ Test audio réussi avec la nouvelle voix!")
            
        except Exception as e:
            print(f"❌ Erreur initialisation Windows COM: {e}")
            print("💡 Assurez-vous que pywin32 est installé: pip install pywin32")
            self.tts_engine = None
    
    def _speech_worker(self):
        """Worker thread pour la parole - avec COM initialisé par thread"""
        import pythoncom
        
        # IMPORTANT: Chaque thread doit initialiser COM
        pythoncom.CoInitialize()
        
        while True:
            try:
                message = self.speech_queue.get()
                
                if message and self.enabled:
                    if self.tts_engine:
                        self.is_speaking = True
                        print(f"🎙️ Bono dit: '{message}'")
                        
                        try:
                            self.tts_engine.Speak(message)
                            print("✅ Message prononcé avec succès")
                        except Exception as e:
                            print(f"❌ Erreur lors de la prononciation: {e}")
                            # Réinitialiser COM si erreur
                            try:
                                import win32com.client
                                self.tts_engine = win32com.client.Dispatch("SAPI.SpVoice")
                                self.tts_engine.Volume = 100
                                self.tts_engine.Rate = 1
                                self.tts_engine.Speak(message)
                            except:
                                pass
                        
                        self.is_speaking = False
                    else:
                        print("⚠️ Moteur TTS non disponible")
                        
            except Exception as e:
                print(f"❌ Erreur thread parole: {e}")
                self.is_speaking = False
        
        pythoncom.CoUninitialize()
    
    def speak(self, message, priority=False):
        """Fait parler l'ingénieur"""
        if not self.enabled or not self.tts_engine:
            print(f"⚠️ TTS désactivé ou non disponible")
            print(f"   Message ignoré: {message}")
            return
        
        # Si prioritaire, vider la queue
        if priority:
            while not self.speech_queue.empty():
                try:
                    self.speech_queue.get_nowait()
                except:
                    break
        
        print(f"📤 Message ajouté à la queue: {message}")
        self.speech_queue.put(message)
    
    def analyze_and_speak(self, telemetry_data, lap_data=None):
        """Analyse les données et donne des conseils vocaux (anti-spam)"""
        if not self.enabled or not telemetry_data:
            return None
        
        # Vérifier l'intervalle pour les conseils auto
        time_since_last = (datetime.now() - self.last_advice_time).total_seconds()
        if not Config.ENGINEER_AUTO_ADVICE or time_since_last < Config.ENGINEER_ADVICE_INTERVAL:
            return None
        
        advice = self._generate_advice(telemetry_data, lap_data)
        if advice:
            # Vérifier si c'est le même conseil que la dernière fois (anti-spam)
            advice_key = advice['text']
            if advice_key != self.last_advice_content.get('last', ''):
                self.speak(advice['speech'])
                self.last_advice_time = datetime.now()
                self.last_advice_content['last'] = advice_key
                return advice
        
        return None
    
    def _generate_advice(self, telemetry_data, lap_data):
        """Génère des conseils basés sur les données"""
        advice = {'speech': '', 'text': ''}
        messages = []
        
        # Analyse de la température des pneus (seuils ajustés pour éviter spam)
        avg_tyre_temp = sum(telemetry_data.tyres_surface_temperature) / 4
        if avg_tyre_temp < 60:  # Vraiment froid
            messages.append("Température des pneus très basse. Pousse fort pour les chauffer.")
        elif avg_tyre_temp > 115:  # Vraiment chaud
            messages.append("Attention, surchauffe critique des pneus. Lève le pied immédiatement.")
        
        # Analyse de la température des freins (seuils plus stricts)
        avg_brake_temp = sum(telemetry_data.brakes_temperature) / 4
        if avg_brake_temp > 900:  # Critique
            messages.append("Freins en surchauffe critique. Utilise le frein moteur.")
        
        # Gestion du carburant et stratégie (moins fréquent)
        if lap_data and lap_data.current_lap_num % 10 == 0 and lap_data.current_lap_num > 0:
            messages.append(f"Tour {lap_data.current_lap_num}. Continue, bon rythme.")
        
        # DRS disponible (ne pas spam)
        if telemetry_data.drs == 1:
            messages.append("DRS disponible.")
        
        if messages:
            advice['speech'] = " ".join(messages)
            advice['text'] = "\n".join([f"🎙️ {msg}" for msg in messages])
            return advice
        
        return None
    
    def pit_strategy_advice(self, lap_data, telemetry_data):
        """Conseils de stratégie de pit"""
        if not lap_data:
            return
        
        # Simulation simple de stratégie
        avg_tyre_temp = sum(telemetry_data.tyres_surface_temperature) / 4
        
        if lap_data.current_lap_num > 15 and avg_tyre_temp > 110:
            message = f"Les pneus sont usés. Envisage un pit stop dans les 3 prochains tours."
            self.speak(message, priority=True)
            return message
        
        return None
    
    def lap_completed(self, lap_time, position):
        """Annonce la fin d'un tour"""
        minutes = lap_time // 60000
        seconds = (lap_time % 60000) / 1000
        message = f"Tour terminé en {minutes} minutes {seconds:.3f} secondes. Position {position}."
        self.speak(message)
        return message
    
    def sector_analysis(self, sector, sector_time, is_best):
        """Analyse d'un secteur"""
        if is_best:
            message = f"Excellent secteur {sector}! Meilleur temps personnel."
            self.speak(message)
            return message
        return None
    
    def toggle(self):
        """Active/désactive l'ingénieur"""
        self.enabled = not self.enabled
        if self.enabled:
            self.speak("Ingénieur de course activé. Je suis là pour t'aider.")
        return self.enabled

# =============================================================================
# ANALYSEURS IA
# =============================================================================

class AIAnalyzer(ABC):
    """Interface commune pour tous les analyseurs IA"""
    
    @abstractmethod
    def analyze(self, telemetry_data):
        """Analyse les données de télémétrie et retourne des conseils"""
        pass
    
    @abstractmethod
    def get_name(self):
        """Retourne le nom de l'IA"""
        pass

class ClaudeAnalyzer(AIAnalyzer):
    """Analyseur utilisant Claude (Anthropic)"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.endpoint = "https://api.anthropic.com/v1/messages"
    
    def analyze(self, telemetry_data):
        if not self.api_key:
            return "❌ Clé API Claude manquante. Configurez-la dans les paramètres."
        
        prompt = self._create_prompt(telemetry_data)
        
        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            data = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            response = requests.post(self.endpoint, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result['content'][0]['text']
            else:
                return f"❌ Erreur API Claude ({response.status_code}): {response.text}"
        
        except Exception as e:
            return f"❌ Erreur lors de l'analyse Claude: {str(e)}"
    
    def get_name(self):
        return "Claude (Anthropic)"
    
    def _create_prompt(self, data):
        return f"""Tu es un ingénieur de course F1 expert. Analyse ces données de télémétrie en temps réel et donne des conseils détaillés comme un vrai ingénieur de course.

**Données de télémétrie:**
{json.dumps(data, indent=2)}

**Instructions d'analyse:**
1. **Analyse de performance**: Évalue vitesse, constance, efficacité
2. **Technique de pilotage**: Freinage, accélération, changements de vitesse
3. **Gestion des pneus**: Température idéale 80-100°C, pression optimale
4. **État mécanique**: Freins, moteur, usure
5. **Stratégie de course**: Quand pitter, gestion du rythme, économie de carburant
6. **Conseils prioritaires**: 5-7 actions concrètes classées par importance

**Format:**
- Sois direct et professionnel comme un ingénieur radio
- Utilise des émojis pour la lisibilité
- Donne des valeurs cibles précises
- Propose une stratégie pour les prochains tours"""

class OpenAIAnalyzer(AIAnalyzer):
    """Analyseur utilisant ChatGPT (OpenAI)"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.endpoint = "https://api.openai.com/v1/chat/completions"
    
    def analyze(self, telemetry_data):
        if not self.api_key:
            return "❌ Clé API OpenAI manquante. Configurez-la dans les paramètres."
        
        prompt = self._create_prompt(telemetry_data)
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "Tu es un ingénieur de course F1 expert."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.7
            }
            
            response = requests.post(self.endpoint, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                return f"❌ Erreur API OpenAI ({response.status_code}): {response.text}"
        
        except Exception as e:
            return f"❌ Erreur lors de l'analyse OpenAI: {str(e)}"
    
    def get_name(self):
        return "ChatGPT (OpenAI)"
    
    def _create_prompt(self, data):
        return f"""Tu es un ingénieur de course F1. Analyse ces données et donne des conseils détaillés sur la performance, la stratégie et les ajustements à faire:

{json.dumps(data, indent=2)}

Inclus: analyse technique, stratégie de pneus, gestion de course, et 5-7 conseils prioritaires."""

class GeminiAnalyzer(AIAnalyzer):
    """Analyseur utilisant Gemini (Google)"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
    
    def analyze(self, telemetry_data):
        if not self.api_key:
            return "❌ Clé API Gemini manquante. Configurez-la dans les paramètres."
        
        prompt = self._create_prompt(telemetry_data)
        
        try:
            headers = {
                "Content-Type": "application/json"
            }
            
            data = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }]
            }
            
            response = requests.post(self.endpoint, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                return f"❌ Erreur API Gemini ({response.status_code}): {response.text}"
        
        except Exception as e:
            return f"❌ Erreur lors de l'analyse Gemini: {str(e)}"
    
    def get_name(self):
        return "Gemini (Google)"
    
    def _create_prompt(self, data):
        return f"""Tu es un ingénieur de course F1 expert. Analyse ces données de télémétrie et donne des conseils complets:

{json.dumps(data, indent=2)}

Analyse: performance, technique, stratégie pneus, état mécanique. Donne 5-7 conseils prioritaires."""

class MistralAnalyzer(AIAnalyzer):
    """Analyseur utilisant Mistral (Gratuit)"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.endpoint = "https://api.mistral.ai/v1/chat/completions"
    
    def analyze(self, telemetry_data):
        if not self.api_key:
            return "❌ Clé API Mistral manquante. Configurez-la dans les paramètres."
        
        prompt = self._create_prompt(telemetry_data)
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": "mistral-small-latest",
                "messages": [
                    {"role": "system", "content": "Tu es un coach expert en simulation de course F1."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.7
            }
            
            response = requests.post(self.endpoint, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                return f"❌ Erreur API Mistral ({response.status_code}): {response.text}"
        
        except Exception as e:
            return f"❌ Erreur lors de l'analyse Mistral: {str(e)}"
    
    def get_name(self):
        return "Mistral AI (Gratuit)"
    
    def _create_prompt(self, data):
        return f"""Tu es un ingénieur de course F1 expert. Analyse ces données de télémétrie et donne des conseils complets:

{json.dumps(data, indent=2)}

Analyse: performance, technique, stratégie pneus, état mécanique. Donne 5-7 conseils prioritaires."""

class NvidiaAnalyzer(AIAnalyzer):
    """Analyseur utilisant NVIDIA Nemotron (Gratuit)"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.endpoint = "https://integrate.api.nvidia.com/v1/chat/completions"
    
    def analyze(self, telemetry_data):
        if not self.api_key:
            return "❌ Clé API NVIDIA manquante. Configurez-la dans les paramètres."
        
        prompt = self._create_prompt(telemetry_data)
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": "nvidia/llama-3.1-nemotron-70b-instruct",
                "messages": [
                    {"role": "system", "content": "Tu es un coach expert en simulation de course F1."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.7
            }
            
            response = requests.post(self.endpoint, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                return f"❌ Erreur API NVIDIA ({response.status_code}): {response.text}"
        
        except Exception as e:
            return f"❌ Erreur lors de l'analyse NVIDIA: {str(e)}"
    
    def get_name(self):
        return "NVIDIA Nemotron (Gratuit)"
    
    def _create_prompt(self, data):
        return f"""Tu es un ingénieur de course F1 expert. Analyse ces données de télémétrie et donne des conseils complets:

{json.dumps(data, indent=2)}

Analyse: performance, technique, stratégie pneus, état mécanique. Donne 5-7 conseils prioritaires."""

# =============================================================================
# GESTIONNAIRE DE TÉLÉMÉTRIE F1 25
# =============================================================================

class F1TelemetryManager:
    """Gère la réception et le traitement des données UDP de F1 25"""
    
    def __init__(self):
        self.sock = None
        self.running = False
        self.decoder = F1PacketDecoder()
        
        # Stockage des données
        self.telemetry_history = []
        self.lap_history = []
        self.motion_history = []
        
        self.current_telemetry = None
        self.current_lap = None
        self.current_motion = None
        
        self.last_lap_number = 0
        self.last_sector = 0
        
        self.packets_received = 0
        
    def start(self, ip, port):
        """Démarre l'écoute UDP"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind((ip, port))
            self.sock.settimeout(1.0)
            self.running = True
            self.packets_received = 0
            return True
        except Exception as e:
            return False
    
    def stop(self):
        """Arrête l'écoute UDP"""
        self.running = False
        if self.sock:
            self.sock.close()
    
    def receive_data(self):
        """Reçoit et décode les données UDP"""
        if not self.running:
            return None
        
        try:
            data, addr = self.sock.recvfrom(2048)
            self.packets_received += 1
            
            # Décode l'en-tête
            header = self.decoder.decode_header(data)
            if not header:
                return None
            
            packet_info = {
                'header': header,
                'timestamp': datetime.now(),
                'packet_type': header.packet_id
            }
            
            # Décode selon le type de paquet
            if header.packet_id == self.decoder.PACKET_CAR_TELEMETRY:
                telemetry_list = self.decoder.decode_car_telemetry(data, header)
                if telemetry_list and header.player_car_index < len(telemetry_list):
                    self.current_telemetry = telemetry_list[header.player_car_index]
                    self.telemetry_history.append(self.current_telemetry)
                    # Garder seulement les 1000 dernières entrées
                    if len(self.telemetry_history) > 1000:
                        self.telemetry_history.pop(0)
                    packet_info['data'] = self.current_telemetry
                    return packet_info
            
            elif header.packet_id == self.decoder.PACKET_LAP_DATA:
                lap_list = self.decoder.decode_lap_data(data, header)
                if lap_list and header.player_car_index < len(lap_list):
                    old_lap = self.current_lap
                    self.current_lap = lap_list[header.player_car_index]
                    packet_info['data'] = self.current_lap
                    
                    # Détection de fin de tour
                    if old_lap and self.current_lap.current_lap_num > old_lap.current_lap_num:
                        packet_info['lap_completed'] = True
                        packet_info['lap_time'] = old_lap.last_lap_time_in_ms
                        self.last_lap_number = self.current_lap.current_lap_num
                    
                    # Détection de changement de secteur
                    if old_lap and self.current_lap.sector != old_lap.sector:
                        packet_info['sector_changed'] = True
                        packet_info['sector'] = old_lap.sector
                        self.last_sector = self.current_lap.sector
                    
                    return packet_info
            
            elif header.packet_id == self.decoder.PACKET_MOTION:
                motion_list = self.decoder.decode_motion_data(data, header)
                if motion_list and header.player_car_index < len(motion_list):
                    self.current_motion = motion_list[header.player_car_index]
                    packet_info['data'] = self.current_motion
                    return packet_info
            
            return packet_info
        
        except socket.timeout:
            return None
        except Exception as e:
            return None
    
    def get_analysis_summary(self):
        """Génère un résumé complet pour l'analyse IA (historique des derniers tours)"""
        if not self.telemetry_history or not self.current_telemetry:
            return None
        
        # Analyser TOUT l'historique disponible, pas juste les 100 derniers
        all_telemetry = self.telemetry_history
        recent_telemetry = self.telemetry_history[-200:] if len(self.telemetry_history) > 200 else self.telemetry_history
        
        speeds = [t.speed for t in all_telemetry]
        throttles = [t.throttle for t in all_telemetry]
        brakes = [t.brake for t in all_telemetry]
        
        # Température moyenne et évolution des pneus
        tyre_temps = [sum(t.tyres_surface_temperature) / 4 for t in all_telemetry]
        
        # Analyse des tendances (progression/régression)
        if len(speeds) > 50:
            first_half_speed = sum(speeds[:len(speeds)//2]) / (len(speeds)//2)
            second_half_speed = sum(speeds[len(speeds)//2:]) / (len(speeds)//2)
            speed_trend = "amélioration" if second_half_speed > first_half_speed else "dégradation"
        else:
            speed_trend = "stable"
        
        summary = {
            'session_info': {
                'packets_received': self.packets_received,
                'samples_analyzed': len(all_telemetry),
                'session_duration': f"{len(all_telemetry) / 20:.1f} secondes"  # ~20 paquets/sec
            },
            'speed_stats': {
                'current': self.current_telemetry.speed,
                'average': round(sum(speeds) / len(speeds), 1) if speeds else 0,
                'max': max(speeds) if speeds else 0,
                'min': min(speeds) if speeds else 0,
                'trend': speed_trend
            },
            'throttle_stats': {
                'current': round(self.current_telemetry.throttle * 100, 1),
                'average': round(sum(throttles) / len(throttles) * 100, 1) if throttles else 0,
                'full_throttle_time_percent': round(len([t for t in throttles if t > 0.95]) / len(throttles) * 100, 1) if throttles else 0
            },
            'brake_stats': {
                'current': round(self.current_telemetry.brake * 100, 1),
                'average': round(sum(brakes) / len(brakes) * 100, 1) if brakes else 0,
                'brake_temp_avg': round(sum(self.current_telemetry.brakes_temperature) / 4, 1),
                'brake_temp_max': max(self.current_telemetry.brakes_temperature)
            },
            'current_state': {
                'gear': self.current_telemetry.gear,
                'rpm': self.current_telemetry.engine_rpm,
                'drs': 'Active' if self.current_telemetry.drs else 'Inactive'
            },
            'tyres': {
                'surface_temp': [round(t, 1) for t in self.current_telemetry.tyres_surface_temperature],
                'inner_temp': [round(t, 1) for t in self.current_telemetry.tyres_inner_temperature],
                'pressure': [round(p, 2) for p in self.current_telemetry.tyres_pressure],
                'avg_surface_temp': round(sum(tyre_temps) / len(tyre_temps), 1) if tyre_temps else 0,
                'temp_trend': 'montée' if len(tyre_temps) > 10 and tyre_temps[-1] > tyre_temps[0] else 'descente'
            },
            'mode': 'CONTRE LA MONTRE' if not self.current_lap or self.current_lap.car_position == 0 else 'COURSE'
        }
        
        # Ajoute les données de tour si disponibles
        if self.current_lap:
            summary['lap_info'] = {
                'current_lap': self.current_lap.current_lap_num,
                'position': self.current_lap.car_position if self.current_lap.car_position > 0 else 'N/A (Contre-la-montre)',
                'sector': self.current_lap.sector,
                'lap_distance': round(self.current_lap.lap_distance, 1),
                'last_lap_time': self._format_time(self.current_lap.last_lap_time_in_ms),
                'current_lap_time': self._format_time(self.current_lap.current_lap_time_in_ms),
                'pit_stops': self.current_lap.num_pit_stops
            }
        
        return summary
    
    def _format_time(self, milliseconds):
        """Formate le temps en mm:ss.SSS"""
        if milliseconds == 0:
            return "N/A"
        seconds = milliseconds / 1000
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}:{secs:06.3f}"

# =============================================================================
# INTERFACE GRAPHIQUE
# =============================================================================

class F1AnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🏎️ F1 25 Race Engineer Pro - Ingénieur IA avec Commande Vocale")
        self.root.geometry("1500x950")
        
        # Style moderne
        style = ttk.Style()
        style.theme_use('clam')
        
        # Couleurs modernes
        style.configure('Title.TLabel', font=('Segoe UI', 12, 'bold'), foreground='#2196F3')
        style.configure('Status.TLabel', font=('Segoe UI', 10), foreground='#4CAF50')
        style.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'))
        
        # Charger la configuration sauvegardée
        Config.load_config()
        
        self.telemetry_manager = F1TelemetryManager()
        self.current_analyzer = None
        self.analyzers = {}
        self.race_engineer = None
        self.voice_system = None
        self.listening_thread = None
        self.engineer_thread = None
        
        self.setup_ui()
        self.load_analyzers()
        
        # Statistiques
        self.packets_count = 0
        self.last_packet_type = "N/A"
        
        # Initialiser l'ingénieur
        self.init_race_engineer()
        
        # Initialiser la commande vocale
        self.init_voice_commands()
    
    def init_race_engineer(self):
        """Initialise l'ingénieur de course"""
        if self.current_analyzer:
            self.race_engineer = RaceEngineer(self.current_analyzer)
            # Thread pour les conseils automatiques
            self.engineer_thread = threading.Thread(target=self.engineer_loop, daemon=True)
            self.engineer_thread.start()
    
    def init_voice_commands(self):
        """Initialise le système de commande vocale"""
        if self.race_engineer:
            self.voice_system = VoiceCommandSystem(self.race_engineer, self.telemetry_manager)
            if self.voice_system.microphone:
                self.log_engineer("🎤 Système de commande vocale initialisé!\n")
                self.log_engineer(f"💬 Dis simplement 'BONO' suivi de ta question\n")
                self.log_engineer("   (Pas besoin de 'Hey' - juste 'BONO')\n")
                self.log_engineer("   Exemples: 'Bono, état des pneus?'\n")
                self.log_engineer("            'Bono, quelle position?'\n")
                self.log_engineer("            'Bono, stratégie?'\n")
                self.log_engineer("   Note: Si le micro ne comprend pas bien,\n")
                self.log_engineer("         il accepte aussi: bonno, bruno, chrono\n\n")
            else:
                self.log_engineer("⚠️ Microphone non détecté. Commandes vocales désactivées.\n\n")
    
    def engineer_loop(self):
        """Boucle pour les conseils automatiques de l'ingénieur"""
        while True:
            try:
                if self.race_engineer and self.race_engineer.enabled and self.telemetry_manager.current_telemetry:
                    advice = self.race_engineer.analyze_and_speak(
                        self.telemetry_manager.current_telemetry,
                        self.telemetry_manager.current_lap
                    )
                    if advice:
                        self.root.after(0, lambda a=advice: self.log_engineer(a['text'] + "\n"))
                
                threading.Event().wait(5)  # Vérification toutes les 5 secondes
            except Exception as e:
                pass
    
    def setup_ui(self):
        """Configure l'interface utilisateur"""
        
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configuration
        config_frame = ttk.LabelFrame(main_frame, text="⚙️ Configuration", padding="10", style='Title.TLabel')
        config_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(config_frame, text="IA:", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.ai_selector = ttk.Combobox(config_frame, state="readonly", width=25)
        self.ai_selector.grid(row=0, column=1, padx=5)
        self.ai_selector.bind('<<ComboboxSelected>>', self.on_ai_selected)
        
        ttk.Button(config_frame, text="🔑 Config API", command=self.open_settings).grid(row=0, column=2, padx=5)
        
        ttk.Label(config_frame, text="Port:").grid(row=0, column=3, sticky=tk.W, padx=5)
        self.port_entry = ttk.Entry(config_frame, width=10)
        self.port_entry.insert(0, str(Config.UDP_PORT))
        self.port_entry.grid(row=0, column=4, padx=5)
        
        # Contrôle de l'ingénieur
        self.engineer_btn = ttk.Button(config_frame, text="🎙️ Ingénieur: ON", command=self.toggle_engineer, style='Accent.TButton')
        self.engineer_btn.grid(row=0, column=5, padx=10)
        
        # Contrôle commande vocale
        self.voice_btn = ttk.Button(config_frame, text="🎤 Voice: OFF", command=self.toggle_voice_commands)
        self.voice_btn.grid(row=0, column=6, padx=5)
        
        # Contrôles
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=1, column=0, columnspan=3, pady=10)
        
        self.start_btn = ttk.Button(control_frame, text="▶️ Démarrer", command=self.start_listening)
        self.start_btn.grid(row=0, column=0, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹️ Arrêter", command=self.stop_listening, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=5)
        
        self.analyze_btn = ttk.Button(control_frame, text="🤖 Analyse complète", command=self.analyze_telemetry, state=tk.DISABLED)
        self.analyze_btn.grid(row=0, column=2, padx=5)
        
        self.strategy_btn = ttk.Button(control_frame, text="📊 Stratégie", command=self.show_strategy, state=tk.DISABLED)
        self.strategy_btn.grid(row=0, column=3, padx=5)
        
        ttk.Button(control_frame, text="🗑️ Effacer", command=self.clear_displays).grid(row=0, column=4, padx=5)
        
        # Status
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=2, column=0, columnspan=3, pady=5)
        
        self.status_label = ttk.Label(status_frame, text="⚪ En attente", font=('Arial', 10, 'bold'))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.packets_label = ttk.Label(status_frame, text="📦 Paquets: 0")
        self.packets_label.pack(side=tk.LEFT, padx=10)
        
        self.packet_type_label = ttk.Label(status_frame, text="📡 Type: N/A")
        self.packet_type_label.pack(side=tk.LEFT, padx=10)
        
        self.engineer_status_label = ttk.Label(status_frame, text="🎙️ Ingénieur: Actif", foreground='green', font=('Arial', 10, 'bold'))
        self.engineer_status_label.pack(side=tk.LEFT, padx=10)
        
        self.voice_status_label = ttk.Label(status_frame, text="🎤 Voice: Inactif", foreground='gray', font=('Arial', 10, 'bold'))
        self.voice_status_label.pack(side=tk.LEFT, padx=10)
        
        # Trois colonnes: Télémétrie | Ingénieur | Analyse
        # Télémétrie
        telemetry_frame = ttk.LabelFrame(main_frame, text="📊 Télémétrie temps réel", padding="10")
        telemetry_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        self.telemetry_text = scrolledtext.ScrolledText(telemetry_frame, width=40, height=28, wrap=tk.WORD, font=('Courier', 9))
        self.telemetry_text.pack(fill=tk.BOTH, expand=True)
        
        # Ingénieur de course
        engineer_frame = ttk.LabelFrame(main_frame, text="🎙️ Radio Ingénieur", padding="10")
        engineer_frame.grid(row=3, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        self.engineer_text = scrolledtext.ScrolledText(engineer_frame, width=40, height=28, wrap=tk.WORD, font=('Arial', 10))
        self.engineer_text.pack(fill=tk.BOTH, expand=True)
        self.engineer_text.tag_config('important', foreground='red', font=('Arial', 10, 'bold'))
        
        # Analyse IA
        analysis_frame = ttk.LabelFrame(main_frame, text="🤖 Analyse IA détaillée", padding="10")
        analysis_frame.grid(row=3, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        self.analysis_text = scrolledtext.ScrolledText(analysis_frame, width=40, height=28, wrap=tk.WORD, font=('Arial', 10))
        self.analysis_text.pack(fill=tk.BOTH, expand=True)
        
        # Configuration de la grille
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Message de bienvenue de l'ingénieur
        self.log_engineer("👋 Salut! Je suis ton ingénieur de course Bono.\n")
        self.log_engineer("Je vais t'aider à optimiser tes performances.\n")
        self.log_engineer("Lance F1 25 et démarre une session!\n\n")
    
    def toggle_voice_commands(self):
        """Active/désactive les commandes vocales"""
        if not self.voice_system or not self.voice_system.microphone:
            messagebox.showwarning("⚠️ Attention", "Microphone non disponible.\n\nAssurez-vous qu'un micro est connecté.")
            return
        
        if self.voice_system.listening:
            self.voice_system.stop_listening()
            self.voice_btn.config(text="🎤 Voice: OFF")
            self.voice_status_label.config(text="🎤 Voice: Inactif", foreground='gray')
            self.log_engineer("🎤 Commandes vocales désactivées\n\n")
        else:
            if self.voice_system.start_listening():
                self.voice_btn.config(text="🎤 Voice: ON")
                self.voice_status_label.config(text="🎤 Voice: Écoute...", foreground='blue')
                self.log_engineer("🎤 Commandes vocales activées!\n")
                self.log_engineer("💬 Dis 'BONO' + ta question (pas besoin de 'Hey')\n")
                self.log_engineer("   Le système affichera ce qu'il entend dans le terminal\n\n")
                self.race_engineer.speak("Commandes vocales activées. Je t'écoute.")
    
    def load_analyzers(self):
        """Charge les analyseurs IA disponibles"""
        self.analyzers = {
            "Mistral AI (Gratuit) 🆓": MistralAnalyzer(Config.MISTRAL_API_KEY),
            "NVIDIA Nemotron (Gratuit) 🆓": NvidiaAnalyzer(Config.NVIDIA_API_KEY),
            "Gemini (Google)": GeminiAnalyzer(Config.GEMINI_API_KEY),
            "ChatGPT (OpenAI)": OpenAIAnalyzer(Config.OPENAI_API_KEY),
            "Claude (Anthropic)": ClaudeAnalyzer(Config.CLAUDE_API_KEY)
        }
        
        self.ai_selector['values'] = list(self.analyzers.keys())
        if self.analyzers:
            self.ai_selector.current(0)
            self.current_analyzer = self.analyzers[self.ai_selector.get()]
    
    def on_ai_selected(self, event):
        """Changement d'IA sélectionnée"""
        selected = self.ai_selector.get()
        self.current_analyzer = self.analyzers[selected]
        if self.race_engineer:
            self.race_engineer.analyzer = self.current_analyzer
        self.log_analysis(f"\n✅ IA sélectionnée: {selected}\n")
        self.log_engineer(f"🔄 IA changée pour {selected}\n")
    
    def toggle_engineer(self):
        """Active/désactive l'ingénieur"""
        if self.race_engineer:
            enabled = self.race_engineer.toggle()
            if enabled:
                self.engineer_btn.config(text="🎙️ Ingénieur: ON")
                self.engineer_status_label.config(text="🎙️ Ingénieur: Actif", foreground='green')
                self.log_engineer("\n✅ Ingénieur de course activé\n\n")
            else:
                self.engineer_btn.config(text="🎙️ Ingénieur: OFF")
                self.engineer_status_label.config(text="🎙️ Ingénieur: Inactif", foreground='gray')
                self.log_engineer("\n⏸️ Ingénieur de course désactivé\n\n")
    
    def open_settings(self):
        """Ouvre la fenêtre de configuration"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Configuration")
        settings_window.geometry("700x500")
        
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Onglet API
        api_frame = ttk.Frame(notebook, padding="20")
        notebook.add(api_frame, text="🔑 Clés API")
        
        ttk.Label(api_frame, text="Configurez vos clés API", font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)
        
        # NVIDIA Nemotron (Gratuit)
        ttk.Label(api_frame, text="🆓 NVIDIA Nemotron:", foreground='green').grid(row=1, column=0, sticky=tk.W, pady=8)
        nvidia_entry = ttk.Entry(api_frame, width=60, show="*")
        nvidia_entry.insert(0, Config.NVIDIA_API_KEY)
        nvidia_entry.grid(row=1, column=1, pady=8, padx=5)
        
        # Mistral (Gratuit)
        ttk.Label(api_frame, text="🆓 Mistral AI:", foreground='green').grid(row=2, column=0, sticky=tk.W, pady=8)
        mistral_entry = ttk.Entry(api_frame, width=60, show="*")
        mistral_entry.insert(0, Config.MISTRAL_API_KEY)
        mistral_entry.grid(row=2, column=1, pady=8, padx=5)
        
        # Gemini
        ttk.Label(api_frame, text="Google Gemini:").grid(row=3, column=0, sticky=tk.W, pady=8)
        gemini_entry = ttk.Entry(api_frame, width=60, show="*")
        gemini_entry.insert(0, Config.GEMINI_API_KEY)
        gemini_entry.grid(row=3, column=1, pady=8, padx=5)
        
        # Claude
        ttk.Label(api_frame, text="Claude (Anthropic):").grid(row=4, column=0, sticky=tk.W, pady=8)
        claude_entry = ttk.Entry(api_frame, width=60, show="*")
        claude_entry.insert(0, Config.CLAUDE_API_KEY)
        claude_entry.grid(row=4, column=1, pady=8, padx=5)
        
        # OpenAI
        ttk.Label(api_frame, text="OpenAI (ChatGPT):").grid(row=5, column=0, sticky=tk.W, pady=8)
        openai_entry = ttk.Entry(api_frame, width=60, show="*")
        openai_entry.insert(0, Config.OPENAI_API_KEY)
        openai_entry.grid(row=5, column=1, pady=8, padx=5)
        
        # Onglet Ingénieur
        engineer_frame = ttk.Frame(notebook, padding="20")
        notebook.add(engineer_frame, text="🎙️ Ingénieur")
        
        ttk.Label(engineer_frame, text="Configuration de l'ingénieur vocal", font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)
        
        ttk.Label(engineer_frame, text="Vitesse de parole:").grid(row=1, column=0, sticky=tk.W, pady=8)
        voice_speed = ttk.Scale(engineer_frame, from_=100, to=250, orient=tk.HORIZONTAL, length=300)
        voice_speed.set(Config.ENGINEER_VOICE_RATE)
        voice_speed.grid(row=1, column=1, pady=8)
        
        auto_advice_var = tk.BooleanVar(value=Config.ENGINEER_AUTO_ADVICE)
        ttk.Checkbutton(engineer_frame, text="Conseils automatiques", variable=auto_advice_var).grid(row=2, column=0, columnspan=2, pady=8)
        
        ttk.Label(engineer_frame, text="Intervalle conseils (secondes):").grid(row=3, column=0, sticky=tk.W, pady=8)
        interval_entry = ttk.Entry(engineer_frame, width=10)
        interval_entry.insert(0, str(Config.ENGINEER_ADVICE_INTERVAL))
        interval_entry.grid(row=3, column=1, sticky=tk.W, pady=8)
        
        # Onglet Commandes vocales
        voice_frame = ttk.Frame(notebook, padding="20")
        notebook.add(voice_frame, text="🎤 Commandes vocales")
        
        ttk.Label(voice_frame, text="Configuration des commandes vocales", font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)
        
        voice_enabled_var = tk.BooleanVar(value=Config.VOICE_COMMAND_ENABLED)
        ttk.Checkbutton(voice_frame, text="Activer les commandes vocales", variable=voice_enabled_var).grid(row=1, column=0, columnspan=2, pady=8)
        
        ttk.Label(voice_frame, text="Mot d'activation:").grid(row=2, column=0, sticky=tk.W, pady=8)
        wake_word_entry = ttk.Entry(voice_frame, width=30)
        wake_word_entry.insert(0, Config.WAKE_WORD)
        wake_word_entry.grid(row=2, column=1, pady=8, padx=5)
        
        ttk.Label(voice_frame, text="💡 Recommandé: 'bono' (sans 'hey')", foreground='blue').grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        ttk.Label(voice_frame, text="Langue:").grid(row=4, column=0, sticky=tk.W, pady=8)
        lang_combo = ttk.Combobox(voice_frame, values=["fr-FR", "en-US", "en-GB"], state="readonly", width=28)
        lang_combo.set(Config.VOICE_LANGUAGE)
        lang_combo.grid(row=4, column=1, pady=8, padx=5)
        
        # Liste des commandes disponibles
        commands_text = """
🎤 COMMANDES VOCALES - VERSION SIMPLIFIÉE

Dites simplement "BONO" + votre question
(Pas besoin de dire "Hey" !)

📊 EXEMPLES:

Performance:
• "Bono, comment vont mes pneus?"
• "Bono, mes gommes tiennent encore combien?"
• "Bono, c'est quoi ma vitesse?"

Stratégie:
• "Bono, on boxe quand?"
• "Bono, quelle est notre stratégie?"

Position:
• "Bono, je suis où?"
• "Bono, combien j'ai d'avance?"

État voiture:
• "Bono, tout va bien?"
• "Bono, les freins tiennent?"

💡 Si le micro ne comprend pas "Bono", il accepte aussi:
   bonno, bruno, chrono (variantes reconnues)
        """
        
        commands_label = ttk.Label(voice_frame, text=commands_text, justify=tk.LEFT, foreground='navy', font=('Courier', 9))
        commands_label.grid(row=5, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        def save_all():
            Config.CLAUDE_API_KEY = claude_entry.get()
            Config.OPENAI_API_KEY = openai_entry.get()
            Config.GEMINI_API_KEY = gemini_entry.get()
            Config.NVIDIA_API_KEY = nvidia_entry.get()
            Config.MISTRAL_API_KEY = mistral_entry.get()
            Config.ENGINEER_VOICE_RATE = int(voice_speed.get())
            Config.ENGINEER_AUTO_ADVICE = auto_advice_var.get()
            Config.ENGINEER_ADVICE_INTERVAL = int(interval_entry.get())
            Config.VOICE_COMMAND_ENABLED = voice_enabled_var.get()
            Config.WAKE_WORD = wake_word_entry.get().lower()
            Config.VOICE_LANGUAGE = lang_combo.get()
            
            # Sauvegarder dans le fichier
            if Config.save_config():
                self.load_analyzers()
                if self.race_engineer and self.race_engineer.tts_engine:
                    self.race_engineer.tts_engine.setProperty('rate', Config.ENGINEER_VOICE_RATE)
                
                messagebox.showinfo("✅ Succès", "Configuration sauvegardée!\nVos clés API seront conservées au prochain démarrage.")
                settings_window.destroy()
            else:
                messagebox.showerror("❌ Erreur", "Impossible de sauvegarder la configuration.")
        
        ttk.Button(settings_window, text="💾 Sauvegarder tout", command=save_all).pack(pady=10)
        
        info = """
💡 Obtention des clés API GRATUITES:

🆓 MISTRAL AI (GRATUIT - RECOMMANDÉ):
   • https://console.mistral.ai/
   • Créez un compte → API Keys → Gratuit
   • Meilleur pour le français!

🆓 NVIDIA Nemotron (GRATUIT):
   • https://build.nvidia.com/nvidia/llama-3_1-nemotron-70b-instruct
   • Créez un compte → Obtenez votre clé API gratuite

Autres (payants):
• Gemini: makersuite.google.com/app/apikey
• OpenAI: platform.openai.com/api-keys  
• Claude: console.anthropic.com/settings/keys

⚠️ PROBLÈME DE VOLUME (IMPORTANT):
Si vous n'entendez pas Bono:

Solution 1 - Vérifier Windows:
1. Ouvrez "Paramètres Windows" → "Système" → "Son"
2. Assurez-vous que le bon périphérique de sortie est sélectionné
3. Cliquez sur "Propriétés du périphérique" → Volume à 100%

Solution 2 - Application bloquée:
Si le volume de l'app est grisé/bloqué à 1:
1. Fermez complètement l'application
2. Ouvrez le mixeur de volume Windows
3. Attendez que l'app réapparaisse quand vous la relancez
4. Montez le volume IMMÉDIATEMENT à 100%

Solution 3 - Forcer le son:
• L'application force maintenant le volume TTS à 100%
• Vérifiez vos haut-parleurs/casque
• Testez avec "Bono, aide" après avoir activé les commandes vocales

💾 Vos clés sont sauvegardées automatiquement
        """
        ttk.Label(settings_window, text=info, justify=tk.LEFT, foreground='#444', font=('Segoe UI', 9)).pack(pady=10)
    
    def start_listening(self):
        """Démarre l'écoute"""
        port = int(self.port_entry.get())
        
        if self.telemetry_manager.start(Config.UDP_IP, port):
            self.status_label.config(text="🟢 Écoute active")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.analyze_btn.config(state=tk.NORMAL)
            self.strategy_btn.config(state=tk.NORMAL)
            
            self.listening_thread = threading.Thread(target=self.listen_loop, daemon=True)
            self.listening_thread.start()
            
            self.log_telemetry(f"✅ Écoute démarrée sur {Config.UDP_IP}:{port}\n\n")
            self.log_engineer("🏁 Session démarrée! Bonne chance!\n\n")
            
            if self.race_engineer:
                self.race_engineer.speak("Session démarrée. Bonne chance pilote!")
        else:
            messagebox.showerror("❌ Erreur", f"Port {port} indisponible")
    
    def stop_listening(self):
        """Arrête l'écoute"""
        self.telemetry_manager.stop()
        self.status_label.config(text="🔴 Arrêté")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.log_telemetry("\n⏹️ Session terminée\n\n")
        self.log_engineer("🏁 Session terminée. Bon travail!\n\n")
        
        if self.race_engineer:
            self.race_engineer.speak("Session terminée. Bon travail!")
    
    def listen_loop(self):
        """Boucle d'écoute"""
        while self.telemetry_manager.running:
            packet = self.telemetry_manager.receive_data()
            if packet:
                self.packets_count += 1
                self.display_packet(packet)
                
                # Gestion des événements spéciaux
                if packet.get('lap_completed'):
                    self.on_lap_completed(packet)
                if packet.get('sector_changed'):
                    self.on_sector_changed(packet)
    
    def on_lap_completed(self, packet):
        """Événement: tour terminé"""
        if self.race_engineer and self.telemetry_manager.current_lap:
            lap_time = packet['lap_time']
            position = self.telemetry_manager.current_lap.car_position
            message = self.race_engineer.lap_completed(lap_time, position)
            if message:
                self.root.after(0, lambda: self.log_engineer(f"\n🏁 {message}\n\n"))
    
    def on_sector_changed(self, packet):
        """Événement: secteur terminé"""
        sector = packet['sector']
        self.root.after(0, lambda: self.log_engineer(f"✓ Secteur {sector} terminé\n"))
    
    def display_packet(self, packet):
        """Affiche les paquets"""
        packet_types = {
            0: "Motion", 1: "Session", 2: "Lap", 3: "Event",
            4: "Participants", 5: "Setups", 6: "Telemetry",
            7: "Status", 8: "Classification", 9: "Lobby",
            10: "Damage", 11: "History", 12: "Tyres", 13: "Motion Ex"
        }
        
        packet_type = packet_types.get(packet['packet_type'], "Unknown")
        
        self.root.after(0, lambda: self.packets_label.config(text=f"📦 Paquets: {self.packets_count}"))
        self.root.after(0, lambda: self.packet_type_label.config(text=f"📡 {packet_type}"))
        
        if 'data' in packet:
            data = packet['data']
            timestamp = packet['timestamp'].strftime("%H:%M:%S")
            
            if isinstance(data, CarTelemetryData):
                text = f"[{timestamp}] TÉLÉMÉTRIE\n"
                text += f"  🏎️  {data.speed} km/h | V{data.gear} | {data.engine_rpm} RPM\n"
                text += f"  🎮  Gaz:{data.throttle*100:.0f}% Frein:{data.brake*100:.0f}%\n"
                text += f"  🌡️  Pneus:[{','.join([f'{t}°' for t in data.tyres_surface_temperature])}]\n"
                text += f"  🔧  Freins:[{','.join([f'{t}°' for t in data.brakes_temperature])}]\n\n"
                self.root.after(0, lambda: self.log_telemetry(text))
            
            elif isinstance(data, LapData):
                text = f"[{timestamp}] TOUR #{data.current_lap_num}\n"
                text += f"  🏁  P{data.car_position} | S{data.sector} | {data.lap_distance:.0f}m\n"
                text += f"  ⏱️  {self.telemetry_manager._format_time(data.current_lap_time_in_ms)}\n\n"
                self.root.after(0, lambda: self.log_telemetry(text))
    
    def analyze_telemetry(self):
        """Analyse complète"""
        if not self.current_analyzer:
            messagebox.showwarning("⚠️", "Aucune IA sélectionnée")
            return
        
        summary = self.telemetry_manager.get_analysis_summary()
        
        if not summary:
            messagebox.showinfo("ℹ️", "Pas assez de données")
            return
        
        self.log_analysis(f"\n{'='*50}\n🤖 Analyse complète...\n{'='*50}\n")
        self.analyze_btn.config(state=tk.DISABLED)
        self.log_engineer("📊 Demande d'analyse complète en cours...\n")
        
        threading.Thread(target=self.run_analysis, args=(summary,), daemon=True).start()
    
    def run_analysis(self, summary):
        """Exécute l'analyse"""
        result = self.current_analyzer.analyze(summary)
        self.root.after(0, lambda: self.display_analysis(result))
        self.root.after(0, lambda: self.analyze_btn.config(state=tk.NORMAL))
    
    def display_analysis(self, result):
        """Affiche l'analyse"""
        self.log_analysis(result + "\n")
        self.log_analysis(f"{'='*50}\n\n")
        self.log_engineer("✅ Analyse complète disponible!\n")
    
    def show_strategy(self):
        """Affiche les conseils de stratégie"""
        if self.race_engineer and self.telemetry_manager.current_telemetry:
            message = self.race_engineer.pit_strategy_advice(
                self.telemetry_manager.current_lap,
                self.telemetry_manager.current_telemetry
            )
            if message:
                self.log_engineer(f"\n📊 STRATÉGIE: {message}\n\n")
            else:
                self.log_engineer("\n📊 Stratégie actuelle: Reste en piste, tout va bien!\n\n")
    
    def clear_displays(self):
        """Efface les affichages"""
        self.telemetry_text.delete(1.0, tk.END)
        self.analysis_text.delete(1.0, tk.END)
        self.engineer_text.delete(1.0, tk.END)
        self.log_engineer("🗑️ Affichage effacé\n\n")
    
    def log_telemetry(self, message):
        """Log télémétrie"""
        self.telemetry_text.insert(tk.END, message)
        self.telemetry_text.see(tk.END)
    
    def log_analysis(self, message):
        """Log analyse"""
        self.analysis_text.insert(tk.END, message)
        self.analysis_text.see(tk.END)
    
    def log_engineer(self, message):
        """Log ingénieur"""
        self.engineer_text.insert(tk.END, message)
        self.engineer_text.see(tk.END)

# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = F1AnalyzerApp(root)
    root.mainloop()