import os
import cv2
import zipfile
import threading
import tempfile
import numpy as np
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import vtracer

# Настройка премиум-дизайна
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class VTracerDesignerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("VectorMaster Pro | Smart AI & Preview (V2.0)")
        self.geometry("1100x850")
        self.minsize(1000, 800)

        self.input_file = None
        self.output_file = None
        self.original_cv_img = None  # Оригинальное фото для предпросмотра
        self.preview_cv_img = None   # Фото с примененными фильтрами

        self.build_ui()

    def build_ui(self):
        # --- ЛЕВАЯ ПАНЕЛЬ (ПРЕПРОЦЕССИНГ И ПРЕДПРОСМОТР) ---
        self.left_panel = ctk.CTkScrollableFrame(self, width=350, corner_radius=0)
        self.left_panel.pack(side="left", fill="y", padx=0, pady=0)

        self.add_section_header(self.left_panel, "1. ФОТО И ФИЛЬТРЫ")
        
        # Окно предпросмотра
        self.preview_canvas = ctk.CTkLabel(self.left_panel, text="Нет фото", bg_color="#2b2b2b", width=300, height=300)
        self.preview_canvas.pack(padx=20, pady=10)

        self.color_mode_var = ctk.StringVar(value="Цветное")
        self.seg_color = ctk.CTkSegmentedButton(self.left_panel, values=["Цветное", "ЧБ (Тени)", "Трафарет"], variable=self.color_mode_var, command=self.update_preview)
        self.seg_color.pack(fill="x", padx=20, pady=(10, 5))

        self.add_slider(self.left_panel, "Сглаживание шума", "blur", 0, 15, 0, True, self.update_preview)
        self.add_slider(self.left_panel, "Резкость контуров", "sharpness", 0, 5, 0, False, self.update_preview)
        self.add_slider(self.left_panel, "Контрастность", "contrast", 0.5, 3.0, 1.0, False, self.update_preview)

        # --- ЦЕНТРАЛЬНАЯ ПАНЕЛЬ (ВЕКТОРИЗАТОР) ---
        self.center_panel = ctk.CTkScrollableFrame(self, width=350, corner_radius=0)
        self.center_panel.pack(side="left", fill="y", padx=0, pady=0)

        self.add_section_header(self.center_panel, "2. ДВИЖОК ВЕКТОРА")

        self.vector_mode_var = ctk.StringVar(value="Сплайны (Плавные)")
        self.seg_mode = ctk.CTkSegmentedButton(self.center_panel, values=["Сплайны (Плавные)", "Полигоны (Углы)"], variable=self.vector_mode_var)
        self.seg_mode.pack(fill="x", padx=20, pady=(10, 20))

        self.add_slider(self.center_panel, "Детализация (Цвета/Слои)", "layer_diff", 1, 32, 1, True)
        self.add_slider(self.center_panel, "Игнорирование пылинок", "speckle", 0, 10, 0, True)
        self.add_slider(self.center_panel, "Точность изгибов (Итерации)", "iterations", 10, 100, 50, True)
        self.add_slider(self.center_panel, "Длина микро-линий", "length", 0.1, 5.0, 0.1, False)
        self.add_slider(self.center_panel, "Острота углов", "corner", 10, 90, 30, True)

        self.btn_analyze = ctk.CTkButton(self.center_panel, text="✨ ИИ-АНАЛИЗ НАСТРОЕК", fg_color="#e68a00", hover_color="#ffb333", command=self.run_analyzer, state="disabled")
        self.btn_analyze.pack(fill="x", padx=20, pady=20)

        # --- ПРАВАЯ ПАНЕЛЬ (ЭКСПОРТ) ---
        self.right_panel = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.right_panel.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        self.btn_select = ctk.CTkButton(self.right_panel, text="📂 ВЫБРАТЬ ФАЙЛ", font=ctk.CTkFont(size=16, weight="bold"), command=self.select_file, height=50)
        self.btn_select.pack(fill="x", pady=(0, 10))

        self.lbl_file = ctk.CTkLabel(self.right_panel, text="Файл не выбран", text_color="gray")
        self.lbl_file.pack(pady=(0, 20))

        self.add_section_header(self.right_panel, "3. ЭКСПОРТ (НАРЕЗКА)")
        self.add_slider(self.right_panel, "Разрезка по строкам", "rows", 1, 10, 2, True)
        self.add_slider(self.right_panel, "Разрезка по столбцам", "cols", 1, 10, 3, True)

        self.btn_run = ctk.CTkButton(self.right_panel, text="🚀 ЗАПУСТИТЬ", font=ctk.CTkFont(size=16, weight="bold"), fg_color="#b30000", hover_color="#ff3333", command=self.run_process, height=60, state="disabled")
        self.btn_run.pack(fill="x", pady=(30, 10))

        # Прогресс-бар
        self.progress = ctk.CTkProgressBar(self.right_panel)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=5)

        self.log_box = ctk.CTkTextbox(self.right_panel, font=ctk.CTkFont(family="Courier", size=12), state="disabled")
        self.log_box.pack(fill="both", expand=True, pady=(10, 0))

    def add_section_header(self, parent, title):
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color="#3399ff").pack(anchor="w", padx=20, pady=(10, 5))

    def add_slider(self, parent, title, name, min_val, max_val, default, is_int=True, callback=None):
        frame = ctk.CTkFrame(parent, fg_color="#2b2b2b", corner_radius=5)
        frame.pack(fill="x", padx=20, pady=5)
        
        lbl_title = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(weight="bold", size=12))
        lbl_title.grid(row=0, column=0, sticky="w", padx=10, pady=(5, 0))
        
        val_lbl = ctk.CTkLabel(frame, text=str(default), font=ctk.CTkFont(weight="bold", size=12), text_color="#3399ff")
        val_lbl.grid(row=0, column=1, sticky="e", padx=10, pady=(5, 0))
        
        slider = ctk.CTkSlider(frame, from_=min_val, to=max_val, number_of_steps=int((max_val-min_val)*10) if not is_int else (max_val-min_val))
        slider.set(default)
        slider.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        
        frame.columnconfigure(0, weight=1)
        
        def update_val(value):
            val_lbl.configure(text=f"{int(value) if is_int else round(value, 1)}")
            if callback: callback(value) # Вызов обновления предпросмотра
            
        slider.configure(command=update_val)
        setattr(self, f"slider_{name}", slider)
        setattr(self, f"val_lbl_{name}", val_lbl)
        setattr(self, f"is_int_{name}", is_int)

    def get_val(self, name):
        val = getattr(self, f"slider_{name}").get()
        return int(val) if getattr(self, f"is_int_{name}") else float(val)

    def set_val(self, name, value):
        getattr(self, f"slider_{name}").set(value)
        getattr(self, f"val_lbl_{name}").configure(text=f"{int(value) if getattr(self, f'is_int_{name}') else round(value, 1)}")

    def log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # --- ЛОГИКА ЧТЕНИЯ И ПРЕДПРОСМОТРА ---
    def imread_unicode(self, path):
        stream = open(path, "rb")
        bytes_array = bytearray(stream.read())
        numpy_array = np.asarray(bytes_array, dtype=np.uint8)
        img = cv2.imdecode(numpy_array, cv2.IMREAD_UNCHANGED)
        
        if img is not None:
            if len(img.shape) == 3 and img.shape[2] == 4:
                alpha_channel = img[:, :, 3] / 255.0
                rgb_channels = img[:, :, :3]
                white_bg = np.ones_like(rgb_channels, dtype=np.uint8) * 255
                img = (rgb_channels * alpha_channel[..., np.newaxis] + white_bg * (1 - alpha_channel[..., np.newaxis])).astype(np.uint8)
            elif len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        return img

    def imwrite_unicode(self, path, img_array):
        is_success, im_buf_arr = cv2.imencode(".png", img_array)
        im_buf_arr.tofile(path)

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg;*.jpeg;*.png")])
        if file_path:
            self.input_file = file_path
            self.lbl_file.configure(text=os.path.basename(file_path), text_color="white")
            self.btn_run.configure(state="normal")
            self.btn_analyze.configure(state="normal")
            
            # Загружаем оригинал для предпросмотра
            self.original_cv_img = self.imread_unicode(file_path)
            self.update_preview()
            self.log(f"[ЗАГРУЖЕНО] {os.path.basename(file_path)}")

    def update_preview(self, _=None):
        if self.original_cv_img is None: return

        # Делаем уменьшенную копию для быстрого превью (max 300x300)
        img = self.original_cv_img.copy()
        h, w = img.shape[:2]
        scale = min(300/w, 300/h)
        img_small = cv2.resize(img, (int(w*scale), int(h*scale)))

        # Применяем фильтры к превью
        img_small = self.apply_filters_to_image(img_small)

        # Конвертируем OpenCV (BGR) в формат для интерфейса (RGB -> PIL -> ImageTk)
        img_rgb = cv2.cvtColor(img_small, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(pil_img.width, pil_img.height))
        
        self.preview_canvas.configure(image=ctk_img, text="")

    def apply_filters_to_image(self, img):
        # 1. Цвет / ЧБ / Трафарет
        mode = self.color_mode_var.get()
        if mode == "ЧБ (Тени)" or mode == "Трафарет":
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if mode == "Трафарет":
                # Бинаризация (жесткий 1-bit контур)
                _, img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        # 2. Контраст
        contrast = self.get_val("contrast")
        if contrast != 1.0:
            img = cv2.convertScaleAbs(img, alpha=contrast, beta=0)

        # 3. Резкость
        sharp = self.get_val("sharpness")
        if sharp > 0:
            gaussian = cv2.GaussianBlur(img, (0, 0), sharp)
            img = cv2.addWeighted(img, 1.5, gaussian, -0.5, 0)

        # 4. Сглаживание (Denoise)
        blur = self.get_val("blur")
        if blur > 0:
            img = cv2.bilateralFilter(img, blur, blur*5, blur*5)
            
        return img

    # --- ИИ АНАЛИЗАТОР ---
    def run_analyzer(self):
        if not self.original_cv_img is None:
            self.log("[Анализ] Оцениваю шум и детализацию...")
            threading.Thread(target=self.analyze_logic, daemon=True).start()

    def analyze_logic(self):
        self.btn_analyze.configure(state="disabled")
        try:
            img = self.original_cv_img
            h, w = img.shape[:2]
            pixels = h * w
            
            # Подбор сетки
            rows, cols = (3, 4) if pixels > 16e6 else (3, 3) if pixels > 9e6 else (2, 2) if pixels > 4e6 else (1, 1)

            # Анализ шума (Дисперсия Лапласиана)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            variance = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            if variance < 300: # Логотип
                self.set_val("blur", 0)
                self.set_val("layer_diff", 16)
                self.set_val("speckle", 4)
                self.set_val("iterations", 20)
                self.vector_mode_var.set("Полигоны (Углы)")
                self.log(f"-> Тип: Плоская графика. Настройки оптимизированы.")
            elif variance < 1500: # Фото
                self.set_val("blur", 3)
                self.set_val("layer_diff", 4)
                self.set_val("speckle", 2)
                self.set_val("iterations", 40)
                self.vector_mode_var.set("Сплайны (Плавные)")
                self.log(f"-> Тип: Фотография. Настройки оптимизированы.")
            else: # Шумное фото
                self.set_val("blur", 6)
                self.set_val("sharpness", 2.0)
                self.set_val("layer_diff", 2)
                self.set_val("speckle", 1)
                self.vector_mode_var.set("Сплайны (Плавные)")
                self.log(f"-> Тип: Высоко-детализированное фото (Шум). Включены фильтры.")

            self.set_val("rows", rows)
            self.set_val("cols", cols)
            self.update_preview()
            
        finally:
            self.btn_analyze.configure(state="normal")

    # --- ЯДРО ПРОЦЕССА ВЕКТОРИЗАЦИИ ---
    def run_process(self):
        self.output_file = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP", "*.zip")], initialfile="vector_output.zip")
        if not self.output_file: return

        self.btn_run.configure(state="disabled")
        self.progress.set(0)
        self.log("\n[СТАРТ] Начинаю обработку...")
        threading.Thread(target=self.process, daemon=True).start()

    def process(self):
        try:
            img = self.original_cv_img.copy()
            
            self.log(">> 1/3 Применяю фильтры к оригиналу...")
            img = self.apply_filters_to_image(img)

            rows, cols = self.get_val("rows"), self.get_val("cols")
            total_chunks = rows * cols
            h, w = img.shape[:2]
            ch_h, ch_w = h // rows, w // cols
            
            # НАХЛЕСТ (Overlap) 5 пикселей для идеальных стыков
            overlap = 5 if total_chunks > 1 else 0
            
            self.log(f">> 2/3 Нарезка на {total_chunks} частей (с нахлестом)...")
            
            v_mode = 'polygon' if self.vector_mode_var.get() == "Полигоны (Углы)" else 'spline'
            c_mode = 'binary' if self.color_mode_var.get() == "Трафарет" else 'color'
            
            svgs = []
            with tempfile.TemporaryDirectory() as tmpdir:
                for r in range(rows):
                    for c in range(cols):
                        num = r * cols + c + 1
                        
                        y1 = max(0, r * ch_h - overlap)
                        y2 = min(h, (r + 1) * ch_h + overlap)
                        x1 = max(0, c * ch_w - overlap)
                        x2 = min(w, (c + 1) * ch_w + overlap)
                        
                        chunk = img[y1:y2, x1:x2]
                        tmp_png = os.path.join(tmpdir, f"chunk_{num}.png")
                        tmp_svg = os.path.join(tmpdir, f"part_{num}.svg")
                        
                        self.imwrite_unicode(tmp_png, chunk)
                        self.log(f"   -> Высчитываю кривые ({num}/{total_chunks})...")
                        
                        vtracer.convert_image_to_svg_py(
                            tmp_png, tmp_svg,
                            colormode=c_mode, hierarchical='stacked', mode=v_mode,
                            filter_speckle=self.get_val("speckle"),
                            color_precision=8,
                            layer_difference=self.get_val("layer_diff"),
                            corner_threshold=self.get_val("corner"),
                            length_threshold=self.get_val("length"),
                            max_iterations=self.get_val("iterations"),
                            splice_threshold=45, path_precision=8
                        )
                        svgs.append(tmp_svg)
                        self.progress.set(num / total_chunks)

                self.log(">> 3/3 Упаковка в ZIP...")
                with zipfile.ZipFile(self.output_file, 'w', zipfile.ZIP_DEFLATED) as z:
                    for svg in svgs: z.write(svg, os.path.basename(svg))

            self.log(f"[УСПЕХ] Сохранено:\n{self.output_file}")
            messagebox.showinfo("Готово", "Векторизация успешно завершена!")

        except Exception as e:
            self.log(f"[ОШИБКА] {str(e)}")
            messagebox.showerror("Ошибка", f"Сбой: {str(e)}")
            
        finally:
            self.btn_run.configure(state="normal")
            self.progress.set(1.0)

if __name__ == "__main__":
    app = VTracerDesignerApp()
    app.mainloop()


