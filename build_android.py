#!/usr/bin/env python3
"""
Build script for GimRoutine Android app
"""
import os
import subprocess
import sys

def run_command(cmd, description):
    print(f"\n{'='*50}")
    print(f"Ejecutando: {description}")
    print(f"Comando: {' '.join(cmd)}")
    print('='*50)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        if result.returncode != 0:
            print(f"ERROR: Comando falló con código {result.returncode}")
            return False
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    print("Build script para GimRoutine Android")
    print("="*50)

    # Clean previous build
    if run_command(['buildozer', 'android', 'clean'], 'Limpiando build anterior'):
        print("✓ Build limpiado exitosamente")
    else:
        print("⚠ Error limpiando build, continuando...")

    # Build the APK
    if run_command(['buildozer', 'android', 'debug'], 'Construyendo APK de debug'):
        print("✓ APK construido exitosamente!")

        # Check if APK exists
        apk_path = 'bin/GimRoutine-0.1-debug.apk'
        if os.path.exists(apk_path):
            print(f"✓ APK encontrado en: {apk_path}")
            print(f"Tamaño: {os.path.getsize(apk_path)} bytes")

            print("\n" + "="*50)
            print("INSTRUCCIONES PARA INSTALAR:")
            print("="*50)
            print("1. Transfiere el APK a tu teléfono:")
            print(f"   {os.path.abspath(apk_path)}")
            print("2. En tu teléfono, habilita 'Instalación de apps desconocidas'")
            print("3. Instala el APK")
            print("4. Si crashea, revisa el log en:")
            print("   Almacenamiento interno > gimroutine_debug.log")
            print("="*50)
        else:
            print("✗ APK no encontrado")
    else:
        print("✗ Error construyendo APK")
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())