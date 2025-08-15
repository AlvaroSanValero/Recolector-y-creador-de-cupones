#!/usr/bin/env python3
"""
coupon_harvester.py
Recoge cupones visibles en páginas que el usuario indique, muestra los encontrados,
analiza patrones y genera cupones sintéticos marcados con -TEST para evitar uso indebido.
Funciona en Windows, Linux y macOS (requiere Python 3.8+ y dependencias).
"""

import re
import threading
import csv
import json
import random
import string
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
from bs4 import BeautifulSoup

# ----------------------------
# Ajustes
# ----------------------------
HEADERS = {
    "User-Agent": "coupon-harvester-bot/1.0 (+https://example.local/)"
}
COUPON_HINT_WORDS = [
    'coupon', 'promo', 'promocode', 'promo code', 'code:', 'code ', 'cupón', 'cupon', 'codigo', 'código', 'voucher', 'discount'
]
TOKEN_REGEXES = [
    re.compile(r'\\b[A-Z0-9]{4,20}\\b'),                # mayúsculas y dígitos
    re.compile(r'\\b[A-Za-z0-9]{4,20}\\b'),             # letras/dígitos cualquier caso
    re.compile(r'\\b[A-Z0-9]{2,6}(?:-[A-Z0-9]{2,6})+\\b') # con guiones
]

# ----------------------------
# Funciones
# ----------------------------
def fetch_page(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        raise RuntimeError(f"Error al obtener {url}: {e}")

def extract_text_candidates(soup):
    texts = []
    # Buscar textos cortos o con pistas semánticas y atributos potenciales
    candidates = soup.find_all(text=True)
    for t in candidates:
        txt = t.strip()
        if not txt:
            continue
        lowered = txt.lower()
        if any(k in lowered for k in COUPON_HINT_WORDS) or len(txt) <= 60:
            texts.append(txt)
    # atributos útiles
    for tag in soup.find_all(True):
        for attr in ('data-coupon','data-code','value','title','alt'):
            if tag.has_attr(attr):
                texts.append(str(tag[attr]))
        cls = " ".join(tag.get('class', []))
        if cls and re.search(r'coupon|promo|code|voucher', cls, re.I):
            texts.append(tag.get_text(strip=True))
    return texts

def find_coupon_tokens(texts):
    found = set()
    for txt in texts:
        for rx in TOKEN_REGEXES:
            for m in rx.findall(txt):
                if len(m) >= 4:
                    found.add(m.strip())
    return sorted(found)

def pattern_from_code(code):
    out = []
    for ch in code:
        if ch.isupper():
            out.append('L')
        elif ch.islower():
            out.append('l')
        elif ch.isdigit():
            out.append('D')
        else:
            out.append(ch if ch.isalnum() else 'S')
    return "".join(out)

def infer_templates(codes):
    from collections import Counter
    templates = Counter()
    prefix_candidates = Counter()
    suffix_candidates = Counter()
    for c in codes:
        templates[pattern_from_code(c)] += 1
        for n in (2,3,4,5):
            if len(c) > n+1:
                prefix_candidates[c[:n]] += 1
                suffix_candidates[c[-n:]] += 1
    top_templates = [t for t,_ in templates.most_common(6)]
    top_prefixes = [p for p,_ in prefix_candidates.most_common(3)]
    top_suffixes = [s for s,_ in suffix_candidates.most_common(3)]
    return top_templates, top_prefixes, top_suffixes

def generate_from_template(template, prefix=None, suffix=None, marker="-TEST"):
    out = []
    for ch in template:
        if ch == 'L':
            out.append(random.choice(string.ascii_uppercase))
        elif ch == 'l':
            out.append(random.choice(string.ascii_lowercase))
        elif ch == 'D':
            out.append(random.choice(string.digits))
        elif ch == 'S':
            out.append(random.choice("!@#$%&*"))
        else:
            out.append(ch)
    code = "".join(out)
    if prefix:
        code = prefix + code
    if suffix:
        code = code + suffix
    return f"{code}{marker}"

# ----------------------------
# GUI
# ----------------------------
class CouponHarvesterApp:
    def __init__(self, root):
        self.root = root
        root.title("Coupon Harvester & Pattern Generator")
        root.geometry("920x680")
        mainframe = ttk.Frame(root, padding="8")
        mainframe.pack(fill=tk.BOTH, expand=True)

        url_frame = ttk.LabelFrame(mainframe, text="URLs (una por línea)")
        url_frame.pack(fill=tk.X, padx=4, pady=4)
        self.url_text = tk.Text(url_frame, height=4)
        self.url_text.pack(fill=tk.X, padx=4, pady=4)

        controls = ttk.Frame(mainframe)
        controls.pack(fill=tk.X, padx=4, pady=4)
        self.fetch_btn = ttk.Button(controls, text="Recoger cupones ahora", command=self.start_fetch)
        self.fetch_btn.pack(side=tk.LEFT, padx=2)
        self.save_btn = ttk.Button(controls, text="Exportar encontrados (CSV)", command=self.export_found)
        self.save_btn.pack(side=tk.LEFT, padx=2)

        panes = ttk.Panedwindow(mainframe, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        left = ttk.Frame(panes, width=340)
        right = ttk.Frame(panes, width=560)
        panes.add(left, weight=1)
        panes.add(right, weight=2)

        ttk.Label(left, text="Cupones encontrados:").pack(anchor=tk.W)
        self.found_list = tk.Listbox(left, height=25)
        self.found_list.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.found_list.bind('<<ListboxSelect>>', self.on_select_found)

        pattern_frame = ttk.LabelFrame(right, text="Análisis de patrones / Generador")
        pattern_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        ttk.Label(pattern_frame, text="Templates detectados:").pack(anchor=tk.W)
        self.template_box = tk.Listbox(pattern_frame, height=4)
        self.template_box.pack(fill=tk.X, padx=2, pady=2)

        pf = ttk.Frame(pattern_frame)
        pf.pack(fill=tk.X, padx=2, pady=2)
        ttk.Label(pf, text="Prefijo (opcional):").grid(row=0, column=0, sticky=tk.W)
        self.prefix_entry = ttk.Entry(pf)
        self.prefix_entry.grid(row=0, column=1, sticky=tk.EW, padx=4)
        ttk.Label(pf, text="Sufijo (opcional):").grid(row=1, column=0, sticky=tk.W)
        self.suffix_entry = ttk.Entry(pf)
        self.suffix_entry.grid(row=1, column=1, sticky=tk.EW, padx=4)
        pf.columnconfigure(1, weight=1)

        gen_ctrl = ttk.Frame(pattern_frame)
        gen_ctrl.pack(fill=tk.X, padx=2, pady=4)
        ttk.Label(gen_ctrl, text="Número a generar:").pack(side=tk.LEFT)
        self.num_spin = ttk.Spinbox(gen_ctrl, from_=1, to=1000, width=6)
        self.num_spin.set(20)
        self.num_spin.pack(side=tk.LEFT, padx=4)
        self.generate_btn = ttk.Button(gen_ctrl, text="Generar códigos sintéticos (-TEST)", command=self.generate_codes)
        self.generate_btn.pack(side=tk.LEFT, padx=6)
        self.save_gen_btn = ttk.Button(gen_ctrl, text="Exportar generados (CSV)", command=self.export_generated)
        self.save_gen_btn.pack(side=tk.LEFT, padx=6)

        ttk.Label(pattern_frame, text="Códigos generados (marcados):").pack(anchor=tk.W)
        self.generated_list = tk.Listbox(pattern_frame, height=12)
        self.generated_list.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.status = ttk.Label(mainframe, text="Listo.")
        self.status.pack(fill=tk.X, padx=4, pady=4)

        self.found_codes = []
        self.generated_codes = []

    def set_status(self, text):
        self.status.config(text=text)
        self.root.update_idletasks()

    def start_fetch(self):
        urls = [u.strip() for u in self.url_text.get("1.0", tk.END).splitlines() if u.strip()]
        if not urls:
            messagebox.showwarning("Aviso", "Introduce al menos una URL.")
            return
        self.fetch_btn.config(state=tk.DISABLED)
        t = threading.Thread(target=self.fetch_worker, args=(urls,))
        t.daemon = True
        t.start()

    def fetch_worker(self, urls):
        all_found = set()
        for u in urls:
            try:
                self.set_status(f"Descargando {u} ...")
                html = fetch_page(u)
                soup = BeautifulSoup(html, "lxml")
                texts = extract_text_candidates(soup)
                tokens = find_coupon_tokens(texts)
                for t in tokens:
                    all_found.add(t)
                time.sleep(1.0)  # retraso responsable entre peticiones
            except Exception as e:
                print("Error:", e)
        self.found_codes = sorted(all_found)
        self.root.after(0, self.update_found_ui)

    def update_found_ui(self):
        self.found_list.delete(0, tk.END)
        for c in self.found_codes:
            self.found_list.insert(tk.END, c)
        self.set_status(f"Encontrados {len(self.found_codes)} cupones.")
        self.fetch_btn.config(state=tk.NORMAL)
        templates, prefixes, suffixes = infer_templates(self.found_codes)
        self.template_box.delete(0, tk.END)
        for t in templates:
            self.template_box.insert(tk.END, t)
        if prefixes:
            self.prefix_entry.delete(0, tk.END)
            self.prefix_entry.insert(0, prefixes[0])
        if suffixes:
            self.suffix_entry.delete(0, tk.END)
            self.suffix_entry.insert(0, suffixes[0])

    def on_select_found(self, evt):
        sel = self.found_list.curselection()
        if not sel:
            return
        code = self.found_list.get(sel[0])
        pat = pattern_from_code(code)
        messagebox.showinfo("Patrón detectado", f"Código: {code}\\nPatrón: {pat}")

    def generate_codes(self):
        templates = [self.template_box.get(i) for i in range(self.template_box.size())]
        if not templates:
            messagebox.showwarning("Aviso", "No hay templates detectados. Recoge cupones primero.")
            return
        sel = self.template_box.curselection()
        template = templates[sel[0]] if sel else templates[0]
        prefix = self.prefix_entry.get().strip() or None
        suffix = self.suffix_entry.get().strip() or None
        try:
            n = int(self.num_spin.get())
        except:
            n = 20
        self.generated_codes = []
        for _ in range(n):
            code = generate_from_template(template, prefix=prefix, suffix=suffix, marker="-TEST")
            self.generated_codes.append(code)
        self.generated_list.delete(0, tk.END)
        for c in self.generated_codes:
            self.generated_list.insert(tk.END, c)
        self.set_status(f"Generados {len(self.generated_codes)} códigos sintéticos (marcados con -TEST).")

    def export_found(self):
        if not self.found_codes:
            messagebox.showinfo("Info", "No hay cupones para exportar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV file","*.csv"),("JSON file","*.json")])
        if not path:
            return
        if path.endswith(".json"):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"found": self.found_codes}, f, ensure_ascii=False, indent=2)
        else:
            with open(path, "w", newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(["code"])
                for c in self.found_codes:
                    w.writerow([c])
        messagebox.showinfo("Exportado", f"Exportado a {path}")

    def export_generated(self):
        if not self.generated_codes:
            messagebox.showinfo("Info", "No hay códigos generados para exportar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV file","*.csv"),("JSON file","*.json")])
        if not path:
            return
        if path.endswith(".json"):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"generated": self.generated_codes}, f, ensure_ascii=False, indent=2)
        else:
            with open(path, "w", newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(["code","synthetic_marker"])
                for c in self.generated_codes:
                    w.writerow([c,"-TEST"])
        messagebox.showinfo("Exportado", f"Exportado a {path}")

def main():
    root = tk.Tk()
    app = CouponHarvesterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
