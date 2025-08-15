
Coupon Harvester & Pattern Generator
-----------------------------------

Contenido del paquete:
- coupon_harvester.py    -> Script principal (Python 3.8+)
- run_linux.sh           -> Script para ejecutar en Linux (doble clic / terminal)
- run_mac.command        -> Script para ejecutar en macOS (doble clic)
- run_windows.bat        -> Script para ejecutar en Windows (doble clic)
- README.txt             -> Este fichero
- LICENSE.txt            -> Aviso de uso

Requisitos:
- Python 3.8 o superior
- Dependencias: requests, beautifulsoup4, lxml
  Instalar con: python -m pip install requests beautifulsoup4 lxml

Ejecutar directamente (sin crear .exe/.app):
- Linux/macOS: abrir terminal en la carpeta y ejecutar:
    python3 coupon_harvester.py
  o hacer doble clic sobre run_linux.sh / run_mac.command si el gestor lo permite.

- Windows: doble clic en run_windows.bat (abre una consola y ejecuta Python).

Crear ejecutable con PyInstaller (opcional, recomendado crear en el SO destino):
1) Instalar PyInstaller: python -m pip install pyinstaller
2) Generar .exe (Windows): pyinstaller --onefile --windowed coupon_harvester.py
   Resultado: dist\coupon_harvester.exe
3) Generar binario (Linux/macOS): pyinstaller --onefile --windowed coupon_harvester.py
   Resultado: dist/coupon_harvester  (macOS puede requerir notarización para distribución)

Notas de seguridad y legales:
- Este generador produce códigos marcados con suffix '-TEST' para evitar uso indebido.
- No utilices los cupones generados para intentar redimir en tiendas ajenas.
- Respeta robots.txt y condiciones de uso de las páginas que analices.
