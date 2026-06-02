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

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class HelpWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Инструкция")
        self.geometry("700x600")
        self.attributes("-topmost", True)

        textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(size=13), wrap="word")
        textbox.pack(fill="both", expand=True, padx=20, pady=20)
        
        help_text = """📘 РУКОВОДСТВО ПОЛЬЗОВАТЕЛЯ: VectorMaster Pro

Добро пожаловать! Эта программа переводит растровые картинки (фото, арты) в векторный формат (SVG) с экстремальным качеством. Чтобы файлы не "вешали" Иллюстратор, программа умеет умно нарезать результат на куски-пазлы.

--- 1. ФОТО И ФИЛЬТРЫ ---
• Цветное: Обрисовка с сохранением оригинальных цветов.
• ЧБ (Тени): Перевод в монохром. Сохраняет всю глубину света и тени (идеально для гравировок).
• Трафарет: Жесткий 1-bit режим без полутонов (только черный и белый цвет). Идеально для плоттеров.

• Сглаживание шума (Denoise): 0 = Откл. Если на фото есть пиксельный мусор, выкрутите ползунок на 5-10. Программа "замылит" мусор, но сохранит края острыми.
• Резкость контуров: Усиливает контраст на границах объектов, чтобы векторизатор точнее обвел края.
• Контрастность: Высветляет или затемняет фото перед векторизацией.

--- 2. ДВИЖОК ВЕКТОРА ---
• Сплайны / Полигоны: Сплайны делают кривые плавными. Полигоны делают формы рублеными (Low-Poly).
• Детализация (Цвета/Слои): 1 = Экстрим (каждый оттенок станет новым векторным слоем). 16+ = Плакатный эффект (мало цветов).
• Игнорирование пылинок: 0 = Экстрим (обрисует даже точку в 1 пиксель). 4+ = Чистый логотип без мусора.
• Точность изгибов (Итерации): 50 = Экстрим. Процессор потратит в 5 раз больше времени на идеальное прилегание кривой к пикселям.
• Длина микро-линий: 0.1 = Экстрим (рисует микро-черточки, поры, волоски). 2.0+ = Оставит только крупные контуры.
• Острота углов: 10 = Максимально острые углы. 90 = Все углы будут скругленными.

--- 3. ЭКСПОРТ (НАРЕЗКА) ---
Вектор 1-в-1 из фото весит сотни мегабайт. Программа разрежет холст на прямоугольники и запакует их в ZIP.
Стыки нарезаются с "нахлестом" (Overlap) в 5 пикселей, чтобы в Иллюстраторе между кусками не было щелей!
"""
        textbox.insert("0.0", help_text)
        textbox.configure(state="disabled")
        ctk.CTkButton(self, text="Закрыть", command=self.destroy).pack(pady=(0, 20))

class VTracerDesignerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("VectorMaster Pro | Loupe & AI Edition")
        self.geometry("1400x900")
        self.minsize(1200, 800)

        self.input_file = None
        self.output_file = None
        self.original_cv_img = None
        
        # Переменные для лупы и превью
        self.current_preview_size = (0, 0)
        self.loupe_active = False

        self.build_ui()

    def build_ui(self):
        self.grid_columnconfigure(0, weight=0, minsize=300)
        self.grid_columnconfigure(1, weight=1) 
        self.grid_columnconfigure(2, weight=0, minsize=350)
        self.grid_rowconfigure(0, weight=1)

        # --- ЛЕВАЯ ПАНЕЛЬ ---
        self.left_panel = ctk.CTkFrame(self, corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.btn_select = ctk.CTkButton(self.left_panel, text="📂 ВЫБРАТЬ ФАЙЛ", font=ctk.CTkFont(size=16, weight="bold"), command=self.select_file, height=50)
        self.btn_select.pack(fill="x", padx=15, pady=(20, 5))
        self.lbl_file = ctk.CTkLabel(self.left_panel, text="Файл не выбран", text_color="gray")
        self.lbl_file.pack(pady=(0, 20))

        self.add_section_header(self.left_panel, "1. ФИЛЬТРЫ (ПРЕДПРОСМОТР)")
        
        self.color_mode_var = ctk.StringVar(value="Цветное")
        self.seg_color = ctk.CTkSegmentedButton(self.left_panel, values=["Цветное", "ЧБ (Тени)", "Трафарет"], variable=self.color_mode_var, command=self.update_preview)
        self.seg_color.pack(fill="x", padx=15, pady=10)

        self.add_slider(self.left_panel, "Сглаживание шума", "blur", 0, 15, 0, True, self.update_preview)
        self.add_slider(self.left_panel, "Резкость контуров", "sharpness", 0, 5, 0, False, self.update_preview)
        self.add_slider(self.left_panel, "Контрастность", "contrast", 0.5, 3.0, 1.0, False, self.update_preview)

        self.btn_help = ctk.CTkButton(self.left_panel, text="ℹ️ Инструкция", fg_color="#4d4d4d", hover_color="#666666", command=self.show_help)
        self.btn_help.pack(fill="x", padx=15, side="bottom", pady=20)

        # --- ЦЕНТРАЛЬНАЯ ПАНЕЛЬ (ПРЕВЬЮ + ЛУПА) ---
        self.center_panel = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=10)
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.center_panel.grid_rowconfigure(0, weight=1)
        self.center_panel.grid_columnconfigure(0, weight=1)

        self.preview_canvas = ctk.CTkLabel(self.center_panel, text="Загрузите фото для предпросмотра\n(Наведите мышь для Лупы)", text_color="#4d4d4d", font=ctk.CTkFont(size=16, weight="bold"))
        self.preview_canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Плавающее окно Лупы (изначально скрыто)
        self.loupe_label = ctk.CTkLabel(self.preview_canvas, text="", fg_color="black", corner_radius=0)
        
        # Привязка событий для Лупы и Ресайза
        self.center_panel.bind("<Configure>", self.on_resize)
        self.preview_canvas.bind("<Enter>", self.show_loupe)
        self.preview_canvas.bind("<Leave>", self.hide_loupe)
        self.preview_canvas.bind("<Motion>", self.update_loupe)

        # --- ПРАВАЯ ПАНЕЛЬ ---
        self.right_panel = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)

        self.add_section_header(self.right_panel, "2. НАСТРОЙКИ ВЕКТОРА")

        self.vector_mode_var = ctk.StringVar(value="Сплайны (Плавные)")
        self.seg_mode = ctk.CTkSegmentedButton(self.right_panel, values=["Сплайны", "Полигоны"], variable=self.vector_mode_var)
        self.seg_mode.pack(fill="x", padx=15, pady=(5, 15))

        self.btn_analyze = ctk.CTkButton(self.right_panel, text="✨ ИИ-АВТОНАСТРОЙКА", fg_color="#e68a00", hover_color="#ffb333", command=self.run_analyzer, state="disabled")
        self.btn_analyze.pack(fill="x", padx=15, pady=(0, 15))

        self.add_slider(self.right_panel, "Детализация (Слои)", "layer_diff", 1, 32, 1, True)
        self.add_slider(self.right_panel, "Пылинки (Игнор)", "speckle", 0, 10, 0, True)
        self.add_slider(self.right_panel, "Точность изгибов", "iterations", 10, 100, 50, True)
        self.add_slider(self.right_panel, "Микро-линии", "length", 0.1, 5.0, 0.1, False)
        self.add_slider(self.right_panel, "Острота углов", "corner", 10, 90, 30, True)

        self.add_section_header(self.right_panel, "3. ЭКСПОРТ (НАРЕЗКА)")
        self.add_slider(self.right_panel, "Разрезка (Строки)", "rows", 1, 10, 2, True)
        self.add_slider(self.right_panel, "Разрезка (Столбцы)", "cols", 1, 10, 3, True)

        self.btn_run = ctk.CTkButton(self.right_panel, text="🚀 ЗАПУСТИТЬ", font=ctk.CTkFont(size=16, weight="bold"), fg_color="#b30000", hover_color="#ff3333", command=self.run_process, height=60, state="disabled")
        self.btn_run.pack(fill="x", padx=15, pady=(20, 10))

        self.progress = ctk.CTkProgressBar(self.right_panel)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=15, pady=5)

        self.log_box = ctk.CTkTextbox(self.right_panel, font=ctk.CTkFont(family="Courier", size=11), height=150, state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=15, pady=(10, 20))

    def show_help(self):
        HelpWindow(self)

    def add_section_header(self, parent, title):
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=13, weight="bold"), text_color="#3399ff").pack(anchor="w", padx=15, pady=(15, 5))

    def add_slider(self, parent, title, name, min_val, max_val, default, is_int=True, callback=None):
        frame = ctk.CTkFrame(parent, fg_color="#2b2b2b", corner_radius=5)
        frame.pack(fill="x", padx=15, pady=4)
        lbl_title = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(weight="bold", size=11))
        lbl_title.grid(row=0, column=0, sticky="w", padx=10, pady=(5, 0))
        val_lbl = ctk.CTkLabel(frame, text=str(default), font=ctk.CTkFont(weight="bold", size=11), text_color="#3399ff")
        val_lbl.grid(row=0, column=1, sticky="e", padx=10, pady=(5, 0))
        slider = ctk.CTkSlider(frame, from_=min_val, to=max_val, number_of_steps=int((max_val-min_val)*10) if not is_int else (max_val-min_val))
        slider.set(default)
        slider.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        
        def update_val(value):
            val_lbl.configure(text=f"{int(value) if is_int else round(value, 1)}")
            if callback: callback() 
            
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
            
            self.original_cv_img = self.imread_unicode(file_path)
            self.update_preview()
            self.log(f"[ЗАГРУЖЕНО] {os.path.basename(file_path)}")

    def on_resize(self, event):
        if self.original_cv_img is not None:
            if hasattr(self, '_resize_timer'):
                self.after_cancel(self._resize_timer)
            self._resize_timer = self.after(150, self.update_preview)

    def update_preview(self):
        if self.original_cv_img is None: return

        target_w = max(300, self.center_panel.winfo_width() - 20)
        target_h = max(300, self.center_panel.winfo_height() - 20)

        img = self.original_cv_img.copy()
        orig_h, orig_w = img.shape[:2]

        scale = min(target_w / orig_w, target_h / orig_h)
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        
        # Сохраняем текущий размер для математики Лупы
        self.current_preview_size = (new_w, new_h)

        img_small = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        img_small = self.apply_filters_to_image(img_small)

        img_rgb = cv2.cvtColor(img_small, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(new_w, new_h))
        
        self.preview_canvas.configure(image=ctk_img, text="")

    def apply_filters_to_image(self, img):
        mode = self.color_mode_var.get()
        if mode == "ЧБ (Тени)" or mode == "Трафарет":
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if mode == "Трафарет":
                _, img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        contrast = self.get_val("contrast")
        if contrast != 1.0:
            img = cv2.convertScaleAbs(img, alpha=contrast, beta=0)

        sharp = self.get_val("sharpness")
        if sharp > 0:
            gaussian = cv2.GaussianBlur(img, (0, 0), sharp)
            img = cv2.addWeighted(img, 1.5, gaussian, -0.5, 0)

        blur = self.get_val("blur")
        if blur > 0:
            img = cv2.bilateralFilter(img, blur, blur*5, blur*5)
            
        return img

    # ==========================================
    # ЛОГИКА ЛУПЫ (МАГНИФЕРА)
    # ==========================================
    def show_loupe(self, event):
        if self.original_cv_img is not None:
            self.loupe_active = True
            self.loupe_label.lift()

    def hide_loupe(self, event):
        self.loupe_active = False
        self.loupe_label.place_forget()

    def update_loupe(self, event):
        if not self.loupe_active or self.original_cv_img is None or self.current_preview_size == (0, 0): 
            return

        # Размеры
        lbl_w = self.preview_canvas.winfo_width()
        lbl_h = self.preview_canvas.winfo_height()
        img_w, img_h = self.current_preview_size

        # Поскольку картинка центрируется в Label, вычисляем отступы
        offset_x = (lbl_w - img_w) // 2
        offset_y = (lbl_h - img_h) // 2

        # Координаты мыши относительно самой картинки (а не рамки окна)
        rel_x = event.x - offset_x
        rel_y = event.y - offset_y

        # Если курсор вышел за пределы самой картинки - прячем лупу
        if rel_x < 0 or rel_x > img_w or rel_y < 0 or rel_y > img_h:
            self.loupe_label.place_forget()
            return

        # Проекцируем координаты на ОРИГИНАЛЬНОЕ High-Res фото
        orig_h, orig_w = self.original_cv_img.shape[:2]
        orig_x = int(rel_x * (orig_w / img_w))
        orig_y = int(rel_y * (orig_h / img_h))

        # Вырезаем квадрат 150x150 из оригинала
        crop_size = 150
        x1 = max(0, orig_x - crop_size // 2)
        x2 = min(orig_w, orig_x + crop_size // 2)
        y1 = max(0, orig_y - crop_size // 2)
        y2 = min(orig_h, orig_y + crop_size // 2)

        crop = self.original_cv_img[y1:y2, x1:x2].copy()

        # Если кусок получился слишком маленьким (на краю фото) - добиваем черным цветом
        if crop.shape[0] != crop_size or crop.shape[1] != crop_size:
            padded_crop = np.zeros((crop_size, crop_size, 3), dtype=np.uint8)
            padded_crop[0:crop.shape[0], 0:crop.shape[1]] = crop
            crop = padded_crop

        # Применяем фильтры (Только к этому маленькому High-Res кусочку! Это работает мгновенно)
        crop_filtered = self.apply_filters_to_image(crop)

        # Рисуем красивую синюю рамку прицела на самом куске
        cv2.rectangle(crop_filtered, (0, 0), (crop_size-1, crop_size-1), (255, 153, 51), 3) # Синий BGR
        cv2.line(crop_filtered, (crop_size//2, crop_size//2 - 10), (crop_size//2, crop_size//2 + 10), (255, 153, 51), 1)
        cv2.line(crop_filtered, (crop_size//2 - 10, crop_size//2), (crop_size//2 + 10, crop_size//2), (255, 153, 51), 1)

        # Увеличиваем кусок для эффекта "Лупы" (Zoom 1.5x)
        zoom_size = int(crop_size * 1.5)
        
        crop_rgb = cv2.cvtColor(crop_filtered, cv2.COLOR_BGR2RGB)
        pil_crop = Image.fromarray(crop_rgb)
        loupe_img = ctk.CTkImage(light_image=pil_crop, dark_image=pil_crop, size=(zoom_size, zoom_size))
        
        self.loupe_label.configure(image=loupe_img)

        # Вычисляем позицию лупы (чтобы она следовала за курсором, но не перекрывала его)
        loupe_x = event.x + 20
        loupe_y = event.y + 20

        # Если лупа упирается в край экрана, отзеркаливаем её положение
        if loupe_x + zoom_size > lbl_w:
            loupe_x = event.x - zoom_size - 20
        if loupe_y + zoom_size > lbl_h:
            loupe_y = event.y - zoom_size - 20

        self.loupe_label.place(x=loupe_x, y=loupe_y)


    # --- ИИ АНАЛИЗАТОР ---
    def run_analyzer(self):
        if not self.original_cv_img is None:
            self.log("\n[Анализ] Оцениваю шум и детализацию...")
            threading.Thread(target=self.analyze_logic, daemon=True).start()

    def analyze_logic(self):
        self.btn_analyze.configure(state="disabled")
        try:
            img = self.original_cv_img
            h, w = img.shape[:2]
            pixels = h * w
            
            rows, cols = (3, 4) if pixels > 16e6 else (3, 3) if pixels > 9e6 else (2, 2) if pixels > 4e6 else (1, 1)

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            variance = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            if variance < 300: 
                self.set_val("blur", 0)
                self.set_val("layer_diff", 16)
                self.set_val("speckle", 4)
                self.set_val("iterations", 20)
                self.vector_mode_var.set("Полигоны")
                self.log(f"-> Тип: Плоская графика. Настройки оптимизированы.")
            elif variance < 1500: 
                self.set_val("blur", 3)
                self.set_val("layer_diff", 4)
                self.set_val("speckle", 2)
                self.set_val("iterations", 40)
                self.vector_mode_var.set("Сплайны")
                self.log(f"-> Тип: Фотография. Настройки оптимизированы.")
            else: 
                self.set_val("blur", 6)
                self.set_val("sharpness", 2.0)
                self.set_val("layer_diff", 2)
                self.set_val("speckle", 1)
                self.vector_mode_var.set("Сплайны")
                self.log(f"-> Тип: Высоко-детализированное фото. Включены фильтры.")

            self.set_val("rows", rows)
            self.set_val("cols", cols)
            self.update_preview()
            
        finally:
            self.btn_analyze.configure(state="normal")

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
            
            overlap = 5 if total_chunks > 1 else 0
            
            self.log(f">> 2/3 Нарезка на {total_chunks} частей (с нахлестом)...")
            
            v_mode = 'polygon' if self.vector_mode_var.get() == "Полигоны" else 'spline'
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


