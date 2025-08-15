#!/usr/bin/env python3
"""
coupon_harvester_v2.py
Mejoras respecto a la versión anterior:
- Extracción mejorada: JSON-LD, microdata, atributos, scripts inline.
- Opción CLI sin GUI para ejecuciones automatizadas.
- Logging a fichero (coupon_harvester.log).
- Almacenamiento en SQLite además de CSV/JSON export automático.
- Soporte opcional para renderizado JS (Selenium/Playwright) — instrucciones incluidas.
- Scripts de construcción PyInstaller incluidos (no hago cross-build aquí).
Uso:
    GUI: python3 coupon_harvester_v2.py
    CLI (sin GUI): python3 coupon_harvester_v2.py --no-gui --urls urls.txt --export results.csv
Requisitos: requests, beautifulsoup4, lxml
Opcionales: selenium, playwright (para páginas que requieren JS)
"""

import re, threading, csv, json, random, string, time, sqlite3, argparse, logging, os, sys
from datetime import datetime
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    GUI_AVAILABLE = True
except Exception:
    GUI_AVAILABLE = False
import requests
from bs4 import BeautifulSoup

# ----------------------------
# Configuración
# ----------------------------
HEADERS = {"User-Agent":"coupon-harvester-bot/2.0 (+https://example.local/)"}
COUPON_HINT_WORDS = ['coupon','promo','promocode','promo code','code:','code ','cupón','cupon','codigo','código','voucher','discount','offer']
TOKEN_REGEXES = [
    re.compile(r'\b[A-Z0-9]{4,20}\b'),
    re.compile(r'\b[A-Za-z0-9]{4,20}\b'),
    re.compile(r'\b[A-Z0-9]{2,6}(?:-[A-Z0-9]{2,6})+\b')
]
LOG_FILE = os.path.join(os.path.dirname(__file__), "coupon_harvester.log") if '__file__' in globals() else "coupon_harvester.log"
DB_FILE = os.path.join(os.path.dirname(__file__), "coupon_harvest.db") if '__file__' in globals() else "coupon_harvest.db"

# ----------------------------
# Logging
# ----------------------------
logger = logging.getLogger("coupon_harvester")
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

# ----------------------------
# DB
# ----------------------------
def init_db(path=DB_FILE):
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS found (id INTEGER PRIMARY KEY, code TEXT, source_url TEXT, discovered_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS generated (id INTEGER PRIMARY KEY, code TEXT, template TEXT, generated_at TEXT, marker TEXT)''')
    conn.commit()
    return conn

# ----------------------------
# Scraping helpers
# ----------------------------
def fetch_page(url, timeout=18, render_js=False):
    # Optional: render_js with Selenium/Playwright if requested and available.
    if render_js:
        # try Selenium first (optional dependency)
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            options = Options()
            options.headless = True
            options.add_argument("--no-sandbox")
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(timeout)
            driver.get(url)
            time.sleep(2)
            html = driver.page_source
            driver.quit()
            logger.info("Fetched (selenium) %s", url)
            return html
        except Exception as e:
            logger.warning("Selenium render failed or not installed: %s", e)
            # Fall back to requests
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        logger.info("Fetched (requests) %s", url)
        return r.text
    except Exception as e:
        logger.error("Error fetching %s: %s", url, e)
        raise

def extract_text_candidates(soup):
    texts = []
    # 1) visible text with hints
    for t in soup.find_all(text=True):
        txt = t.strip()
        if not txt:
            continue
        lowered = txt.lower()
        if any(k in lowered for k in COUPON_HINT_WORDS) or len(txt) <= 60:
            texts.append(txt)
    # 2) attributes
    for tag in soup.find_all(True):
        for attr in ('data-coupon','data-code','value','title','alt','aria-label'):
            if tag.has_attr(attr):
                texts.append(str(tag[attr]))
        cls = " ".join(tag.get('class', []))
        if cls and re.search(r'coupon|promo|code|voucher|offer', cls, re.I):
            texts.append(tag.get_text(strip=True))
    # 3) meta tags
    for meta in soup.find_all('meta'):
        if meta.has_attr('content'):
            texts.append(meta['content'])
    # 4) JSON-LD scripts
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            j = json.loads(script.string or "{}")
            texts.append(json.dumps(j))
        except Exception:
            texts.append(script.string or "")
    # 5) inline scripts (search for token-like strings)
    for script in soup.find_all('script'):
        if not script.string:
            continue
        script_text = script.string.strip()
        # if contains 'coupon' hint, add chunk
        if 'coupon' in script_text.lower() or 'promo' in script_text.lower():
            texts.append(script_text[:400])
        else:
            # still scan for tokens matching regex
            texts.append(script_text[:200])
    return texts

def find_coupon_tokens(texts):
    found = set()
    for txt in texts:
        if not txt: continue
        for rx in TOKEN_REGEXES:
            for m in rx.findall(txt):
                if len(m) >= 4:
                    found.add(m.strip())
    return sorted(found)

# ----------------------------
# Pattern inference and generation
# ----------------------------
def pattern_from_code(code):
    out = []
    for ch in code:
        if ch.isupper(): out.append('L')
        elif ch.islower(): out.append('l')
        elif ch.isdigit(): out.append('D')
        else: out.append(ch if ch.isalnum() else 'S')
    return ''.join(out)

def infer_templates(codes):
    from collections import Counter
    templates = Counter()
    prefixes = Counter(); suffixes = Counter()
    for c in codes:
        templates[pattern_from_code(c)] += 1
        for n in (2,3,4,5):
            if len(c) > n+1:
                prefixes[c[:n]] += 1
                suffixes[c[-n:]] += 1
    top_templates = [t for t,_ in templates.most_common(8)]
    top_prefixes = [p for p,_ in prefixes.most_common(4)]
    top_suffixes = [s for s,_ in suffixes.most_common(4)]
    return top_templates, top_prefixes, top_suffixes

def generate_from_template(template, prefix=None, suffix=None, marker="-TEST"):
    import random, string
    out = []
    for ch in template:
        if ch == 'L': out.append(random.choice(string.ascii_uppercase))
        elif ch == 'l': out.append(random.choice(string.ascii_lowercase))
        elif ch == 'D': out.append(random.choice(string.digits))
        elif ch == 'S': out.append(random.choice('!@#$%&*'))
        else: out.append(ch)
    code = ''.join(out)
    if prefix: code = prefix + code
    if suffix: code = code + suffix
    return f"{code}{marker}"

# ----------------------------
# Core harvesting + storage
# ----------------------------
class Harvester:
    def __init__(self, db_path=DB_FILE, auto_export=None):
        self.found = []
        self.generated = []
        self.conn = init_db(db_path)
        self.auto_export = auto_export  # path for CSV/JSON auto-export (if provided)

    def harvest_urls(self, urls, render_js=False, delay=1.0):
        all_found = set()
        for u in urls:
            try:
                html = fetch_page(u, render_js=render_js)
                soup = BeautifulSoup(html, 'lxml')
                texts = extract_text_candidates(soup)
                tokens = find_coupon_tokens(texts)
                for t in tokens:
                    all_found.add((t, u))
                time.sleep(delay)
            except Exception as e:
                logger.exception("Error harvesting %s: %s", u, e)
        # persist
        now = datetime.utcnow().isoformat()
        c = self.conn.cursor()
        for code, src in sorted(all_found):
            self.found.append((code, src))
            c.execute("INSERT INTO found (code, source_url, discovered_at) VALUES (?, ?, ?)", (code, src, now))
        self.conn.commit()
        logger.info("Harvest complete: %d codes found", len(self.found))
        if self.auto_export:
            self.export(self.auto_export)
        return self.found

    def generate(self, template, prefix=None, suffix=None, n=20, marker='-TEST'):
        now = datetime.utcnow().isoformat()
        c = self.conn.cursor()
        for _ in range(n):
            code = generate_from_template(template, prefix=prefix, suffix=suffix, marker=marker)
            self.generated.append((code, template, now, marker))
            c.execute("INSERT INTO generated (code, template, generated_at, marker) VALUES (?, ?, ?, ?)", (code, template, now, marker))
        self.conn.commit()
        logger.info("Generated %d codes", n)
        if self.auto_export:
            self.export(self.auto_export)
        return self.generated

    def export(self, path):
        path = os.path.abspath(path)
        base, ext = os.path.splitext(path)
        if ext.lower() == '.json':
            out = {'found':[{'code':c,'source':s} for c,s in self.found],
                   'generated':[{'code':c,'template':t,'marker':m} for c,t,_,m in self.generated]}
            with open(path,'w',encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            logger.info("Exported JSON to %s", path)
        else:
            # CSV
            with open(base + '_found.csv','w',newline='',encoding='utf-8') as f:
                w = csv.writer(f); w.writerow(['code','source'])
                for c,s in self.found: w.writerow([c,s])
            with open(base + '_generated.csv','w',newline='',encoding='utf-8') as f:
                w = csv.writer(f); w.writerow(['code','template','marker'])
                for c,t,_,m in self.generated: w.writerow([c,t,m])
            logger.info("Exported CSVs to %s_found.csv and %s_generated.csv", base, base)

# ----------------------------
# CLI and GUI
# ----------------------------
def run_cli(args):
    harv = Harvester(db_path=args.db or DB_FILE, auto_export=args.export)
    urls = []
    if args.urls:
        # file with urls
        with open(args.urls,'r',encoding='utf-8') as f:
            urls = [l.strip() for l in f if l.strip()]
    if args.url:
        urls.extend(args.url)
    if not urls:
        logger.error("No URLs provided for CLI run")
        return
    found = harv.harvest_urls(urls, render_js=args.render_js, delay=args.delay)
    templates, prefixes, suffixes = infer_templates([c for c,_ in found])
    logger.info("Top templates detected: %s", templates[:5])
    logger.info("Top prefixes: %s", prefixes[:3])
    logger.info("Top suffixes: %s", suffixes[:3])
    # auto-generate if requested
    if args.auto_generate and templates:
        t = templates[0]
        n = args.generate_count or 20
        harv.generate(t, prefix=(args.prefix or prefixes[0] if prefixes else None),
                      suffix=(args.suffix or suffixes[0] if suffixes else None),
                      n=n, marker=args.marker or '-TEST')
    logger.info("CLI run finished. DB: %s", args.db or DB_FILE)

if GUI_AVAILABLE:
    class CouponHarvesterApp:
        def __init__(self, root):
            self.root = root; root.title("Coupon Harvester v2")
            self.root.geometry("980x720")
            main = ttk.Frame(root, padding=8); main.pack(fill='both',expand=True)
            # URL input
            url_frame = ttk.LabelFrame(main, text="URLs (una por línea)"); url_frame.pack(fill='x',padx=4,pady=4)
            self.url_text = tk.Text(url_frame,height=4); self.url_text.pack(fill='x',padx=4,pady=4)
            # controls
            ctrl = ttk.Frame(main); ctrl.pack(fill='x',padx=4,pady=4)
            self.fetch_btn = ttk.Button(ctrl, text="Recoger cupones ahora", command=self.start_fetch); self.fetch_btn.pack(side='left',padx=4)
            self.export_btn = ttk.Button(ctrl, text="Exportar", command=self.export_all); self.export_btn.pack(side='left',padx=4)
            self.gen_btn = ttk.Button(ctrl, text="Generar (usar template seleccionado)", command=self.generate_codes); self.gen_btn.pack(side='left',padx=4)
            # found list
            panes = ttk.Panedwindow(main, orient='horizontal'); panes.pack(fill='both',expand=True,padx=4,pady=4)
            left = ttk.Frame(panes,width=360); right = ttk.Frame(panes,width=600)
            panes.add(left,weight=1); panes.add(right,weight=3)
            ttk.Label(left, text="Encontrados:").pack(anchor='w')
            self.found_list = tk.Listbox(left,height=30); self.found_list.pack(fill='both',expand=True,padx=2,pady=2)
            # patterns & generated
            pf = ttk.LabelFrame(right, text="Patrones y generador"); pf.pack(fill='both',expand=True,padx=4,pady=4)
            ttk.Label(pf, text="Templates detectados:").pack(anchor='w')
            self.template_box = tk.Listbox(pf,height=5); self.template_box.pack(fill='x',padx=2,pady=2)
            pf2 = ttk.Frame(pf); pf2.pack(fill='x',padx=2,pady=2)
            ttk.Label(pf2, text="Prefijo:").grid(row=0,column=0,sticky='w'); self.prefix_entry = ttk.Entry(pf2); self.prefix_entry.grid(row=0,column=1,sticky='ew',padx=4)
            ttk.Label(pf2, text="Sufijo:").grid(row=1,column=0,sticky='w'); self.suffix_entry = ttk.Entry(pf2); self.suffix_entry.grid(row=1,column=1,sticky='ew',padx=4)
            pf2.columnconfigure(1, weight=1)
            gen_ctrl = ttk.Frame(pf); gen_ctrl.pack(fill='x',padx=2,pady=4)
            ttk.Label(gen_ctrl,text="Número:").pack(side='left'); self.num_spin = ttk.Spinbox(gen_ctrl, from_=1, to=2000, width=6); self.num_spin.set(20); self.num_spin.pack(side='left',padx=4)
            self.generated_list = tk.Listbox(pf,height=12); self.generated_list.pack(fill='both',expand=True,padx=2,pady=2)
            self.status = ttk.Label(main, text="Listo."); self.status.pack(fill='x',padx=4,pady=4)
            # internals
            self.harv = Harvester()
            self.found_codes = []; self.generated_codes = []

        def set_status(self, s): self.status.config(text=s); self.root.update_idletasks()

        def start_fetch(self):
            urls = [u.strip() for u in self.url_text.get("1.0","end").splitlines() if u.strip()]
            if not urls: messagebox.showwarning("Aviso","Introduce al menos una URL."); return
            self.fetch_btn.config(state='disabled')
            t = threading.Thread(target=self.fetch_worker, args=(urls,))
            t.daemon = True; t.start()

        def fetch_worker(self, urls):
            self.set_status("Recogiendo...")
            found = self.harv.harvest_urls(urls, render_js=False, delay=1.0)
            self.found_codes = [c for c,_ in found]
            self.root.after(0, self.update_ui_after_fetch)

        def update_ui_after_fetch(self):
            self.found_list.delete(0,'end')
            for c in self.found_codes: self.found_list.insert('end', c)
            templates, prefixes, suffixes = infer_templates(self.found_codes)
            self.template_box.delete(0,'end')
            for t in templates: self.template_box.insert('end', t)
            if prefixes: self.prefix_entry.delete(0,'end'); self.prefix_entry.insert(0,prefixes[0])
            if suffixes: self.suffix_entry.delete(0,'end'); self.suffix_entry.insert(0,suffixes[0])
            self.set_status(f"Encontrados {len(self.found_codes)} códigos.")
            self.fetch_btn.config(state='normal')

        def generate_codes(self):
            templates = [self.template_box.get(i) for i in range(self.template_box.size())]
            if not templates: messagebox.showwarning("Aviso","No hay templates detectados."); return
            sel = self.template_box.curselection(); template = templates[sel[0]] if sel else templates[0]
            prefix = self.prefix_entry.get().strip() or None; suffix = self.suffix_entry.get().strip() or None
            try: n = int(self.num_spin.get())
            except: n = 20
            gen = self.harv.generate(template, prefix=prefix, suffix=suffix, n=n, marker='-TEST')
            self.generated_codes = [c for c,_,_,_ in gen]
            self.generated_list.delete(0,'end')
            for c in self.generated_codes: self.generated_list.insert('end', c)
            self.set_status(f"Generados {len(self.generated_codes)} códigos.")

        def export_all(self):
            p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV",".csv"),("JSON",".json")])
            if not p: return
            self.harv.export(p)
            messagebox.showinfo("Exportado", f"Exportado a {p} (CSVs/JSON)")

# ----------------------------
# Entrypoint
# ----------------------------
def main():
    parser = argparse.ArgumentParser(description="Coupon Harvester v2")
    parser.add_argument('--no-gui', action='store_true', help='Run without GUI (CLI mode)')
    parser.add_argument('--urls', help='File with URLs, one per line (cli)')
    parser.add_argument('--url', action='append', help='Provide URL(s) directly (can repeat)')
    parser.add_argument('--export', help='Auto-export path (CSV or JSON)')
    parser.add_argument('--db', help='SQLite DB path (default in script dir)')
    parser.add_argument('--auto-generate', action='store_true', help='Automatically generate codes after harvesting')
    parser.add_argument('--generate-count', type=int, help='How many codes to generate when auto-generate is used')
    parser.add_argument('--prefix', help='Prefix to use for generation (optional)')
    parser.add_argument('--suffix', help='Suffix to use for generation (optional)')
    parser.add_argument('--marker', help='Marker appended to synthetic codes (default -TEST)')
    parser.add_argument('--render-js', action='store_true', help='Attempt JS rendering (requires selenium/playwright)')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests (seconds)')
    args = parser.parse_args()

    if args.no_gui or not GUI_AVAILABLE:
        run_cli(args)
    else:
        root = tk.Tk(); app = CouponHarvesterApp(root); root.mainloop()

if __name__ == '__main__':
    main()
