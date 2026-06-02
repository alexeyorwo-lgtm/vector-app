import os
import cv2
import zipfile
import threading
import tempfile
import numpy as np
import customtkinter as ctk
from tkinter import filedialog, messagebox
import vtracer

# Настройка премиум-дизайна
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class VTracerDesignerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("VectorMaster Pro | Smart AI Edition (Win7)")
        self.geometry("950x850")
        self.minsize(900, 800)

        self.input_file = None
        self.output_file = None

        self.build_ui()

    def build_ui(self):
        self.sidebar = ctk.CTkScrollableFrame(self, width=500, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)

        self.add_section_header("1. ПОДГОТОВКА И ЦВЕТ")
        
        self.color_mode_var = ctk.StringVar(value="Цветное (Оригинал)")
        self.seg_color = ctk.CTkSegmentedButton(self.sidebar, values=["Цветное (Оригинал)", "Истинный ЧБ"], variable=self.color_mode_var, font=ctk.CTkFont(weight="bold"))
        self.seg_color.pack(fill="x", padx=20, pady=(10, 5))
        
        ctk.CTkLabel(self.sidebar, text="В цвете программа сохранит оригинальные оттенки.\nВ ЧБ — переведет фото в монохром.", text_color="gray", font=ctk.CTkFont(size=11), justify="left").pack(anchor="w", padx=20, pady=(0, 10))
        
        self.add_slider("Умное сглаживание (Denoise)", "0 = Откл. Убирает пиксельный шум, не размывая края объектов.", "blur", 0, 15, 5, is_int=True)

        self.add_section_header("2. НАРЕЗКА ИСХОДНИКА (СЕТКА)")
        self.add_slider("Разрезка по горизонтали (Строки)", "Сколько частей будет по высоте.", "rows", 1, 10, 2, is_int=True)
        self.add_slider("Разрезка по вертикали (Столбцы)", "Сколько частей будет по ширине. Итог: 2х3 = 6 файлов.", "cols", 1, 10, 3, is_int=True)

        self.add_section_header("3. ДВИЖОК ВЕКТОРИЗАЦИИ")
        self.add_slider("Детализация оттенков (Layer Diff)", "1 = ЭКСТРИМ. Каждый мельчайший оттенок цвета создаст новый слой.\n16 = Плакатный эффект (мало цветов).", "layer_diff", 1, 32, 1, is_int=True)
        self.add_slider("Игнорирование пылинок (Speckle)", "0 = ЭКСТРИМ. Векторизатор обрисует даже точки размером в 1 пиксель.\n4+ = Чистый логотип без мусора.", "speckle", 0, 10, 0, is_int=True)
        self.add_slider("Точность изгиба кривых (Iterations)", "50 = ЭКСТРИМ. Процессор потратит в 5 раз больше времени на \nидеальное прилегание кривой к пикселю.", "iterations", 10, 100, 50, is_int=True)
        self.add_slider("Отрисовка микро-линий (Length)", "0.1 = ЭКСТРИМ. Захватывает черточки длиной в десятую долю пикселя.", "length", 0.1, 5.0, 0.1, is_int=False)
        self.add_slider("Острота углов (Corner Threshold)", "30 = ЭКСТРИМ. Углы остаются острыми.\n90 = Все углы сглаживаются в круглые формы.", "corner", 10, 90, 30, is_int=True)

        self.main_view = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_view.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        self.btn_select = ctk.CTkButton(self.main_view, text="📂 ВЫБРАТЬ JPEG / PNG", font=ctk.CTkFont(size=16, weight="bold"), command=self.select_file, height=50)
        self.btn_select.pack(fill="x", pady=(0, 10))

        self.lbl_file = ctk.CTkLabel(self.main_view, text="Файл не выбран", text_color="gray", font=ctk.CTkFont(size=14))
        self.lbl_file.pack(pady=(0, 10))

        # НОВОЕ: Кнопка Умного Анализатора
        self.btn_analyze = ctk.CTkButton(self.main_view, text="✨ АНАЛИЗИРОВАТЬ И ПОДОБРАТЬ НАСТРОЙКИ", font=ctk.CTkFont(size=13, weight="bold"), fg_color="#e68a00", hover_color="#ffb333", command=self.run_analyzer, height=40, state="disabled")
        self.btn_analyze.pack(fill="x", pady=(0, 20))

        self.btn_run = ctk.CTkButton(self.main_view, text="🚀 ЗАПУСТИТЬ ВЕКТОРИЗАЦИЮ", font=ctk.CTkFont(size=16, weight="bold"), fg_color="#b30000", hover_color="#ff3333", command=self.run_process, height=60, state="disabled")
        self.btn_run.pack(fill="x", pady=10)

        self.log_box = ctk.CTkTextbox(self.main_view, font=ctk.CTkFont(family="Courier", size=13), state="disabled")
        self.log_box.pack(fill="both", expand=True, pady=(20, 0))
        self.log("Добро пожаловать в VectorMaster Pro!\n1. Выберите файл.\n2. Нажмите 'Анализировать' для авто-настройки.\n3. Запустите векторизацию.")

    def add_section_header(self, title):
        ctk.CTkLabel(self.sidebar, text=title, font=ctk.CTkFont(size=16, weight="bold"), text_color="#3399ff").pack(anchor="w", padx=20, pady=(25, 10))

    def add_slider(self, title, desc, name, min_val, max_val, default, is_int=True):
        frame = ctk.CTkFrame(self.sidebar, fg_color="#2b2b2b", corner_radius=8)
        frame.pack(fill="x", padx=20, pady=5)
        
        lbl_title = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(weight="bold", size=13))
        lbl_title.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))
        
        val_lbl = ctk.CTkLabel(frame, text=str(default), font=ctk.CTkFont(weight="bold", size=14), text_color="#3399ff")
        val_lbl.grid(row=0, column=1, sticky="e", padx=10, pady=(10, 0))
        
        lbl_desc = ctk.CTkLabel(frame, text=desc, font=ctk.CTkFont(size=11), text_color="gray", justify="left")
        lbl_desc.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 5))
        
        slider = ctk.CTkSlider(frame, from_=min_val, to=max_val, number_of_steps=int((max_val-min_val)*10) if not is_int else (max_val-min_val))
        slider.set(default)
        slider.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(5, 15))
        
        frame.columnconfigure(0, weight=1)
        
        def update_val(value):
            val_lbl.configure(text=f"{int(value) if is_int else round(value, 1)}")
            
        slider.configure(command=update_val)
        
        # Сохраняем ссылки для авто-обновления анализатором
        setattr(self, f"slider_{name}", slider)
        setattr(self, f"val_lbl_{name}", val_lbl)
        setattr(self, f"is_int_{name}", is_int)

    def get_val(self, name):
        val = getattr(self, f"slider_{name}").get()
        return int(val) if getattr(self, f"is_int_{name}") else float(val)

    def set_val(self, name, value):
        slider = getattr(self, f"slider_{name}")
        lbl = getattr(self, f"val_lbl_{name}")
        is_int = getattr(self, f"is_int_{name}")
        
        slider.set(value)
        lbl.configure(text=f"{int(value) if is_int else round(value, 1)}")

    def log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg;*.jpeg;*.png")])
        if file_path:
            self.input_file = file_path
            self.lbl_file.configure(text=os.path.basename(file_path), text_color="white")
            self.btn_run.configure(state="normal")
            self.btn_analyze.configure(state="normal")
            self.log(f"\n[ЗАГРУЖЕНО] {os.path.basename(file_path)}")

    # НОВОЕ: Логика Анализатора
    def run_analyzer(self):
        if not self.input_file: return
        self.log("\n[ИИ-АНАЛИЗ] Сканирую пиксели и шум...")
        threading.Thread(target=self.analyze_logic, daemon=True).start()

    def analyze_logic(self):
        try:
            self.btn_analyze.configure(state="disabled")
            img = self.imread_unicode(self.input_file)
            h, w = img.shape[:2]
            pixels = h * w
            
            # 1. Анализ разрешения (подбор сетки)
            if pixels > 16_000_000: # Больше 16 МП
                rows, cols = 3, 4
            elif pixels > 9_000_000: # Больше 9 МП
                rows, cols = 3, 3
            elif pixels > 4_000_000: # Больше 4 МП
                rows, cols = 2, 2
            else:
                rows, cols = 1, 1

            # 2. Математический анализ деталей (Laplacian Variance)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            variance = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            self.log(f" -> Разрешение: {w}x{h} ({pixels/1_000_000:.1f} Мегапикселей)")
            self.log(f" -> Коэффициент шума/деталей: {variance:.0f}")

            # 3. Выбор архетипа
            if variance < 300:
                img_type = "Плоская графика / Логотип"
                blur, layer, speckle, iters, length, corner = 0, 16, 4, 15, 1.5, 60
            elif variance < 1500:
                img_type = "Стандартное фото / Арт"
                blur, layer, speckle, iters, length, corner = 2, 8, 2, 30, 0.5, 45
            else:
                img_type = "Шумное фото / Ультра-детали"
                blur, layer, speckle, iters, length, corner = 5, 4, 1, 50, 0.2, 30

            self.log(f" -> Определен тип: {img_type}")

            # Применяем настройки к ползункам в интерфейсе
            self.set_val("rows", rows)
            self.set_val("cols", cols)
            self.set_val("blur", blur)
            self.set_val("layer_diff", layer)
            self.set_val("speckle", speckle)
            self.set_val("iterations", iters)
            self.set_val("length", length)
            self.set_val("corner", corner)

            self.log("[УСПЕХ] Настройки автоматически адаптированы!\nМожете запускать векторизацию.")
            
        except Exception as e:
            self.log(f"[ОШИБКА АНАЛИЗА] {e}")
        finally:
            self.btn_analyze.configure(state="normal")


    def imread_unicode(self, path):
        stream = open(path, "rb")
        bytes_array = bytearray(stream.read())
        numpy_array = np.asarray(bytes_array, dtype=np.uint8)
        img = cv2.imdecode(numpy_array, cv2.IMREAD_UNCHANGED)
        
        if img is not None:
            if len(img.shape) == 3 and img.shape[2] == 4:
                alpha_channel = img[:, :, 3] / 255.0
                rgb_channels = img[:, :, :3]
                white_background = np.ones_like(rgb_channels, dtype=np.uint8) * 255
                img = (rgb_channels * alpha_channel[..., np.newaxis] + white_background * (1 - alpha_channel[..., np.newaxis])).astype(np.uint8)
            elif len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        return img

    def imwrite_unicode(self, path, img_array):
        is_success, im_buf_arr = cv2.imencode(".png", img_array)
        im_buf_arr.tofile(path)

    def run_process(self):
        self.output_file = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP Archive", "*.zip")], initialfile="vector_extreme_parts.zip")
        if not self.output_file: return

        self.btn_run.configure(state="disabled")
        self.btn_select.configure(state="disabled")
        self.btn_analyze.configure(state="disabled")
        self.log("\n[СТАРТ] Вычисления запущены...")
        threading.Thread(target=self.process, daemon=True).start()

    def process(self):
        try:
            img = self.imread_unicode(self.input_file)
            if img is None: raise Exception("Не удалось прочитать изображение.")
            
            if self.color_mode_var.get() == "Истинный ЧБ":
                self.log(">> Режим: ЧЕРНО-БЕЛОЕ (монохром)...")
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            blur = self.get_val("blur")
            if blur > 0:
                self.log(f">> Сглаживание (Сила: {blur})...")
                img = cv2.bilateralFilter(img, blur, blur*5, blur*5)

            rows, cols = self.get_val("rows"), self.get_val("cols")
            h, w = img.shape[:2]
            ch_h, ch_w = h // rows, w // cols
            
            self.log(f">> Нарезаю на {rows*cols} частей ({rows}x{cols})...")
            
            svgs = []
            with tempfile.TemporaryDirectory() as tmpdir:
                for r in range(rows):
                    for c in range(cols):
                        num = r * cols + c + 1
                        y1, y2 = r * ch_h, h if r == rows - 1 else (r + 1) * ch_h
                        x1, x2 = c * ch_w, w if c == cols - 1 else (c + 1) * ch_w
                        
                        chunk = img[y1:y2, x1:x2]
                        tmp_png = os.path.join(tmpdir, f"chunk_{num}.png")
                        tmp_svg = os.path.join(tmpdir, f"part_{num}.svg")
                        
                        self.imwrite_unicode(tmp_png, chunk)
                        self.log(f"   -> Высчитываю сплайны для куска {num} из {rows*cols}...")
                        
                        vtracer.convert_image_to_svg_py(
                            tmp_png, tmp_svg,
                            colormode='color', hierarchical='stacked', mode='spline',
                            filter_speckle=self.get_val("speckle"),
                            color_precision=8,
                            layer_difference=self.get_val("layer_diff"),
                            corner_threshold=self.get_val("corner"),
                            length_threshold=self.get_val("length"),
                            max_iterations=self.get_val("iterations"),
                            splice_threshold=45, path_precision=8
                        )
                        svgs.append(tmp_svg)

                self.log(">> Упаковываю векторные файлы в ZIP архив...")
                with zipfile.ZipFile(self.output_file, 'w', zipfile.ZIP_DEFLATED) as z:
                    for svg in svgs: z.write(svg, os.path.basename(svg))

            self.log(f"\n[УСПЕХ] Файл сохранен:\n{self.output_file}")
            messagebox.showinfo("Готово", "Векторизация успешно завершена!")

        except Exception as e:
            self.log(f"\n[ОШИБКА] {str(e)}")
            messagebox.showerror("Ошибка", f"Сбой:\n{str(e)}")
            
        finally:
            self.btn_run.configure(state="normal")
            self.btn_select.configure(state="normal")
            self.btn_analyze.configure(state="normal")

if __name__ == "__main__":
    app = VTracerDesignerApp()
    app.mainloop()

