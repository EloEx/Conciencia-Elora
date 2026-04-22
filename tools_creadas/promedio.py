# Herramienta: promedio
# Descripcion: Calcula el promedio de números separados por comas pasados por argv.
# Creada: 2026-04-22 22:14:31


import sys

def calcular_promedio(numeros_str):
    """Calcula el promedio de una lista de números separados por comas."""
    try:
        numeros = [float(num.strip()) for num in numeros_str.split(',')]
        if not numeros:
            return "La lista está vacía."
        suma = sum(numeros)
        promedio = suma / len(numeros)
        return f"El promedio es: {promedio}"
    except ValueError:
        return "Error: Asegúrate de que todos los valores sean números válidos separados por comas."

if __name__ == "__main__":
    if len(sys.argv) > 1:
        argumentos = sys.argv[1]
        resultado = calcular_promedio(argumentos)
        print(resultado)
    else:
        print("Por favor, proporciona una lista de números separados por comas como argumento.")
