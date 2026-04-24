# Herramienta: calculadora_promedio
# Descripcion: Calcula el promedio de una lista de numeros dada como argumento.
# Creada: 2026-04-24 01:18:36

def calcular_promedio(lista_numeros):
    """Calcula el promedio de una lista de números."""
    if not lista_numeros:
        return 0
    suma = sum(lista_numeros)
    promedio = suma / len(lista_numeros)
    return promedio