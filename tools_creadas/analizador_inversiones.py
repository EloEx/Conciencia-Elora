# Herramienta: analizador_inversiones
# Descripcion: Analiza datos de inversiones pasados (separados por comas) para estimar tendencias.
# Creada: 2026-04-24 01:18:36

import sys

def analizar_inversiones(argumentos):
    """Analiza datos de inversiones pasados para predecir tendencias.
    Recibe los datos como una cadena separada por comas.
    """
    try:
        numeros_str = argumentos.split(',')
        datos = [float(n) for n in numeros_str]
        
        if not datos:
            return "No se proporcionaron datos para analizar."

        # Lógica simple de análisis: calcular promedio y desviación estándar
        promedio = sum(datos) / len(datos)
        if len(datos) > 1:
            varianza = sum([(d - promedio) ** 2 for d in datos]) / (len(datos) - 1)
            desviacion_estandar = varianza ** 0.5
        else:
            desviacion_estandar = 0
            
        # Predicción muy simplificada: si el último dato es mayor que el promedio, tendencia alcista
        tendencia = "alcista" if datos[-1] > promedio else "bajista" if datos[-1] < promedio else "estable"

        return f"Análisis de Inversiones:\nPromedio: {promedio:.2f}\nDesviación Estándar: {desviacion_estandar:.2f}\nTendencia estimada: {tendencia}"

    except ValueError:
        return "Error: Asegúrate de que todos los argumentos sean números válidos separados por comas."
    except Exception as e:
        return f"Ocurrió un error inesperado: {e}"

if __name__ == "__main__":
    # Simulación de argumentos de línea de comandos
    # En un entorno real, se usaría sys.argv[1:]
    # Ejemplo de uso: python analizador_inversiones.py "100,110,120,115,130"
    if len(sys.argv) > 1:
        print(analizador_inversiones(sys.argv[1]))
    else:
        print("Por favor, proporciona los datos de inversión como argumentos. Ejemplo: '100,110,120,115,130'")