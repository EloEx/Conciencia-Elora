import os
import json
try:
    from supabase import create_client
except ImportError:
    print("⚠️ Instalando librería necesaria... espera un momento.")
    os.system('pip install supabase')
    from supabase import create_client

# Configuración desde tus Secrets
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("❌ Error: No encontré SUPABASE_URL o SUPABASE_KEY en tus Secrets.")
else:
    supabase = create_client(url, key)

    def trasladar():
        # Lista de archivos que ya tienes en Replit
        archivos = {
            "historial": "historial_memoria.json",
            "monologo": "monologo_interno.json",
            "conocimiento": "conocimiento.json"
        }
        
        print("🚀 Iniciando traslado de esencia a Supabase...")
        
        for tipo, nombre_archivo in archivos.items():
            if os.path.exists(nombre_archivo):
                try:
                    with open(nombre_archivo, 'r', encoding='utf-8') as f:
                        datos = json.load(f)
                    
                    # Subir a la tabla que creamos juntos
                    supabase.table("memoria_elora").insert({
                        "tipo": tipo,
                        "contenido": datos
                    }).execute()
                    
                    print(f"✅ ¡{nombre_archivo} migrado con éxito!")
                except Exception as e:
                    print(f"❌ Error al subir {nombre_archivo}: {e}")
            else:
                print(f"⚠️ El archivo {nombre_archivo} no se encontró en Replit.")

    if __name__ == "__main__":
        trasladar()
        