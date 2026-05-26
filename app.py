import os
import cv2
import zipfile
import threading
import tempfile
import customtkinter as ctk
from tkinter import filedialog, messagebox
import vtracer

# Настройка премиум-дизайна (Темная тема, акценты)
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class VTracerDesignerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("VectorMaster Pro | Extreme Edition")
        self.geometry("950x850")
        self.minsize(900, 800)

        self.input_file = None
        self.output_file = None

        self.build_ui()

    def build_ui(self):
        # --- ЛЕВАЯ ПАНЕЛЬ (НАСТРОЙКИ) ---
        self.sidebar = ctk.CTkScrollableFrame(self, width=500, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)

        self.add_section_header("1. ПОДГОТОВКА ИЗОБРАЖЕНИЯ")
        
        self.bw_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(self.sidebar, text="Истинный ЧБ (Сохраняет оригинальные тени)", variable=self.bw_var, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(10, 5))
        ctk.CTkLabel(self.sidebar, text="Переводит фото в идеальный монохром перед векторизацией.", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=20, pady=(0, 10))

        self.add_slider("Умное сглаживание (Denoise)", "0 = Откл. Убирает пиксельный шум JPEG, не размывая края объектов.", "blur", 0, 15, 5, is_int=True)

        self.add_section_header("2. НАРЕЗКА ИСХОДНИКА (СЕТКА)")
        self.add_slider("Разрезка по горизонтали (Строки)", "Сколько частей будет по высоте.", "rows", 1, 10, 2, is_int=True)
        self.add_slider("Разрезка по вертикали (Столбцы)", "Сколько частей будет по ширине. Итог: 2х3 = 6 файлов.", "cols", 1, 10, 3, is_int=True)

        self.add_section_header("3. ДВИЖОК ВЕКТОРИЗАЦИИ (ПРЕДЕЛ)")
        
        self.add_slider("Детализация микро-теней (Layer Diff)", 
                        "1 = ЭКСТРИМ. Каждый мельчайший оттенок создаст новый слой.\n16 = Плакатный эффект (мало цветов).", 
                        "layer_diff", 1, 32, 1, is_int=True)
        
        self.add_slider("Игнорирование пылинок (Speckle)", 
                        "0 = ЭКСТРИМ. Векторизатор обрисует даже точки размером в 1 пиксель.\n4+ = Чистый логотип без мусора.", 
                        "speckle", 0, 10, 0, is_int=True)
        
        self.add_slider("Точность изгиба кривых (Iterations)", 
                        "50 = ЭКСТРИМ. Процессор потратит в 5 раз больше времени на \nидеальное прилегание кривой к пикселю.", 
                        "iterations", 10, 100, 50, is_int=True)
        
        self.add_slider("Отрисовка микро-линий (Length)", 
                        "0.1 = ЭКСТРИМ. Захватывает черточки длиной в десятую долю пикселя.", 
                        "length", 0.1, 5.0, 0.1, is_int=False)
        
        self.add_slider("Острота углов (Corner Threshold)", 
                        "30 = ЭКСТРИМ. Углы остаются острыми.\n90 = Все углы сглаживаются в круглые формы.", 
                        "corner", 10, 90, 30, is_int=True)


        # --- ПРАВАЯ ПАНЕЛЬ (КНОПКИ И ЛОГ) ---
        self.main_view = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_view.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        self.btn_select = ctk.CTkButton(self.main_view, text="📂 ВЫБРАТЬ JPEG / JPG", font=ctk.CTkFont(size=16, weight="bold"), command=self.select_file, height=60)
        self.btn_select.pack(fill="x", pady=(0, 10))

        self.lbl_file = ctk.CTkLabel(self.main_view, text="Файл не выбран", text_color="gray", font=ctk.CTkFont(size=14))
        self.lbl_file.pack(pady=(0, 20))

        self.btn_run = ctk.CTkButton(self.main_view, text="🚀 ЗАПУСТИТЬ ВЕКТОРИЗАЦИЮ", font=ctk.CTkFont(size=16, weight="bold"), fg_color="#b30000", hover_color="#ff3333", command=self.run_process, height=60, state="disabled")
        self.btn_run.pack(fill="x", pady=10)

        self.log_box = ctk.CTkTextbox(self.main_view, font=ctk.CTkFont(family="Courier", size=13), state="disabled")
        self.log_box.pack(fill="both", expand=True, pady=(20, 0))

    # --- Элементы UI ---
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
        setattr(self, f"slider_{name}", slider)
        setattr(self, f"is_int_{name}", is_int)

    def get_val(self, name):
        val = getattr(self, f"slider_{name}").get()
        return int(val) if getattr(self, f"is_int_{name}") else float(val)

    # --- Логика ---
    def log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("JPEG", "*.jpg;*.jpeg")])
        if file_path:
            self.input_file = file_path
            self.lbl_file.configure(text=os.path.basename(file_path), text_color="white")
            self.btn_run.configure(state="normal")
            self.log(f"Загружен файл: {file_path}")

    def run_process(self):
        self.output_file = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP Archive", "*.zip")], initialfile="vector_extreme_parts.zip")
        if not self.output_file: return

        self.btn_run.configure(state="disabled")
        self.btn_select.configure(state="disabled")
        self.log("\n[СТАРТ] Вычисления запущены...")
        threading.Thread(target=self.process, daemon=True).start()

    def process(self):
        try:
            img = cv2.imread(self.input_file)
            
            if self.bw_var.get():
                self.log(">> Применяю Истинный ЧБ (сохранение светотени)...")
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            blur = self.get_val("blur")
            if blur > 0:
                self.log(f">> Сглаживание артефактов (Сила: {blur})...")
                img = cv2.bilateralFilter(img, blur, blur*5, blur*5)

            rows, cols = self.get_val("rows"), self.get_val("cols")
            h, w = img.shape[:2]
            ch_h, ch_w = h // rows, w // cols
            
            self.log(f">> Нарезаю холст на {rows*cols} частей ({rows}x{cols})...")
            
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
                        
                        cv2.imwrite(tmp_png, chunk)
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

if __name__ == "__main__":
    app = VTracerDesignerApp()
    app.mainloop()

