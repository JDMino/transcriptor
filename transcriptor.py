import gc
import json
import shutil
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import av
from faster_whisper import WhisperModel
from huggingface_hub.constants import HF_HUB_CACHE

# nombre: tamaño aproximado en MB
MODELOS = {"tiny": 75, "base": 145, "small": 465,
           "medium": 1500, "large-v3": 3000}

# segundos de proceso por segundo de video (CPU, valores iniciales aprox.)
FACTORES_BASE = {"tiny": 0.1, "base": 0.2, "small": 0.5,
                 "medium": 1.5, "large-v3": 3.0}
ARCHIVO_FACTORES = Path.home() / ".transcriptor_factores.json"


# ---------- Utilidades ----------
def carpeta_modelo(nombre):
    return Path(HF_HUB_CACHE) / f"models--Systran--faster-whisper-{nombre}"


def esta_descargado(nombre):
    return any(carpeta_modelo(nombre).glob("snapshots/*/model.bin"))


def cargar_factores():
    factores = dict(FACTORES_BASE)
    try:
        factores.update(json.loads(ARCHIVO_FACTORES.read_text()))
    except Exception:
        pass
    return factores


def duracion_video(ruta):
    try:
        with av.open(ruta) as c:
            return c.duration / av.time_base if c.duration else None
    except Exception:
        return None


def fmt(seg):
    seg = int(round(seg))
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h} h {m} min"
    if m:
        return f"{m} min {s} s"
    return f"{s} s"


def fmt_mb(mb):
    return f"{mb} MB" if mb < 1000 else f"{mb / 1000:.1f} GB"


# ---------- Aplicación ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video → Transcripción")
        self.geometry("620x360")
        self.resizable(False, False)

        self.video = None
        self.duracion = None
        self.modelo = None
        self.modelo_cargado = None
        self.ocupado = False
        self.t0 = 0
        self.factores = cargar_factores()

        self.lbl = ttk.Label(self, text="Ningún video seleccionado",
                             wraplength=580)
        self.lbl.pack(pady=(16, 4))
        self.btn_cargar = ttk.Button(self, text="Cargar video…",
                                     command=self.elegir)
        self.btn_cargar.pack()
        self.lbl_dur = ttk.Label(self, text="")
        self.lbl_dur.pack()

        marco = ttk.Frame(self)
        marco.pack(pady=12)
        ttk.Label(marco, text="Modelo:").grid(row=0, column=0, padx=4)
        self.combo = ttk.Combobox(marco, state="readonly", width=40,
                                  values=[self.etiqueta(n) for n in MODELOS])
        self.combo.current(2)  # 'small' por defecto
        self.combo.grid(row=0, column=1, padx=4)
        self.combo.bind("<<ComboboxSelected>>",
                        lambda e: self.actualizar_ui())
        self.btn_borrar = ttk.Button(marco, text="Borrar modelo",
                                     command=self.borrar)
        self.btn_borrar.grid(row=0, column=2, padx=4)

        self.lbl_est = ttk.Label(self, text="")
        self.lbl_est.pack(pady=4)

        self.btn = ttk.Button(self, text="Transcribir", command=self.iniciar)
        self.btn.pack(pady=8)

        self.bar = ttk.Progressbar(self, mode="determinate",
                                   length=440, maximum=100)
        self.bar.pack()
        self.estado = ttk.Label(self, text="")
        self.estado.pack(pady=6)

        self.actualizar_ui()

    # ---------- Modelos ----------
    def etiqueta(self, nombre):
        estado = "✔ descargado" if esta_descargado(nombre) \
            else "⬇ no descargado"
        return f"{nombre} · {fmt_mb(MODELOS[nombre])} · {estado}"

    def modelo_sel(self):
        return list(MODELOS)[self.combo.current()]

    def refrescar_combo(self):
        actual = self.combo.current()
        if actual < 0:
            actual = 2
        self.combo["values"] = [self.etiqueta(n) for n in MODELOS]
        self.combo.current(actual)
        self.actualizar_ui()

    def borrar(self):
        nombre = self.modelo_sel()
        if not messagebox.askyesno(
                "Borrar modelo",
                f"¿Borrar el modelo '{nombre}' "
                f"(~{fmt_mb(MODELOS[nombre])})?\n"
                "Habrá que descargarlo de nuevo para usarlo."):
            return
        if self.modelo_cargado == nombre:
            self.modelo = None
            self.modelo_cargado = None
            gc.collect()
        try:
            shutil.rmtree(carpeta_modelo(nombre))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo borrar:\n{e}")
        self.refrescar_combo()

    # ---------- UI ----------
    def actualizar_ui(self):
        descargado = esta_descargado(self.modelo_sel())
        self.btn_borrar.config(
            state="normal" if descargado and not self.ocupado else "disabled")
        self.btn.config(
            state="normal" if self.video and not self.ocupado else "disabled")
        self.combo.config(state="disabled" if self.ocupado else "readonly")
        self.actualizar_estimado()

    def actualizar_estimado(self):
        if self.ocupado:
            return
        if not self.video:
            texto = "Tiempo estimado: cargá un video para calcularlo"
        elif not self.duracion:
            texto = "No se pudo leer la duración del video"
        else:
            nombre = self.modelo_sel()
            seg = self.duracion * self.factores[nombre]
            texto = f"Tiempo estimado con '{nombre}': ≈ {fmt(seg)}"
            if not esta_descargado(nombre):
                texto += " (+ descarga del modelo)"
        self.lbl_est.config(text=texto)

    def elegir(self):
        ruta = filedialog.askopenfilename(
            filetypes=[("Video", "*.mp4 *.mkv *.avi *.mov *.webm"),
                       ("Todos", "*.*")])
        if not ruta:
            return
        self.video = ruta
        self.duracion = duracion_video(ruta)
        self.lbl.config(text=Path(ruta).name)
        self.lbl_dur.config(
            text=f"Duración: {fmt(self.duracion)}" if self.duracion else "")
        self.bar["value"] = 0
        self.estado.config(text="")
        self.actualizar_ui()

    def iniciar(self):
        self.ocupado = True
        self.btn_cargar.config(state="disabled")
        self.bar["value"] = 0
        self.actualizar_ui()
        threading.Thread(target=self.trabajar, args=(self.modelo_sel(),),
                         daemon=True).start()

    def modo_carga(self, nombre):
        self.bar.config(mode="indeterminate")
        self.bar.start(12)
        if esta_descargado(nombre):
            self.estado.config(text=f"Cargando modelo '{nombre}'…")
        else:
            self.estado.config(
                text=f"Descargando modelo '{nombre}' "
                     f"(~{fmt_mb(MODELOS[nombre])})…")
        self.lbl_est.config(text="")

    def modo_progreso(self):
        self.bar.stop()
        self.bar.config(mode="determinate", value=0)
        self.estado.config(text="Transcribiendo… 0%")

    def set_progreso(self, pct):
        self.bar["value"] = pct
        texto = f"Transcribiendo… {pct:.0f}%"
        if pct >= 3:
            transcurrido = time.time() - self.t0
            restante = transcurrido / pct * (100 - pct)
            texto += f" · restante ≈ {fmt(restante)}"
        self.estado.config(text=texto)

    def terminar(self, salida, error):
        self.bar.stop()
        self.bar.config(mode="determinate")
        self.ocupado = False
        self.btn_cargar.config(state="normal")
        if error:
            self.bar["value"] = 0
            self.estado.config(text="Error")
            messagebox.showerror("Error", error)
        else:
            self.bar["value"] = 100
            self.estado.config(text="Listo ✔")
            messagebox.showinfo("Listo", f"Guardado en:\n{salida}")
        self.refrescar_combo()

    # ---------- Trabajo pesado (hilo aparte) ----------
    def trabajar(self, nombre):
        try:
            if self.modelo_cargado != nombre:
                self.after(0, self.modo_carga, nombre)
                self.modelo = None  # libera el anterior
                self.modelo_cargado = None
                gc.collect()
                self.modelo = WhisperModel(nombre, device="cpu",
                                           compute_type="int8")
                self.modelo_cargado = nombre
                self.after(0, self.refrescar_combo)

            segmentos, info = self.modelo.transcribe(
                self.video, vad_filter=True)
            total = info.duration or 1
            self.t0 = time.time()
            self.after(0, self.modo_progreso)

            lineas = []
            for s in segmentos:
                lineas.append(s.text.strip())
                self.after(0, self.set_progreso,
                           min(100, s.end / total * 100))

            # Autocalibración del factor de velocidad
            medido = (time.time() - self.t0) / total
            self.factores[nombre] = 0.5 * self.factores[nombre] + 0.5 * medido
            try:
                ARCHIVO_FACTORES.write_text(json.dumps(self.factores))
            except Exception:
                pass

            salida = Path(self.video).with_suffix(".txt")
            salida.write_text("\n".join(lineas), encoding="utf-8")
            self.after(0, self.terminar, str(salida), None)
        except Exception as e:
            self.after(0, self.terminar, None, str(e))


if __name__ == "__main__":
    App().mainloop()
