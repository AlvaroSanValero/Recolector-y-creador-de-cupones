Coupon Harvester v2 - Paquete mejorado
-------------------------------------

Mejoras incluidas:
- Extracción: JSON-LD, meta, atributos, scripts inline.
- CLI mode con argumentos para automatizar tareas.
- Registro detallado en coupon_harvester.log.
- Almacenamiento en SQLite (coupon_harvest.db) + export CSV/JSON automático.
- Opcional: soporte renderizado JS con Selenium/Playwright (no incluido).

Requisitos mínimos:
- Python 3.8+
- pip install requests beautifulsoup4 lxml
- Opcional para JS: selenium + driver (chromedriver) o playwright

Instrucciones rápidas:
1) Instalar dependencias:
    python -m pip install requests beautifulsoup4 lxml
   Opcional (Selenium):
    python -m pip install selenium
   Opcional (Playwright):
    python -m pip install playwright
    playwright install

2) Ejecutar GUI:
    python3 coupon_harvester_v2.py

3) Ejecutar CLI (sin GUI), ejemplo:
    python3 coupon_harvester_v2.py --no-gui --urls urls.txt --export results.json --auto-generate --generate-count 50

4) Crear ejecutable (en cada SO, en la máquina destino):
    python -m pip install pyinstaller
    pyinstaller --onefile --windowed coupon_harvester_v2.py

Archivos incluidos en este paquete:
- coupon_harvester_v2.py
- build_* scripts (helpers)
- coupon_harvester_v2.spec
- LICENSE.txt

Notas de seguridad:
- Los códigos generados llevan por defecto el sufijo '-TEST' para evitar redenciones accidentales.
- Usa esta herramienta solo para pruebas, auditorías o con permiso del propietario de los cupones.
- Respeta robots.txt y políticas de los sitios web que analices.
