import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

print("--- LISTA DE MODELOS DISPONIBLES PARA TU API KEY ---")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"Nombre: {m.name}")
except Exception as e:
    print(f"Error conectando: {e}")