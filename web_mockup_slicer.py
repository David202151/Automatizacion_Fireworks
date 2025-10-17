import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from PIL import Image, ImageTk, ImageDraw
import shutil
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import io

class ManualWebSlicer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sistema Manual de Recortes Web con Cloudflare R2")
        
        # Obtener el tamaño de la pantalla
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Establecer el tamaño de la ventana
        window_width = int(screen_width * 0.85)
        window_height = int(screen_height * 0.85)
        
        # Centrar la ventana
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Variables de instancia
        self.mockup_path = None
        self.mockup_image = None
        self.photo_image = None
        self.slices = []
        self.output_folder = "output"
        self.custom_output_name = None
        self.images_folder = os.path.join(self.output_folder, "images")
        
        # Variables de configuración
        self.platform = tk.StringVar(value="braze")
        self.header_type = tk.StringVar(value="name_miles")
        self.brand = tk.StringVar(value="clubmiles")
        self.campaign_type = tk.StringVar(value="redencion")
        self.preheader_text = tk.StringVar(value="")
        self.upload_to_r2 = tk.BooleanVar(value=True)
        
        # NUEVA VARIABLE: Versión de template para ClubMiles
        self.template_version = tk.StringVar(value="v1")  # v1 = normal, v2 = plomo
        
        # Configuración de Cloudflare R2
        self.r2_config = {
            "access_key_id": "fcf42625ad735ad63da22100af72e684",
            "secret_access_key": "b304706b40e5544fbc4a50c543e2ba66f5f41595c69afa1b56097dc2fce5db2a",
            "endpoint": "https://95f977894b55126e9809447b9bd1fa20.r2.cloudflarestorage.com",
            "bucket_name": "icare"
        }
        
        # URLs base para cada marca y tipo
        self.r2_base_urls = {
            "clubmiles": {
                "activacion": "images/CME/ACTIVACION/",
                "redencion": "images/CME/"
            },
            "bgr": {
                "activacion": "images/BGR/ACTIVACION/",
                "redencion": "images/BGR/"
            },
            "discover": {
                "redencion": "images/DISCOVER/"
            }
        }
        
        # URLs públicas correspondientes
        self.public_base_urls = {
            "clubmiles": {
                "activacion": "https://content.miles.com.ec/images/CME/ACTIVACION/",
                "redencion": "https://content.miles.com.ec/images/CME/"
            },
            "bgr": {
                "activacion": "https://content.miles.com.ec/images/BGR/ACTIVACION/",
                "redencion": "https://content.miles.com.ec/images/BGR/"
            },
            "discover": {
                "redencion": "https://content.miles.com.ec/images/DISCOVER/"
            }
        }
        
        # Cliente S3 para R2
        self.s3_client = None
        
        # Variables para herramienta de recorte optimizada
        self.slice_tool_active = True
        self.drawing = False
        self.start_x = None
        self.start_y = None
        self.current_x = None
        self.current_y = None
        self.preview_rect = None
        self.preview_overlay = None
        
        # Variables para edición
        self.dragging = False
        self.drag_data = {"item": None, "x": 0, "y": 0, "edge": None}
        self.selected_slice = None
        
        # Variables para zoom y optimización
        self.zoom_factor = 1.0
        self.snap_threshold = 3
        self.guide_lines = []
        self.smart_guides = []
        
        # Optimización de rendimiento
        self.last_update_time = 0
        self.update_delay = 16
        self.pending_update = None
        
        # Variables para vista previa en tiempo real
        self.preview_image = None
        self.show_preview = True
        
        # URLs fijas para redes sociales
        self.social_urls = {
            "facebook": "https://www.facebook.com/ClubMiles/",
            "instagram": "https://instagram.com/clubmiles_ec?igshid=YmMyMTA2M2Y=",
            "whatsapp": "https://wa.me/593963040040",
            "youtube": "https://www.youtube.com/channel/UCJ5qTUrByNb6u9XiQ39xmHA"
        }
        
        # URLs para Discover
        self.discover_social_urls = {
            "twitter": "https://twitter.com/discoverecu?s=21&t=RhDLOB1Gi5VRakyuwoiC8g",
            "facebook": "https://www.facebook.com/DiscoverEC?mibextid=LQQJ4d",
            "instagram": "https://www.instagram.com/discover_ec?igsh=MWdjc3g1NmVuaTA2Nw==",
            "youtube": "https://www.youtube.com/@DiscoverEcuador"
        }
        
        self.setup_ui()
        self.init_r2_client()
        
    def init_r2_client(self):
        """Inicializa el cliente de Cloudflare R2"""
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.r2_config["endpoint"],
                aws_access_key_id=self.r2_config["access_key_id"],
                aws_secret_access_key=self.r2_config["secret_access_key"],
                region_name='auto'
            )
            print("✅ Cliente R2 inicializado correctamente")
        except Exception as e:
            print(f"❌ Error inicializando cliente R2: {e}")
            self.upload_to_r2.set(False)
    
    def setup_ui(self):
        # Frame principal
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Frame superior para controles
        top_frame = ttk.Frame(main_container)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Controles superiores
        controls_row = ttk.Frame(top_frame)
        controls_row.pack(fill=tk.X)
        
        ttk.Button(controls_row, text="📁 Cargar Imagen", 
                  command=self.load_image).pack(side=tk.LEFT, padx=5)
        
        # Separador visual
        ttk.Separator(controls_row, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        # Herramientas
        ttk.Label(controls_row, text="Herramientas:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(5, 5))
        
        # Botón de herramienta de recorte
        self.slice_tool_btn = tk.Button(controls_row, text="🗄️ Recorte", 
                                       bg="#4CAF50", fg="white", font=("Arial", 9, "bold"),
                                       relief=tk.RAISED, command=self.toggle_slice_tool)
        self.slice_tool_btn.pack(side=tk.LEFT, padx=2)
        
        # Vista previa en tiempo real
        self.preview_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls_row, text="Vista previa", 
                       variable=self.preview_var).pack(side=tk.LEFT, padx=5)
        
        # Controles de zoom
        ttk.Separator(controls_row, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        ttk.Label(controls_row, text="Zoom:").pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(controls_row, text="🔍+", command=self.zoom_in).pack(side=tk.LEFT, padx=1)
        ttk.Button(controls_row, text="🔍-", command=self.zoom_out).pack(side=tk.LEFT, padx=1)
        ttk.Button(controls_row, text="100%", command=self.zoom_reset).pack(side=tk.LEFT, padx=1)
        
        self.zoom_label = ttk.Label(controls_row, text="100%", font=("Arial", 9, "bold"))
        self.zoom_label.pack(side=tk.LEFT, padx=5)
        
        # Opciones
        ttk.Separator(controls_row, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        self.show_guides_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls_row, text="Guías", 
                       variable=self.show_guides_var).pack(side=tk.LEFT, padx=5)
        
        # Carpeta de salida
        ttk.Separator(controls_row, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        ttk.Label(controls_row, text="Salida:").pack(side=tk.LEFT, padx=(5, 5))
        self.output_name_var = tk.StringVar(value="output")
        ttk.Entry(controls_row, textvariable=self.output_name_var, width=15).pack(side=tk.LEFT)
        ttk.Button(controls_row, text="OK", command=self.set_output_folder).pack(side=tk.LEFT, padx=2)
        
        # Configuración
        config_frame = ttk.LabelFrame(top_frame, text="Configuración del Boletín", padding="5")
        config_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Primera fila: Marca y Tipo de campaña
        ttk.Label(config_frame, text="Marca:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Radiobutton(config_frame, text="ClubMiles", variable=self.brand, 
                       value="clubmiles", command=self.on_brand_change).grid(row=0, column=1)
        ttk.Radiobutton(config_frame, text="BGR", variable=self.brand, 
                       value="bgr", command=self.on_brand_change).grid(row=0, column=2)
        ttk.Radiobutton(config_frame, text="Discover", variable=self.brand, 
                       value="discover", command=self.on_brand_change).grid(row=0, column=3)
        
        # Tipo de campaña
        ttk.Label(config_frame, text="Tipo:").grid(row=0, column=4, sticky=tk.W, padx=(20, 5))
        self.activation_radio = ttk.Radiobutton(config_frame, text="Activación", variable=self.campaign_type, 
                       value="activacion", command=self.on_campaign_type_change)
        self.activation_radio.grid(row=0, column=5)
        self.redemption_radio = ttk.Radiobutton(config_frame, text="Redención", variable=self.campaign_type, 
                       value="redencion", command=self.on_campaign_type_change)
        self.redemption_radio.grid(row=0, column=6)
        
        # Versión de template (SOLO para ClubMiles)
        ttk.Label(config_frame, text="Template:").grid(row=0, column=7, sticky=tk.W, padx=(20, 5))
        self.template_v1_radio = ttk.Radiobutton(config_frame, text="V1 (Normal)", 
                                                 variable=self.template_version, 
                                                 value="v1")
        self.template_v1_radio.grid(row=0, column=8)
        self.template_v2_radio = ttk.Radiobutton(config_frame, text="V2 (Plomo)", 
                                                 variable=self.template_version, 
                                                 value="v2")
        self.template_v2_radio.grid(row=0, column=9)
        
        # Segunda fila: Plataforma y Header
        ttk.Label(config_frame, text="Plataforma:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=(5,0))
        ttk.Radiobutton(config_frame, text="Braze", variable=self.platform, 
                       value="braze", command=self.on_platform_change).grid(row=1, column=1, pady=(5,0))
        ttk.Radiobutton(config_frame, text="Mautic", variable=self.platform, 
                       value="mautic", command=self.on_platform_change).grid(row=1, column=2, pady=(5,0))
        
        ttk.Label(config_frame, text="Header:").grid(row=1, column=4, sticky=tk.W, padx=(20, 5), pady=(5,0))
        self.header_name_only_radio = ttk.Radiobutton(config_frame, text="Solo nombre", variable=self.header_type, 
                       value="name_only")
        self.header_name_only_radio.grid(row=1, column=5, pady=(5,0))
        self.header_name_miles_radio = ttk.Radiobutton(config_frame, text="Nombre y millas", variable=self.header_type, 
                       value="name_miles")
        self.header_name_miles_radio.grid(row=1, column=6, pady=(5,0))
        
        # Tercera fila: Subida a R2
        ttk.Checkbutton(config_frame, text="☁️ Subir imágenes a Cloudflare R2", 
                       variable=self.upload_to_r2).grid(row=2, column=0, columnspan=3, pady=(5,0))
        
        self.r2_status_label = ttk.Label(config_frame, text="", foreground="green")
        self.r2_status_label.grid(row=2, column=3, columnspan=7, sticky=tk.W, padx=5, pady=(5,0))
        
        # Frame para Preheader (solo visible cuando es Mautic)
        self.preheader_frame = ttk.LabelFrame(top_frame, text="Preheader (Mautic)", padding="5")
        self.preheader_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(self.preheader_frame, text="Texto del Preheader:").pack(side=tk.LEFT, padx=5)
        self.preheader_entry = ttk.Entry(self.preheader_frame, textvariable=self.preheader_text, width=60)
        self.preheader_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Ocultar preheader frame inicialmente si no es Mautic
        if self.platform.get() != "mautic":
            self.preheader_frame.pack_forget()
        
        # Frame del medio para canvas y panel
        middle_frame = ttk.Frame(main_container)
        middle_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Canvas con su frame
        canvas_frame = ttk.Frame(middle_frame)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Instrucciones
        info_frame = ttk.Frame(canvas_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))
        
        instructions = ("🗄️ HERRAMIENTA DE RECORTE ACTIVADA | Arrastra para crear | "
                       "Vista previa EN TIEMPO REAL | Snap automático")
        self.instruction_label = ttk.Label(info_frame, text=instructions,
                                          font=("Arial", 9), foreground="#2E7D32")
        self.instruction_label.pack()
        
        # Info de coordenadas en tiempo real
        self.coord_label = ttk.Label(info_frame, text="Posición: -- | Tamaño: -- | FPS: --", 
                                    font=("Arial", 8), foreground="#666")
        self.coord_label.pack()
        
        # Frame contenedor para canvas y scrollbars
        canvas_container = ttk.Frame(canvas_frame)
        canvas_container.pack(fill=tk.BOTH, expand=True)
        
        # Canvas optimizado
        self.canvas = tk.Canvas(canvas_container, bg="#E8E8E8", cursor="crosshair", 
                               width=700, height=500, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(canvas_container, orient=tk.VERTICAL, command=self.canvas.yview)
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        h_scrollbar = ttk.Scrollbar(canvas_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.E, tk.W))
        
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)
        
        # Eventos del canvas
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<Button-3>", self.on_right_click)
        
        # Zoom y scroll
        self.canvas.bind("<Control-MouseWheel>", self.on_zoom_wheel)
        self.canvas.bind("<Control-Button-4>", self.on_zoom_wheel)
        self.canvas.bind("<Control-Button-5>", self.on_zoom_wheel)
        self.canvas.bind("<MouseWheel>", self.on_scroll_wheel)
        self.canvas.bind("<Button-4>", self.on_scroll_wheel)
        self.canvas.bind("<Button-5>", self.on_scroll_wheel)
        
        # Atajos de teclado
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())
        self.root.bind("<Control-0>", lambda e: self.zoom_reset())
        self.root.bind("<Delete>", lambda e: self.delete_selected_slice())
        self.root.bind("<Escape>", lambda e: self.deselect_all())
        
        # Panel derecho
        right_frame = ttk.Frame(middle_frame, width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_frame.pack_propagate(False)
        
        # Panel de recortes
        slice_panel = ttk.LabelFrame(right_frame, text="🗄️ Recortes Web", padding="5")
        slice_panel.pack(fill=tk.BOTH, expand=True)
        
        # Lista de recortes
        list_frame = ttk.Frame(slice_panel)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("Nombre", "Pos", "Tamaño")
        self.slice_tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=8)
        
        self.slice_tree.heading("#0", text="", anchor=tk.W)
        self.slice_tree.heading("Nombre", text="Nombre", anchor=tk.W)
        self.slice_tree.heading("Pos", text="X,Y", anchor=tk.W)
        self.slice_tree.heading("Tamaño", text="W×H", anchor=tk.W)
        
        self.slice_tree.column("#0", width=30, minwidth=30)
        self.slice_tree.column("Nombre", width=80, minwidth=60)
        self.slice_tree.column("Pos", width=60, minwidth=50)
        self.slice_tree.column("Tamaño", width=70, minwidth=60)
        
        tree_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.slice_tree.yview)
        self.slice_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.slice_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind para selección
        self.slice_tree.bind("<<TreeviewSelect>>", self.on_slice_select)
        self.slice_tree.bind("<Double-1>", self.on_slice_double_click)
        
        # Botones del panel
        btn_frame = ttk.Frame(slice_panel)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="✏️ Editar", 
                  command=self.edit_selected_slice).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_frame, text="📐 Manual", 
                  command=self.manual_edit_slice).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_frame, text="🗑️ Del", 
                  command=self.delete_selected_slice).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_frame, text="🧹 All", 
                  command=self.clear_all_slices).pack(side=tk.LEFT, padx=1)
        
        # Panel de edición manual
        edit_panel = ttk.LabelFrame(right_frame, text="📐 Edición Manual", padding="5")
        edit_panel.pack(fill=tk.X, pady=(10, 0))
        
        # Campos de edición
        edit_grid = ttk.Frame(edit_panel)
        edit_grid.pack(fill=tk.X)
        
        # X, Y, Width, Height
        ttk.Label(edit_grid, text="X:", font=("Arial", 8)).grid(row=0, column=0, sticky=tk.W)
        self.x_var = tk.StringVar()
        self.x_entry = ttk.Entry(edit_grid, textvariable=self.x_var, width=6, font=("Consolas", 8))
        self.x_entry.grid(row=0, column=1, padx=2)
        
        ttk.Label(edit_grid, text="Y:", font=("Arial", 8)).grid(row=0, column=2, sticky=tk.W, padx=(5,0))
        self.y_var = tk.StringVar()
        self.y_entry = ttk.Entry(edit_grid, textvariable=self.y_var, width=6, font=("Consolas", 8))
        self.y_entry.grid(row=0, column=3, padx=2)
        
        ttk.Label(edit_grid, text="W:", font=("Arial", 8)).grid(row=1, column=0, sticky=tk.W)
        self.w_var = tk.StringVar()
        self.w_entry = ttk.Entry(edit_grid, textvariable=self.w_var, width=6, font=("Consolas", 8))
        self.w_entry.grid(row=1, column=1, padx=2, pady=2)
        
        ttk.Label(edit_grid, text="H:", font=("Arial", 8)).grid(row=1, column=2, sticky=tk.W, padx=(5,0))
        self.h_var = tk.StringVar()
        self.h_entry = ttk.Entry(edit_grid, textvariable=self.h_var, width=6, font=("Consolas", 8))
        self.h_entry.grid(row=1, column=3, padx=2, pady=2)
        
        # Botones de edición manual
        manual_btn_frame = ttk.Frame(edit_panel)
        manual_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(manual_btn_frame, text="✅ Aplicar", 
                  command=self.apply_manual_edit).pack(side=tk.LEFT, padx=2)
        ttk.Button(manual_btn_frame, text="🔄 Cargar", 
                  command=self.load_current_values).pack(side=tk.LEFT, padx=2)
        
        # Bind para actualización en tiempo real
        self.x_var.trace_add('write', self.on_manual_value_change)
        self.y_var.trace_add('write', self.on_manual_value_change)
        self.w_var.trace_add('write', self.on_manual_value_change)
        self.h_var.trace_add('write', self.on_manual_value_change)
        
        # Vista previa en tiempo real
        preview_panel = ttk.LabelFrame(right_frame, text="👁️ Vista Previa", padding="5")
        preview_panel.pack(fill=tk.X, pady=(10, 0))
        
        self.preview_canvas = tk.Canvas(preview_panel, width=280, height=150, bg="white")
        self.preview_canvas.pack()
        
        # Botón de exportar
        export_button = tk.Button(controls_row, 
                                text="🚀 EXPORTAR HTML", 
                                command=self.process_slices,
                                bg="#FF6B35",
                                fg="white",
                                font=("Arial", 10, "bold"),
                                padx=20,
                                pady=8,
                                cursor="hand2")
        export_button.pack(side=tk.RIGHT, padx=(20, 10))
        
        # Inicializar FPS counter
        self.fps_counter = 0
        self.fps_time = 0
        self.root.after(1000, self.update_fps)
    
    def on_brand_change(self):
        """Maneja el cambio de marca"""
        if self.brand.get() == "discover":
            # Para Discover, solo se permite "Solo nombre" y "Redención"
            self.header_type.set("name_only")
            self.header_name_miles_radio.config(state="disabled")
            self.campaign_type.set("redencion")
            self.activation_radio.config(state="disabled")
            self.redemption_radio.config(state="normal")
            # Ocultar opciones de template
            self.template_v1_radio.grid_remove()
            self.template_v2_radio.grid_remove()
        elif self.brand.get() == "clubmiles":
            # Para ClubMiles, mostrar opciones de template
            self.header_name_miles_radio.config(state="normal")
            self.activation_radio.config(state="normal")
            self.redemption_radio.config(state="normal")
            # MOSTRAR opciones de template
            self.template_v1_radio.grid()
            self.template_v2_radio.grid()
        else:  # BGR
            # Para BGR, comportamiento normal sin templates
            self.header_name_miles_radio.config(state="normal")
            self.activation_radio.config(state="normal")
            self.redemption_radio.config(state="normal")
            # Ocultar opciones de template
            self.template_v1_radio.grid_remove()
            self.template_v2_radio.grid_remove()
        
        self.update_r2_status()
    
    def on_campaign_type_change(self):
        """Maneja el cambio de tipo de campaña"""
        if self.campaign_type.get() == "activacion":
            # Si es activación, automáticamente seleccionar "Solo nombre"
            self.header_type.set("name_only")
            # Opcional: deshabilitar la opción de "Nombre y millas" para activación
            self.header_name_miles_radio.config(state="disabled")
        else:
            # Si es redención, habilitar ambas opciones
            if self.brand.get() != "discover":
                self.header_name_miles_radio.config(state="normal")
        
        self.update_r2_status()
    
    def on_platform_change(self):
        """Maneja el cambio de plataforma"""
        if self.platform.get() == "mautic":
            self.preheader_frame.pack(fill=tk.X, pady=(5, 0), after=self.preheader_frame.master.winfo_children()[1])
        else:
            self.preheader_frame.pack_forget()
    
    def update_r2_status(self):
        """Actualiza el estado de la URL de R2"""
        if self.upload_to_r2.get() and self.s3_client:
            brand = self.brand.get()
            campaign_type = self.campaign_type.get()
            
            # Para Discover, solo hay redención
            if brand == "discover":
                campaign_type = "redencion"
            
            if brand in self.public_base_urls and campaign_type in self.public_base_urls[brand]:
                url = self.public_base_urls[brand][campaign_type]
                self.r2_status_label.config(
                    text=f"📍 Destino: {url}{self.output_name_var.get()}/",
                    foreground="green"
                )
            else:
                self.r2_status_label.config(text="", foreground="black")
        else:
            self.r2_status_label.config(text="", foreground="black")
    
    def upload_image_to_r2(self, image_data, filename, folder_name):
        """Sube una imagen a Cloudflare R2"""
        if not self.s3_client or not self.upload_to_r2.get():
            return False, None
        
        try:
            brand = self.brand.get()
            campaign_type = self.campaign_type.get()
            
            # Para Discover, solo hay redención
            if brand == "discover":
                campaign_type = "redencion"
            
            # Obtener la ruta base en R2
            if brand in self.r2_base_urls and campaign_type in self.r2_base_urls[brand]:
                base_path = self.r2_base_urls[brand][campaign_type]
            else:
                print(f"❌ No se encontró configuración para {brand}/{campaign_type}")
                return False, None
            
            # Construir la ruta completa
            remote_path = f"{base_path}{folder_name}/{filename}"
            
            # Determinar el content type
            content_type = 'image/jpeg'
            if filename.lower().endswith('.png'):
                content_type = 'image/png'
            elif filename.lower().endswith('.gif'):
                content_type = 'image/gif'
            
            # Subir a R2
            self.s3_client.put_object(
                Bucket=self.r2_config["bucket_name"],
                Key=remote_path,
                Body=image_data,
                ContentType=content_type,
                CacheControl='public, max-age=31536000'
            )
            
            # Construir URL pública
            public_url = f"{self.public_base_urls[brand][campaign_type]}{folder_name}/{filename}"
            
            print(f"✅ Imagen subida: {filename} -> {public_url}")
            return True, public_url
            
        except Exception as e:
            print(f"❌ Error subiendo {filename}: {str(e)}")
            return False, None
    
    def update_fps(self):
        """Actualiza el contador de FPS"""
        import time
        current_time = time.time()
        if hasattr(self, 'last_fps_time'):
            fps = self.fps_counter / (current_time - self.last_fps_time) if current_time > self.last_fps_time else 0
            self.coord_label.config(text=f"{self.coord_label.cget('text').split('|')[0]}| FPS: {fps:.1f}")
        
        self.last_fps_time = current_time
        self.fps_counter = 0
        self.root.after(1000, self.update_fps)
    
    def schedule_update(self, func, *args):
        """Programa una actualización optimizada"""
        import time
        current_time = time.time() * 1000
        
        if current_time - self.last_update_time >= self.update_delay:
            if self.pending_update:
                self.root.after_cancel(self.pending_update)
            func(*args)
            self.last_update_time = current_time
            self.fps_counter += 1
        else:
            if self.pending_update:
                self.root.after_cancel(self.pending_update)
            delay = int(self.update_delay - (current_time - self.last_update_time))
            self.pending_update = self.root.after(max(1, delay), lambda: self.schedule_update(func, *args))
    
    def toggle_slice_tool(self):
        """Alterna la herramienta de recorte"""
        self.slice_tool_active = not self.slice_tool_active
        if self.slice_tool_active:
            self.slice_tool_btn.config(bg="#4CAF50", relief=tk.RAISED)
            self.canvas.config(cursor="crosshair")
            self.instruction_label.config(text="🗄️ HERRAMIENTA DE RECORTE ACTIVADA | Vista previa EN TIEMPO REAL")
        else:
            self.slice_tool_btn.config(bg="#757575", relief=tk.SUNKEN)
            self.canvas.config(cursor="arrow")
            self.instruction_label.config(text="Herramienta de recorte desactivada | Haz clic para activar")
    
    def zoom_in(self):
        """Aumenta el zoom"""
        if self.zoom_factor < 4.0:
            self.zoom_factor *= 1.25
            self.update_zoom()
    
    def zoom_out(self):
        """Disminuye el zoom"""
        if self.zoom_factor > 0.25:
            self.zoom_factor /= 1.25
            self.update_zoom()
    
    def zoom_reset(self):
        """Resetea el zoom al 100%"""
        self.zoom_factor = 1.0
        self.update_zoom()
    
    def update_zoom(self):
        """Actualiza la visualización con el zoom actual"""
        self.zoom_label.config(text=f"{int(self.zoom_factor * 100)}%")
        if self.mockup_image:
            self.display_image()
    
    def on_zoom_wheel(self, event):
        """Zoom con Ctrl+scroll"""
        try:
            if hasattr(event, 'delta') and event.delta:
                if event.delta > 0:
                    self.zoom_in()
                else:
                    self.zoom_out()
            elif hasattr(event, 'num'):
                if event.num == 4:
                    self.zoom_in()
                elif event.num == 5:
                    self.zoom_out()
        except Exception:
            pass
    
    def on_scroll_wheel(self, event):
        """Scroll normal sin Ctrl"""
        if event.state & 0x4:
            return
        
        try:
            if hasattr(event, 'delta') and event.delta:
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            elif hasattr(event, 'num'):
                if event.num == 4:
                    self.canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.canvas.yview_scroll(1, "units")
        except Exception:
            pass
    
    def load_image(self):
        """Carga la imagen para recortar"""
        file_path = filedialog.askopenfilename(
            title="Seleccionar mockup para recortar",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg")]
        )
        
        if file_path:
            try:
                img = Image.open(file_path)
                width, height = img.size
                
                # Calcular las nuevas dimensiones manteniendo la proporción
                new_width = 700
                aspect_ratio = height / width
                new_height = int(new_width * aspect_ratio)
                
                # Redimensionar la imagen
                self.mockup_image = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Mostrar información del redimensionamiento
                if width != new_width:
                    messagebox.showinfo("Imagen adaptada", 
                                    f"Imagen redimensionada de {width}x{height} a {new_width}x{new_height}")
                
                self.mockup_path = file_path
                self.slices = []
                self.update_slice_tree()
                self.zoom_factor = 1.0
                self.display_image()
                
                # Activar herramienta de recorte automáticamente
                self.slice_tool_active = True
                self.slice_tool_btn.config(bg="#4CAF50", relief=tk.RAISED)
                
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar la imagen: {str(e)}")
    
    def display_image(self):
        """Muestra la imagen optimizada"""
        if not self.mockup_image:
            return
        
        # Limpiar canvas
        self.canvas.delete("all")
        
        # Aplicar zoom
        zoomed_width = int(self.mockup_image.width * self.zoom_factor)
        zoomed_height = int(self.mockup_image.height * self.zoom_factor)
        
        if self.zoom_factor != 1.0:
            zoomed_image = self.mockup_image.resize((zoomed_width, zoomed_height), Image.Resampling.LANCZOS)
            self.photo_image = ImageTk.PhotoImage(zoomed_image)
        else:
            self.photo_image = ImageTk.PhotoImage(self.mockup_image)
        
        # Mostrar imagen
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image, tags="main_image")
        
        # Configurar scroll region
        self.canvas.config(scrollregion=(0, 0, zoomed_width, zoomed_height))
        
        # Dibujar recortes existentes
        for i, slice_data in enumerate(self.slices):
            self.draw_slice_rectangle(i, slice_data)
        
        # Dibujar guías si están activadas
        if self.show_guides_var.get():
            self.draw_smart_guides()
    
    def draw_slice_rectangle(self, index, slice_data):
        """Dibuja un rectángulo de recorte optimizado"""
        x = slice_data["x"] * self.zoom_factor
        y = slice_data["y"] * self.zoom_factor
        w = slice_data["width"] * self.zoom_factor
        h = slice_data["height"] * self.zoom_factor
        
        is_selected = (index == self.selected_slice)
        
        # Colores optimizados
        if is_selected:
            outline_color = "#FF6B35"
            line_width = 2
            fill_color = "#FF6B35"
        else:
            outline_color = "#4CAF50"
            line_width = 1
            fill_color = "#4CAF50"
        
        # Rectángulo principal
        self.canvas.create_rectangle(
            x, y, x + w, y + h,
            outline=outline_color, 
            width=line_width,
            tags=(f"slice_{index}", "slice")
        )
        
        # Handles de redimensionamiento (solo si está seleccionado)
        if is_selected:
            handle_size = max(4, min(8, int(6 * self.zoom_factor)))
            
            # Solo esquinas y puntos medios para optimización
            handles = [
                (x, y), (x + w, y), (x, y + h), (x + w, y + h),
                (x + w/2, y), (x + w/2, y + h), (x, y + h/2), (x + w, y + h/2)
            ]
            
            for hx, hy in handles:
                self.canvas.create_rectangle(
                    hx - handle_size/2, hy - handle_size/2,
                    hx + handle_size/2, hy + handle_size/2,
                    fill="white", outline=outline_color, width=1,
                    tags=(f"slice_{index}", "handle")
                )
        
        # Etiqueta optimizada
        font_size = max(8, min(12, int(10 * self.zoom_factor)))
        label_text = f"{index + 1}"
        if is_selected:
            label_text += f" ({slice_data['width']}×{slice_data['height']})"
        
        # Fondo para la etiqueta
        text_width = len(label_text) * font_size * 0.6
        self.canvas.create_rectangle(
            x + 2, y + 2, x + text_width + 6, y + font_size + 4,
            fill=fill_color, outline="", tags=(f"slice_{index}", "label_bg")
        )
        
        self.canvas.create_text(
            x + 4, y + 3,
            text=label_text,
            fill="white",
            anchor=tk.NW,
            font=("Arial", font_size, "bold"),
            tags=(f"slice_{index}", "slice_text")
        )
    
    def draw_smart_guides(self):
        """Dibuja las guías inteligentes optimizadas"""
        if not self.show_guides_var.get():
            return
        
        zoomed_width = int(self.mockup_image.width * self.zoom_factor)
        zoomed_height = int(self.mockup_image.height * self.zoom_factor)
        
        # Solo dibujar guías temporales durante el arrastre para optimización
        for guide_data in self.guide_lines:
            if guide_data["type"] == "vertical":
                x = guide_data["pos"] * self.zoom_factor
                self.canvas.create_line(
                    x, 0, x, zoomed_height,
                    fill="#00FF00", width=2, tags="temp_guide"
                )
            elif guide_data["type"] == "horizontal":
                y = guide_data["pos"] * self.zoom_factor
                self.canvas.create_line(
                    0, y, zoomed_width, y,
                    fill="#00FF00", width=2, tags="temp_guide"
                )
    
    def canvas_to_image_coords(self, canvas_x, canvas_y):
        """Convierte coordenadas del canvas a coordenadas de imagen"""
        return canvas_x / self.zoom_factor, canvas_y / self.zoom_factor
    
    def image_to_canvas_coords(self, img_x, img_y):
        """Convierte coordenadas de imagen a coordenadas del canvas"""
        return img_x * self.zoom_factor, img_y * self.zoom_factor
    
    def find_snap_positions(self, x, y, width, height, exclude_index=None):
        """Encuentra posiciones de snap optimizadas"""
        snap_x, snap_y = x, y
        self.guide_lines = []
        
        # Snap a otros recortes (optimizado)
        for i, slice_data in enumerate(self.slices):
            if exclude_index is not None and i == exclude_index:
                continue
            
            sx, sy, sw, sh = slice_data["x"], slice_data["y"], slice_data["width"], slice_data["height"]
            
            # Snap horizontal (X)
            if abs(x - sx) <= self.snap_threshold:
                snap_x = sx
                self.guide_lines.append({"type": "vertical", "pos": sx})
            elif abs((x + width) - (sx + sw)) <= self.snap_threshold:
                snap_x = sx + sw - width
                self.guide_lines.append({"type": "vertical", "pos": sx + sw})
            elif abs(x - (sx + sw)) <= self.snap_threshold:
                snap_x = sx + sw
                self.guide_lines.append({"type": "vertical", "pos": sx + sw})
            elif abs((x + width) - sx) <= self.snap_threshold:
                snap_x = sx - width
                self.guide_lines.append({"type": "vertical", "pos": sx})
            
            # Snap vertical (Y)
            if abs(y - sy) <= self.snap_threshold:
                snap_y = sy
                self.guide_lines.append({"type": "horizontal", "pos": sy})
            elif abs((y + height) - (sy + sh)) <= self.snap_threshold:
                snap_y = sy + sh - height
                self.guide_lines.append({"type": "horizontal", "pos": sy + sh})
            elif abs(y - (sy + sh)) <= self.snap_threshold:
                snap_y = sy + sh
                self.guide_lines.append({"type": "horizontal", "pos": sy + sh})
            elif abs((y + height) - sy) <= self.snap_threshold:
                snap_y = sy - height
                self.guide_lines.append({"type": "horizontal", "pos": sy})
        
        # Snap a los bordes de la imagen
        if abs(x) <= self.snap_threshold:
            snap_x = 0
            self.guide_lines.append({"type": "vertical", "pos": 0})
        
        if abs((x + width) - self.mockup_image.width) <= self.snap_threshold:
            snap_x = self.mockup_image.width - width
            self.guide_lines.append({"type": "vertical", "pos": self.mockup_image.width})
        
        if abs(y) <= self.snap_threshold:
            snap_y = 0
            self.guide_lines.append({"type": "horizontal", "pos": 0})
        
        return snap_x, snap_y
    
    def constrain_to_bounds(self, x, y, width, height):
        """Restringe a los límites de la imagen"""
        x = max(0, min(x, self.mockup_image.width - width))
        y = max(0, min(y, self.mockup_image.height - height))
        width = max(10, min(width, self.mockup_image.width - x))
        height = max(10, min(height, self.mockup_image.height - y))
        
        return x, y, width, height
    
    def update_coordinates_display(self, x=None, y=None, w=None, h=None):
        """Actualiza la información de coordenadas"""
        if x is not None and y is not None:
            if w is not None and h is not None:
                text = f"Posición: {int(x)},{int(y)} | Tamaño: {int(w)}×{int(h)}"
            else:
                text = f"Posición: {int(x)},{int(y)} | Tamaño: --"
        else:
            text = "Posición: -- | Tamaño: --"
        
        current_text = self.coord_label.cget('text')
        if '|' in current_text and 'FPS:' in current_text:
            fps_part = current_text.split('FPS:')[1]
            text += f" | FPS:{fps_part}"
        
        self.coord_label.config(text=text)
    
    def update_preview_image(self, x, y, width, height):
        """Actualiza la vista previa en tiempo real"""
        if not self.preview_var.get() or not self.mockup_image:
            return
        
        try:
            # Recortar la imagen
            preview_img = self.mockup_image.crop((x, y, x + width, y + height))
            
            # Redimensionar para el canvas de preview
            preview_img.thumbnail((270, 140), Image.Resampling.LANCZOS)
            
            # Convertir a PhotoImage
            self.preview_image = ImageTk.PhotoImage(preview_img)
            
            # Mostrar en el canvas de preview
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(140, 75, image=self.preview_image)
            
            # Mostrar información
            info_text = f"{int(width)}×{int(height)} px\nPos: {int(x)},{int(y)}"
            self.preview_canvas.create_text(5, 5, text=info_text, anchor=tk.NW, 
                                          fill="red", font=("Arial", 8, "bold"))
        except Exception:
            pass
    
    def on_canvas_motion(self, event):
        """Maneja el movimiento del mouse optimizado"""
        if not self.mockup_image:
            return
        
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)
        
        # Actualizar coordenadas durante el dibujo
        if self.drawing and self.start_x is not None and self.start_y is not None:
            w = abs(img_x - self.start_x)
            h = abs(img_y - self.start_y)
            self.update_coordinates_display(min(self.start_x, img_x), min(self.start_y, img_y), w, h)
        else:
            self.update_coordinates_display(img_x, img_y)
        
        # Cambiar cursor según contexto
        if not self.slice_tool_active:
            self.canvas.config(cursor="arrow")
            return
        
        cursor = "crosshair"
        
        # Detectar si estamos sobre un recorte existente
        for i, slice_data in enumerate(self.slices):
            edge = self.get_edge_at_point(canvas_x, canvas_y, slice_data)
            if edge:
                if edge in ["left", "right"]:
                    cursor = "sb_h_double_arrow"
                elif edge in ["top", "bottom"]:
                    cursor = "sb_v_double_arrow"
                elif edge == "inside":
                    cursor = "fleur"
                break
        
        self.canvas.config(cursor=cursor)
    
    def get_edge_at_point(self, canvas_x, canvas_y, slice_data):
        """Determina qué borde está en el punto dado"""
        img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)
        
        sx, sy = slice_data["x"], slice_data["y"]
        sw, sh = slice_data["width"], slice_data["height"]
        tolerance = max(3, int(5 / self.zoom_factor))
        
        if abs(img_x - sx) <= tolerance and sy <= img_y <= sy + sh:
            return "left"
        elif abs(img_x - (sx + sw)) <= tolerance and sy <= img_y <= sy + sh:
            return "right"
        elif abs(img_y - sy) <= tolerance and sx <= img_x <= sx + sw:
            return "top"
        elif abs(img_y - (sy + sh)) <= tolerance and sx <= img_x <= sx + sw:
            return "bottom"
        elif sx <= img_x <= sx + sw and sy <= img_y <= sy + sh:
            return "inside"
        return None
    
    def on_canvas_click(self, event):
        """Maneja el click en el canvas"""
        if not self.mockup_image or not self.slice_tool_active:
            return
        
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # Verificar si clickeamos sobre un recorte existente
        for i, slice_data in enumerate(self.slices):
            edge = self.get_edge_at_point(canvas_x, canvas_y, slice_data)
            if edge:
                self.start_edit_slice(i, canvas_x, canvas_y, edge)
                return
        
        # Iniciar nuevo recorte
        self.start_new_slice(canvas_x, canvas_y)
    
    def start_new_slice(self, canvas_x, canvas_y):
        """Inicia la creación de un nuevo recorte"""
        img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)
        
        self.drawing = True
        self.start_x = img_x
        self.start_y = img_y
        self.current_x = img_x
        self.current_y = img_y
        
        # Crear rectángulo de previsualización optimizado
        canvas_start_x, canvas_start_y = self.image_to_canvas_coords(img_x, img_y)
        self.preview_rect = self.canvas.create_rectangle(
            canvas_start_x, canvas_start_y, canvas_start_x, canvas_start_y,
            outline="#FF6B35", width=2, dash=(5, 5), tags="preview"
        )
        
        # Deseleccionar otros recortes
        self.selected_slice = None
        self.update_slice_tree()
        self.clear_manual_fields()
    
    def start_edit_slice(self, slice_index, canvas_x, canvas_y, edge):
        """Inicia la edición de un recorte existente"""
        img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)
        
        self.dragging = True
        self.selected_slice = slice_index
        self.drag_data = {
            "item": slice_index,
            "x": img_x,
            "y": img_y,
            "edge": edge,
            "original": self.slices[slice_index].copy()
        }
        
        self.update_slice_tree()
        self.load_current_values()
        self.display_image()
    
    def on_canvas_drag(self, event):
        """Maneja el arrastre optimizado"""
        if not self.mockup_image:
            return
        
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)
        
        # Limitar a los bordes de la imagen
        img_x = max(0, min(img_x, self.mockup_image.width))
        img_y = max(0, min(img_y, self.mockup_image.height))
        
        if self.drawing:
            self.schedule_update(self.handle_new_slice_drag, img_x, img_y)
        elif self.dragging:
            self.schedule_update(self.handle_edit_slice_drag, img_x, img_y)
    
    def handle_new_slice_drag(self, img_x, img_y):
        """Maneja el arrastre para crear nuevo recorte optimizado"""
        self.current_x = img_x
        self.current_y = img_y
        
        # Calcular dimensiones actuales
        x1 = min(self.start_x, img_x)
        y1 = min(self.start_y, img_y)
        x2 = max(self.start_x, img_x)
        y2 = max(self.start_y, img_y)
        width = x2 - x1
        height = y2 - y1
        
        # Aplicar snap inteligente solo con tamaño mínimo
        if width > 5 and height > 5:
            snap_x, snap_y = self.find_snap_positions(x1, y1, width, height)
            
            if snap_x != x1:
                x1 = snap_x
                x2 = x1 + width
            if snap_y != y1:
                y1 = snap_y
                y2 = y1 + height
        
        # Actualizar rectángulo de previsualización
        if self.preview_rect:
            canvas_x1, canvas_y1 = self.image_to_canvas_coords(x1, y1)
            canvas_x2, canvas_y2 = self.image_to_canvas_coords(x2, y2)
            self.canvas.coords(self.preview_rect, canvas_x1, canvas_y1, canvas_x2, canvas_y2)
        
        # Actualizar vista previa en tiempo real
        if width > 10 and height > 10:
            self.update_preview_image(x1, y1, width, height)
        
        # Redibujar guías
        self.draw_smart_guides()
    
    def handle_edit_slice_drag(self, img_x, img_y):
        """Maneja el arrastre para editar recorte existente optimizado"""
        if self.drag_data["item"] is None:
            return
        
        dx = img_x - self.drag_data["x"]
        dy = img_y - self.drag_data["y"]
        
        slice_index = self.drag_data["item"]
        slice_data = self.slices[slice_index]
        original = self.drag_data["original"]
        edge = self.drag_data["edge"]
        
        new_bounds = self.calculate_new_bounds(original, edge, dx, dy)
        
        if new_bounds:
            # Aplicar restricciones
            new_x, new_y, new_w, new_h = self.constrain_to_bounds(
                new_bounds["x"], new_bounds["y"], 
                new_bounds["width"], new_bounds["height"]
            )
            
            # Aplicar snap si estamos moviendo
            if edge == "inside":
                snap_x, snap_y = self.find_snap_positions(new_x, new_y, new_w, new_h, slice_index)
                new_x, new_y = snap_x, snap_y
            
            final_bounds = {
                "x": int(new_x), "y": int(new_y), 
                "width": int(new_w), "height": int(new_h)
            }
            
            # Verificar colisiones
            can_move = True
            for i, other_slice in enumerate(self.slices):
                if i != slice_index and self.rectangles_overlap(final_bounds, other_slice):
                    can_move = False
                    break
            
            if can_move:
                slice_data.update(final_bounds)
                self.load_current_values()
                self.update_preview_image(new_x, new_y, new_w, new_h)
                self.display_image()
    
    def calculate_new_bounds(self, original, edge, dx, dy):
        """Calcula nuevos límites del recorte"""
        bounds = original.copy()
        
        if edge == "left":
            bounds["x"] = original["x"] + dx
            bounds["width"] = original["width"] - dx
        elif edge == "right":
            bounds["width"] = original["width"] + dx
        elif edge == "top":
            bounds["y"] = original["y"] + dy
            bounds["height"] = original["height"] - dy
        elif edge == "bottom":
            bounds["height"] = original["height"] + dy
        elif edge == "inside":
            bounds["x"] = original["x"] + dx
            bounds["y"] = original["y"] + dy
        
        # Validar dimensiones mínimas
        if bounds["width"] < 10:
            bounds["width"] = 10
            if edge == "left":
                bounds["x"] = original["x"] + original["width"] - 10
        
        if bounds["height"] < 10:
            bounds["height"] = 10
            if edge == "top":
                bounds["y"] = original["y"] + original["height"] - 10
        
        return bounds
    
    def rectangles_overlap(self, rect1, rect2):
        """Verifica si dos rectángulos se superponen"""
        x1, y1, w1, h1 = rect1["x"], rect1["y"], rect1["width"], rect1["height"]
        x2, y2, w2, h2 = rect2["x"], rect2["y"], rect2["width"], rect2["height"]
        
        return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)
    
    def on_canvas_release(self, event):
        """Maneja la liberación del mouse"""
        if self.drawing:
            self.finish_new_slice()
        elif self.dragging:
            self.finish_edit_slice()
        
        # Limpiar guías temporales
        self.guide_lines = []
        self.display_image()
    
    def finish_new_slice(self):
        """Finaliza la creación de un nuevo recorte"""
        self.drawing = False
        
        if self.preview_rect and self.mockup_image:
            x1 = min(self.start_x, self.current_x)
            y1 = min(self.start_y, self.current_y)
            x2 = max(self.start_x, self.current_x)
            y2 = max(self.start_y, self.current_y)
            
            width = x2 - x1
            height = y2 - y1
            
            if width > 10 and height > 10:
                # Aplicar snap final
                snap_x, snap_y = self.find_snap_positions(x1, y1, width, height)
                
                # Asegurar límites
                final_x, final_y, final_w, final_h = self.constrain_to_bounds(
                    snap_x, snap_y, width, height
                )
                
                new_slice = {
                    "name": f"slice_{len(self.slices) + 1}",
                    "x": int(final_x),
                    "y": int(final_y),
                    "width": int(final_w),
                    "height": int(final_h),
                    "type": "image",
                    "has_url": False,
                    "url": "",
                    "order": len(self.slices)
                }
                
                # Verificar colisiones
                has_collision = False
                for existing_slice in self.slices:
                    if self.rectangles_overlap(new_slice, existing_slice):
                        has_collision = True
                        break
                
                if not has_collision:
                    self.slices.append(new_slice)
                    self.selected_slice = len(self.slices) - 1
                    self.update_slice_tree()
                    self.load_current_values()
                else:
                    messagebox.showwarning("Colisión detectada", "El recorte se superpone con otro existente")
            
            self.canvas.delete(self.preview_rect)
            self.preview_rect = None
    
    def finish_edit_slice(self):
        """Finaliza la edición de un recorte"""
        self.dragging = False
        self.drag_data = {"item": None, "x": 0, "y": 0, "edge": None}
        self.update_slice_tree()
    
    def update_slice_tree(self):
        """Actualiza el árbol de recortes"""
        # Limpiar árbol
        for item in self.slice_tree.get_children():
            self.slice_tree.delete(item)
        
        # Agregar recortes
        for i, slice_data in enumerate(self.slices):
            item_id = self.slice_tree.insert(
                "", "end",
                text=f"{i+1}",
                values=(
                    slice_data["name"],
                    f"{slice_data['x']},{slice_data['y']}",
                    f"{slice_data['width']}×{slice_data['height']}"
                ),
                tags=("selected" if i == self.selected_slice else "normal",)
            )
            
            if i == self.selected_slice:
                self.slice_tree.selection_set(item_id)
    
    def on_slice_select(self, event):
        """Maneja la selección en el árbol de recortes"""
        selection = self.slice_tree.selection()
        if selection:
            item = selection[0]
            children = self.slice_tree.get_children()
            if item in children:
                self.selected_slice = children.index(item)
                self.load_current_values()
                self.display_image()
    
    def on_slice_double_click(self, event):
        """Maneja el doble click en un recorte"""
        self.manual_edit_slice()
    
    def deselect_all(self):
        """Deselecciona todos los recortes"""
        self.selected_slice = None
        self.slice_tree.selection_remove(self.slice_tree.selection())
        self.clear_manual_fields()
        self.display_image()
    
    def edit_selected_slice(self):
        """Edita el recorte seleccionado"""
        selection = self.slice_tree.selection()
        if selection:
            item = selection[0]
            children = self.slice_tree.get_children()
            if item in children:
                self.selected_slice = children.index(item)
                self.load_current_values()
                self.display_image()
    
    def manual_edit_slice(self):
        """Abre edición manual del recorte seleccionado"""
        if self.selected_slice is not None:
            self.load_current_values()
            self.x_entry.focus_set()
            self.x_entry.select_range(0, tk.END)
    
    def load_current_values(self):
        """Carga los valores actuales en los campos de edición manual"""
        if self.selected_slice is not None and self.selected_slice < len(self.slices):
            slice_data = self.slices[self.selected_slice]
            self.x_var.set(str(slice_data["x"]))
            self.y_var.set(str(slice_data["y"]))
            self.w_var.set(str(slice_data["width"]))
            self.h_var.set(str(slice_data["height"]))
    
    def clear_manual_fields(self):
        """Limpia los campos de edición manual"""
        self.x_var.set("")
        self.y_var.set("")
        self.w_var.set("")
        self.h_var.set("")
    
    def on_manual_value_change(self, *args):
        """Maneja cambios en los valores manuales"""
        # Validación en tiempo real (opcional)
        pass
    
    def apply_manual_edit(self):
        """Aplica la edición manual"""
        if self.selected_slice is None or self.selected_slice >= len(self.slices):
            messagebox.showwarning("Advertencia", "Selecciona un recorte primero")
            return
        
        try:
            # Obtener valores
            x = int(self.x_var.get()) if self.x_var.get() else 0
            y = int(self.y_var.get()) if self.y_var.get() else 0
            w = int(self.w_var.get()) if self.w_var.get() else 10
            h = int(self.h_var.get()) if self.h_var.get() else 10
            
            # Validar y restringir
            x, y, w, h = self.constrain_to_bounds(x, y, w, h)
            
            # Crear nuevos bounds para verificar colisiones
            new_bounds = {"x": x, "y": y, "width": w, "height": h}
            
            # Verificar colisiones con otros recortes
            has_collision = False
            for i, other_slice in enumerate(self.slices):
                if i != self.selected_slice and self.rectangles_overlap(new_bounds, other_slice):
                    has_collision = True
                    break
            
            if has_collision:
                messagebox.showwarning("Colisión", "El recorte se superpondría con otro existente")
                return
            
            # Aplicar cambios
            slice_data = self.slices[self.selected_slice]
            slice_data.update(new_bounds)
            
            # Actualizar interfaz
            self.update_slice_tree()
            self.display_image()
            self.update_preview_image(x, y, w, h)
            
            messagebox.showinfo("Éxito", f"Recorte actualizado: {w}×{h} en {x},{y}")
            
        except ValueError:
            messagebox.showerror("Error", "Por favor ingresa valores numéricos válidos")
    
    def delete_selected_slice(self):
        """Elimina el recorte seleccionado"""
        if self.selected_slice is not None and self.selected_slice < len(self.slices):
            slice_name = self.slices[self.selected_slice]["name"]
            if messagebox.askyesno("Confirmar eliminación", f"¿Eliminar {slice_name}?"):
                del self.slices[self.selected_slice]
                self.selected_slice = None
                self.update_slice_tree()
                self.clear_manual_fields()
                self.preview_canvas.delete("all")
                self.display_image()
    
    def clear_all_slices(self):
        """Limpia todos los recortes"""
        if self.slices and messagebox.askyesno("Confirmar", "¿Eliminar todos los recortes?"):
            self.slices = []
            self.selected_slice = None
            self.update_slice_tree()
            self.clear_manual_fields()
            self.preview_canvas.delete("all")
            self.display_image()
    
    def set_output_folder(self):
        """Establece la carpeta de salida"""
        folder_name = self.output_name_var.get().strip()
        if folder_name:
            self.custom_output_name = folder_name
            self.output_folder = folder_name
            self.images_folder = os.path.join(self.output_folder, "images")
            self.update_r2_status()
            messagebox.showinfo("Carpeta establecida", f"Salida: {folder_name}")
    
    def on_right_click(self, event):
        """Menú contextual"""
        popup = tk.Menu(self.root, tearoff=0)
        
        popup.add_command(label="🗄️ Activar herramienta de recorte", 
                         command=self.toggle_slice_tool)
        popup.add_separator()
        
        if self.slices:
            popup.add_command(label="✓ Validar recortes", 
                            command=self.validate_slices)
            popup.add_command(label="🔧 Auto-organizar", 
                            command=self.auto_arrange_slices)
        
        popup.add_command(label="🧹 Limpiar todo", 
                         command=self.clear_all_slices)
        
        try:
            popup.tk_popup(event.x_root, event.y_root, 0)
        finally:
            popup.grab_release()
    
    def validate_slices(self):
        """Valida los recortes"""
        if not self.slices:
            messagebox.showinfo("Validación", "No hay recortes para validar")
            return
        
        errors, warnings = self.validate_row_widths()
        
        if not errors and not warnings:
            messagebox.showinfo("✅ Validación exitosa", 
                              f"Todos los {len(self.slices)} recortes están correctamente configurados.")
        else:
            # Mostrar resultados
            result_text = ""
            if errors:
                result_text += "❌ ERRORES:\n" + "\n".join(errors) + "\n\n"
            if warnings:
                result_text += "⚠️ ADVERTENCIAS:\n" + "\n".join(warnings)
            
            messagebox.showwarning("Resultados de Validación", result_text)
    
    def validate_row_widths(self):
        """Valida que las filas sumen 700px"""
        # Agrupar por Y
        rows = {}
        for i, slice_data in enumerate(self.slices):
            y = slice_data["y"]
            found_row = None
            for row_y in rows.keys():
                if abs(y - row_y) <= 5:
                    found_row = row_y
                    break
            
            if found_row:
                rows[found_row].append((i, slice_data))
            else:
                rows[y] = [(i, slice_data)]
        
        errors = []
        warnings = []
        
        for y in sorted(rows.keys()):
            row_slices = sorted(rows[y], key=lambda x: x[1]["x"])
            
            if len(row_slices) == 1:
                slice_idx, slice_data = row_slices[0]
                if slice_data["width"] != 700:
                    warnings.append(f"Recorte {slice_idx + 1} tiene {slice_data['width']}px de ancho (debería ser 700px)")
            else:
                total_width = sum(slice_data["width"] for _, slice_data in row_slices)
                
                if total_width != 700:
                    slice_names = [f"{idx+1}" for idx, data in row_slices]
                    
                    if total_width > 700:
                        errors.append(f"Fila Y={int(y)}: Recortes {', '.join(slice_names)} suman {total_width}px (máximo: 700px)")
                    else:
                        warnings.append(f"Fila Y={int(y)}: Recortes {', '.join(slice_names)} suman {total_width}px (deberían sumar 700px)")
        
        return errors, warnings
    
    def auto_arrange_slices(self):
        """Auto-organiza los recortes"""
        if not self.slices:
            return
        
        # Agrupar por Y
        rows = {}
        for slice_data in self.slices:
            y = slice_data["y"]
            found_row = None
            for row_y in rows.keys():
                if abs(y - row_y) <= 8:
                    found_row = row_y
                    break
            
            if found_row:
                rows[found_row].append(slice_data)
            else:
                rows[y] = [slice_data]
        
        # Reorganizar cada fila
        for y in sorted(rows.keys()):
            row_slices = sorted(rows[y], key=lambda s: s["x"])
            current_x = 0
            
            for slice_data in row_slices:
                slice_data["x"] = current_x
                slice_data["y"] = y
                current_x += slice_data["width"]
        
        self.update_slice_tree()
        self.display_image()
        messagebox.showinfo("Auto-organización completada", "Los recortes han sido reorganizados automáticamente.")
    
    def organize_slices_for_html(self):
        """Organiza los recortes en filas para HTML"""
        sorted_slices = sorted(self.slices, key=lambda s: s.get("order", 0))
        
        rows = []
        current_row = []
        current_width = 0
        
        for slice_data in sorted_slices:
            if current_row and current_width + slice_data["width"] > 700:
                rows.append(current_row)
                current_row = []
                current_width = 0
            
            current_row.append(slice_data)
            current_width += slice_data["width"]
        
        if current_row:
            rows.append(current_row)
        
        return rows
    
    def process_slices(self):
        """Procesa los recortes para exportación"""
        if not self.slices:
            messagebox.showwarning("Sin recortes", "No hay recortes para procesar")
            return
        
        # Validación automática
        errors, warnings = self.validate_row_widths()
        
        if errors:
            messagebox.showerror("Errores críticos", 
                               "Se encontraron errores que deben corregirse:\n\n" + "\n".join(errors))
            return
        
        if warnings:
            if not messagebox.askyesno("Advertencias encontradas", 
                                     f"Se encontraron {len(warnings)} advertencias.\n"
                                     "¿Desea continuar con la exportación?"):
                return
        
        if not self.custom_output_name:
            self.set_output_folder()
        
        # Si es Mautic y no hay preheader, pedirlo
        if self.platform.get() == "mautic" and not self.preheader_text.get().strip():
            preheader_dialog = tk.Toplevel(self.root)
            preheader_dialog.title("Ingrese el Preheader")
            preheader_dialog.geometry("500x150")
            
            # Centrar la ventana
            preheader_dialog.transient(self.root)
            preheader_dialog.grab_set()
            
            tk.Label(preheader_dialog, text="Por favor ingrese el texto del Preheader para Mautic:", 
                    font=("Arial", 11), pady=10).pack()
            
            preheader_frame = ttk.Frame(preheader_dialog)
            preheader_frame.pack(fill=tk.X, padx=20, pady=10)
            
            preheader_var = tk.StringVar()
            preheader_entry = ttk.Entry(preheader_frame, textvariable=preheader_var, width=50)
            preheader_entry.pack(fill=tk.X)
            preheader_entry.focus_set()
            
            button_frame = ttk.Frame(preheader_dialog)
            button_frame.pack(pady=10)
            
            def accept_preheader():
                self.preheader_text.set(preheader_var.get())
                preheader_dialog.destroy()
                ConfigWindow(self.root, self)
            
            def cancel_preheader():
                preheader_dialog.destroy()
            
            ttk.Button(button_frame, text="Aceptar", command=accept_preheader).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancelar", command=cancel_preheader).pack(side=tk.LEFT, padx=5)
            
            # Bind Enter key
            preheader_entry.bind('<Return>', lambda e: accept_preheader())
            
            # Center dialog on parent
            preheader_dialog.wait_window()
        else:
            ConfigWindow(self.root, self)
    
    def check_folder_exists_in_r2(self, folder_name):
        """Verifica si una carpeta ya existe en R2"""
        if not self.s3_client or not self.upload_to_r2.get():
            return False
        
        try:
            brand = self.brand.get()
            campaign_type = self.campaign_type.get()
            
            # Para Discover, solo hay redención
            if brand == "discover":
                campaign_type = "redencion"
            
            # Obtener la ruta base en R2
            base_path = self.r2_base_urls[brand][campaign_type]
            prefix = f"{base_path}{folder_name}/"
            
            # Listar objetos con ese prefijo
            response = self.s3_client.list_objects_v2(
                Bucket=self.r2_config["bucket_name"],
                Prefix=prefix,
                MaxKeys=1
            )
            
            # Si hay al menos un objeto, la carpeta existe
            return 'Contents' in response and len(response['Contents']) > 0
            
        except Exception as e:
            print(f"Error verificando carpeta: {e}")
            return False
    
    def generate_output(self):
        """Genera las imágenes y el HTML"""
        os.makedirs(self.images_folder, exist_ok=True)
        
        # Guardar URLs de R2 si están habilitadas
        r2_image_urls = {}
        folder_name = self.output_name_var.get() if self.output_name_var.get() else "output"
        
        # Verificar si la carpeta ya existe en R2
        if self.upload_to_r2.get() and self.check_folder_exists_in_r2(folder_name):
            # Preguntar al usuario qué hacer
            result = messagebox.askyesnocancel(
                "Carpeta existente en R2",
                f"La carpeta '{folder_name}' ya existe en el servidor.\n\n"
                f"¿Qué deseas hacer?\n\n"
                f"• SÍ = Sobrescribir las imágenes existentes\n"
                f"• NO = Usar un nombre diferente\n"
                f"• CANCELAR = Cancelar la exportación",
                icon='warning'
            )
            
            if result is None:
                return
            elif result is False:
                # Pedir nuevo nombre
                new_name = tk.simpledialog.askstring(
                    "Nuevo nombre de carpeta",
                    f"El nombre '{folder_name}' ya existe.\n\nIngresa un nuevo nombre:",
                    initialvalue=f"{folder_name}_v2"
                )
                
                if not new_name:
                    return
                
                folder_name = new_name
                self.output_name_var.set(new_name)
                self.output_folder = new_name
                self.images_folder = os.path.join(self.output_folder, "images")
                os.makedirs(self.images_folder, exist_ok=True)
        
        # Determinar la URL base según configuración
        brand = self.brand.get()
        campaign_type = self.campaign_type.get()
        
        # Para Discover, solo hay redención
        if brand == "discover":
            campaign_type = "redencion"
        
        # Obtener URL base para las imágenes
        if self.upload_to_r2.get() and brand in self.public_base_urls and campaign_type in self.public_base_urls[brand]:
            base_url = self.public_base_urls[brand][campaign_type] + folder_name + "/"
        else:
            base_url = "images/"
        
        # Procesar imágenes de plantilla
        self.copy_template_images(folder_name, r2_image_urls)
        
        # Recortar y guardar/subir imágenes (incluyendo GIFs)
        for i, slice_data in enumerate(self.slices):
            if slice_data["type"] == "image":
                # Procesar imagen JPG normal
                img = self.mockup_image.crop((
                    slice_data["x"],
                    slice_data["y"],
                    slice_data["x"] + slice_data["width"],
                    slice_data["y"] + slice_data["height"]
                ))
                
                # Guardar localmente
                local_path = os.path.join(self.images_folder, f"{slice_data['name']}.jpg")
                img.save(local_path, quality=95)
                
                # Subir a R2 si está habilitado
                if self.upload_to_r2.get():
                    # Convertir imagen a bytes
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='JPEG', quality=95)
                    img_byte_arr = img_byte_arr.getvalue()
                    
                    success, url = self.upload_image_to_r2(
                        img_byte_arr,
                        f"{slice_data['name']}.jpg",
                        folder_name
                    )
                    
                    if success:
                        r2_image_urls[f"{slice_data['name']}.jpg"] = url
            
            elif slice_data["type"] == "gif" and hasattr(self, 'gif_paths') and i in self.gif_paths:
                # Procesar GIF
                gif_path = self.gif_paths[i]
                gif_filename = f"{slice_data['name']}.gif"
                local_gif_path = os.path.join(self.images_folder, gif_filename)
                
                # Copiar GIF localmente
                shutil.copy(gif_path, local_gif_path)
                
                # Subir GIF a R2 si está habilitado
                if self.upload_to_r2.get():
                    with open(gif_path, 'rb') as f:
                        gif_data = f.read()
                    
                    success, url = self.upload_image_to_r2(
                        gif_data,
                        gif_filename,
                        folder_name
                    )
                    
                    if success:
                        r2_image_urls[gif_filename] = url
                        print(f"✅ GIF subido: {gif_filename} -> {url}")
        
        # Generar HTML con las URLs correctas
        self.generate_html(base_url, r2_image_urls)
        
        # Mensaje de éxito
        success_msg = f"""🚀 EXPORTACIÓN COMPLETADA

✅ {len(self.slices)} recortes procesados
✅ HTML generado: {self.output_folder}/index.html
✅ Imágenes guardadas en: {self.images_folder}"""
        
        if self.upload_to_r2.get():
            success_msg += f"\n✅ Imágenes subidas a R2: {base_url}"
        
        success_msg += f"""

Configuración utilizada:
- Marca: {self.brand.get().upper()}"""
        
        # AGREGAR versión de template si es ClubMiles
        if self.brand.get() == "clubmiles":
            template_desc = "V2 (Plomo)" if self.template_version.get() == "v2" else "V1 (Normal)"
            success_msg += f"\n- Template: {template_desc}"
        
        success_msg += f"""
- Tipo: {self.campaign_type.get().upper()}
- Plataforma: {self.platform.get().upper()}
- Header: {self.header_type.get().replace('_', ' ').title()}"""
        
        if self.platform.get() == "mautic" and self.preheader_text.get():
            success_msg += f"\n• Preheader: {self.preheader_text.get()[:50]}..."
        
        messagebox.showinfo("🎉 Exportación Exitosa", success_msg)
    
    def copy_template_images(self, folder_name, r2_image_urls):
        """Copia las imágenes de plantilla y las sube a R2 si está habilitado"""
        brand = self.brand.get()
        
        template_images = {
            "clubmiles": {
                "header": ["clubmiles.jpg"],
                "footer": ["footer_2.jpg", "facebook.jpg", "instagram.jpg", 
                          "whatsapp.jpg", "youtube.jpg", "footer_3.jpg", "cierre.jpg"]
            },
            "bgr": {
                "header": ["cabecera.jpg"],
                "footer": ["consulta.jpg", "bgrvisamiles.jpg", "cards.jpg", 
                          "redes_sociales.jpg", "facebook.jpg", "instagram.jpg", 
                          "youtube.jpg", "bgr_visa.jpg", "cierre.jpg"]
            },
            "discover": {
                "header": ["index_r1_c1.jpg"],
                "footer": ["index_r10_c1.jpg", "index_r11_c1.jpg", "index_r11_c3.jpg",
                          "index_r11_c4.jpg", "index_r11_c6.jpg", "index_r11_c7.jpg",
                          "index_r11_c8.jpg", "index_r12_c1.jpg"]
            }
        }
        
        # Carpetas de búsqueda
        if brand == "clubmiles":
            # MODIFICADO: Elegir carpeta según versión de template
            if self.template_version.get() == "v2":
                folder_suffix = "images_club_miles_v2_plomo"
            else:
                folder_suffix = "images_club_miles"
                
            source_folders = [
                folder_suffix,
                os.path.join(os.path.dirname(__file__), folder_suffix),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), folder_suffix),
                f"C:/Users/david.vargas/Desktop/Automatizacion_Fireworks/{folder_suffix}"
            ]
        elif brand == "bgr":
            source_folders = [
                "images_bgr",
                os.path.join(os.path.dirname(__file__), "images_bgr"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "images_bgr"),
                "C:/Users/david.vargas/Desktop/Automatizacion_Fireworks/images_bgr"
            ]
        else:  # discover
            source_folders = [
                "images_discover",
                os.path.join(os.path.dirname(__file__), "images_discover"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "images_discover"),
                "C:/Users/david.vargas/Desktop/Automatizacion_Fireworks/images_discover"
            ]
        
        source_folder = None
        for folder in source_folders:
            if os.path.exists(folder):
                source_folder = folder
                break
        
        if source_folder and brand in template_images:
            all_images = template_images[brand]["header"] + template_images[brand]["footer"]
            
            for img_name in all_images:
                source_path = os.path.join(source_folder, img_name)
                dest_path = os.path.join(self.images_folder, img_name)
                
                try:
                    if os.path.exists(source_path):
                        shutil.copy(source_path, dest_path)
                        
                        # Subir a R2 si está habilitado
                        if self.upload_to_r2.get():
                            with open(source_path, 'rb') as f:
                                img_data = f.read()
                            
                            success, url = self.upload_image_to_r2(
                                img_data,
                                img_name,
                                folder_name
                            )
                            
                            if success:
                                r2_image_urls[img_name] = url
                    else:
                        # Crear placeholders con colores apropiados
                        if "facebook" in img_name:
                            if brand == "discover":
                                placeholder = Image.new('RGB', (55, 53), color='#3b5998')
                            elif brand == "clubmiles":
                                placeholder = Image.new('RGB', (47, 55), color='#3b5998')
                            else:
                                placeholder = Image.new('RGB', (35, 30), color='#3b5998')
                        elif "instagram" in img_name:
                            if brand == "discover":
                                placeholder = Image.new('RGB', (54, 53), color='#e1306c')
                            elif brand == "clubmiles":
                                placeholder = Image.new('RGB', (42, 55), color='#e1306c')
                            else:
                                placeholder = Image.new('RGB', (36, 30), color='#e1306c')
                        elif "whatsapp" in img_name:
                            placeholder = Image.new('RGB', (41, 55), color='#25d366')
                        elif "youtube" in img_name:
                            if brand == "discover":
                                placeholder = Image.new('RGB', (58, 53), color='#ff0000')
                            elif brand == "clubmiles":
                                placeholder = Image.new('RGB', (43, 55), color='#ff0000')
                            else:
                                placeholder = Image.new('RGB', (37, 30), color='#ff0000')
                        elif "twitter" in img_name or "index_r11_c3" in img_name:
                            placeholder = Image.new('RGB', (55, 53), color='#1DA1F2')
                        else:
                            placeholder = Image.new('RGB', (100, 50), color='gray')
                        placeholder.save(dest_path)
                        
                        # Subir placeholder a R2 si está habilitado
                        if self.upload_to_r2.get():
                            img_byte_arr = io.BytesIO()
                            placeholder.save(img_byte_arr, format='JPEG')
                            img_byte_arr = img_byte_arr.getvalue()
                            
                            success, url = self.upload_image_to_r2(
                                img_byte_arr,
                                img_name,
                                folder_name
                            )
                            
                            if success:
                                r2_image_urls[img_name] = url
                except Exception:
                    # Crear placeholder genérico
                    placeholder = Image.new('RGB', (100, 50), color='gray')
                    placeholder.save(dest_path)
    
    def generate_html(self, base_url, r2_image_urls=None):
        """Genera el archivo HTML con las URLs correctas"""
        brand = self.brand.get()
        platform = self.platform.get()
        header_type = self.header_type.get()
        
        # Si tenemos URLs de R2, usar esas; si no, usar la base_url
        def get_image_url(filename):
            if r2_image_urls and filename in r2_image_urls:
                return r2_image_urls[filename]
            else:
                return f"{base_url}{filename}"
        
        # Configurar greeting según plataforma, marca y tipo
        if brand == "discover":
            # Discover solo tiene opción de nombre
            if platform == "braze":
                greeting_html = '''<td width="700" height="50" style="background-color:#e3e3e3;color:#000000;font-family:sans-serif;font-size:22px; text-align:center;">
<strong>Hola, {{${first_name}}}</strong>
</td>'''
            else:  # mautic
                greeting_html = '''<td width="700" height="50" style="background-color:#e3e3e3;color:#000000;font-family:sans-serif;font-size:22px; text-align:center;">
<strong>Hola, {contactfield=firstname}</strong>
</td>'''
        else:
            # ClubMiles y BGR
            if platform == "braze":
                if header_type == "name_only":
                    greeting_html = '''<td width="700" height="68" style="background-color:#EBEFF2;color:#358EF2;font-family:sans-serif;font-size:22px;text-align: center">
<strong>Hola, {{${first_name}}}</strong>
</td>'''
                else:
                    greeting_html = '''<td width="700" height="68" style="background-color:#EBEFF2;color:#358EF2;font-family:sans-serif;font-size:22px;text-align: center">
<strong>Hola, {{${first_name}}}</strong><br/>
<span style="color:#84898f">Tienes {{custom_attribute.${miles_balance}}} millas</span>
</td>'''
            else:  # mautic
                if header_type == "name_only":
                    greeting_html = '''<td width="700" height="70" style="background-color:#EBEFF2;color:#001751;font-family:sans-serif;font-size:22px;text-align: center">
<strong>Hola, {contactfield=firstname}</strong>
</td>'''
                else:
                    greeting_html = '''<td width="700" height="68" style="background-color:#EBEFF2;color:#001751;font-family:sans-serif;font-size:22px;text-align: center">
<strong>Hola, {contactfield=firstname}</strong> <br/>
<span style="background-color:#EBEFF2;color:#000f4a;font-family:sans-serif;font-size:22px; text-align: center;">Tienes {contactfield=balance_miles_txt} millas</span>
</td>'''
        
        if brand == "clubmiles":
            html = self.generate_clubmiles_html(greeting_html, platform, get_image_url)
        elif brand == "bgr":
            html = self.generate_bgr_html(greeting_html, platform, get_image_url)
        else:  # discover
            html = self.generate_discover_html(greeting_html, platform, get_image_url)
        
        with open(os.path.join(self.output_folder, "index.html"), 'w', encoding='utf-8') as f:
            f.write(html)
    
    def generate_clubmiles_html(self, greeting_html, platform, get_image_url):
        """Genera HTML para ClubMiles con URLs correctas"""
        if platform == "mautic":
            preheader_text = self.preheader_text.get() if self.preheader_text.get() else "Preheader"
            opening = f'''<span class="preheader">
 {preheader_text}
 </span>
<center>
 <table width="100%">
 <tr>
 <td>
 <center>'''
        else:
            opening = '''<center>
 <table width="100%">
 <tr>
 <td>
 <center>'''
        
        html = '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>ClubMiles</title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<style type="text/css">
html, body, div, form, fieldset, legend, label, img, tr
{
margin: 0;
padding: 0;
}
table
{
border-collapse: collapse;
border-spacing: 0;
font-size:0;
}
th, td
{
text-align: left;
}
h1, h2, h3, h4, h5, h6, th, td, caption { font-weight:normal; }
img { border: 0; display:block; padding:0; margin:0;}
div {
 display:block !important;
 }
 span.preheader { display: none !important; }
</style>
</head>
<body bgcolor="#ffffff">
'''
        html += opening
        html += f'''
<table border="0" cellpadding="0" cellspacing="0" width="700">
<tr>
<td><img style="display:block" src="{get_image_url('clubmiles.jpg')}" width="700" height="89" alt="" /></td>
</tr>
<tr>
'''
        html += greeting_html
        html += '''
</tr>
'''
        
        # Organizar recortes en filas
        rows = self.organize_slices_for_html()
        
        # Agregar cada fila
        for row in rows:
            if len(row) == 1:
                slice_data = row[0]
                if slice_data["has_url"] and slice_data["url"]:
                    html += f'<tr>\n<td><a href="{slice_data["url"]}" target="_blank">'
                else:
                    html += '<tr>\n<td>'
                
                if slice_data["type"] == "gif":
                    html += f'<img style="display:block" src="{get_image_url(slice_data["name"] + ".gif")}" '
                else:
                    html += f'<img style="display:block" src="{get_image_url(slice_data["name"] + ".jpg")}" '
                
                html += f'width="{slice_data["width"]}" height="{slice_data["height"]}" alt="" />'
                
                if slice_data["has_url"] and slice_data["url"]:
                    html += '</a>'
                html += '</td>\n</tr>\n'
            else:
                html += '<tr>\n<td>\n<table border="0" cellpadding="0" cellspacing="0" width="700">\n<tr>\n'
                
                for slice_data in row:
                    if slice_data["has_url"] and slice_data["url"]:
                        html += f'<td><a href="{slice_data["url"]}" target="_blank">'
                    else:
                        html += '<td>'
                    
                    if slice_data["type"] == "gif":
                        html += f'<img style="display:block" src="{get_image_url(slice_data["name"] + ".gif")}" '
                    else:
                        html += f'<img style="display:block" src="{get_image_url(slice_data["name"] + ".jpg")}" '
                    
                    html += f'width="{slice_data["width"]}" height="{slice_data["height"]}" alt="" />'
                    
                    if slice_data["has_url"] and slice_data["url"]:
                        html += '</a>'
                    html += '</td>\n'
                
                html += '</tr>\n</table>\n</td>\n</tr>\n'
        
        # Footer ClubMiles con URLs correctas
        html += f'''<tr>
<td><table border="0" cellpadding="0" cellspacing="0" width="700">
<tr>
<td><img style="display:block" src="{get_image_url('footer_2.jpg')}" width="509" height="55" alt="" /></td>
<td><a href="https://www.facebook.com/ClubMiles/" target="_blank"><img style="display:block" src="{get_image_url('facebook.jpg')}" width="46" height="55" alt="Facebook" /></a></td>
<td><a href="https://instagram.com/clubmiles_ec?igshid=YmMyMTA2M2Y=" target="_blank"><img style="display:block" src="{get_image_url('instagram.jpg')}" width="41" height="55" alt="Instagram" /></a></td>
<td><a href="https://wa.me/593963040040" target="_blank"><img style="display:block" src="{get_image_url('whatsapp.jpg')}" width="41" height="55" alt="Whatsapp" /></a></td>
<td><a href="https://www.youtube.com/channel/UCJ5qTUrByNb6u9XiQ39xmHA" target="_blank"><img style="display:block" src="{get_image_url('youtube.jpg')}" width="44" height="55" alt="Youtube" /></a></td>
<td><img style="display:block" src="{get_image_url('footer_3.jpg')}" width="19" height="55" alt="" /></td>
</tr>
</table></td>
</tr>
<tr>
<td><img style="display:block" src="{get_image_url('cierre.jpg')}" width="700" height="33" alt="" /></td>
</tr>
</table>
 </center>
 </td>
 </tr>
 </table>
</center>
</body>
</html>
'''
        
        if platform == "braze":
            html += "{{${email_footer}}}"
        else:
            html += "{unsubscribe_text}"
        
        html += '''
'''
        return html
    
    def generate_bgr_html(self, greeting_html, platform, get_image_url):
        """Genera HTML para BGR con URLs correctas"""
        if platform == "mautic":
            preheader_text = self.preheader_text.get() if self.preheader_text.get() else "Preheader"
            opening = f'''<span class="preheader">
    {preheader_text}
    </span>
    <center>
    <table width="100%">
    <tr>
    <td>
    <center>'''
        else:
            opening = '''<center>
    <table width="100%">
    <tr>
    <td>
    <center>'''
        
        html = '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
    <title>BGR Visa Miles</title>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <style type="text/css">
    html, body, div, form, fieldset, legend, label, img, tr
    {
    margin: 0;
    padding: 0;
    }
    table
    {
    border-collapse: collapse;
    border-spacing: 0;
    font-size:0;
    }
    th, td
    {
    text-align: left;
    }
    h1, h2, h3, h4, h5, h6, th, td, caption { font-weight:normal; }
    img { border: 0; display:block; padding:0; margin:0;}
    div {
    display:block !important;
    }
    span.preheader { display: none !important; }
    </style>
    </head>
    <body bgcolor="#ffffff">
    '''
        html += opening
        html += f'''
    <table border="0" cellpadding="0" cellspacing="0" width="700">
    <tr>
    <td><img style="display:block" src="{get_image_url('cabecera.jpg')}" width="700" height="50" alt="" /></td>
    </tr>
    <tr>
    '''
        html += greeting_html
        html += '''
    </tr>
    '''
        
        # Organizar recortes en filas
        rows = self.organize_slices_for_html()
        
        # Agregar cada fila
        for row in rows:
            if len(row) == 1:
                slice_data = row[0]
                if slice_data["has_url"] and slice_data["url"]:
                    html += f'<tr>\n<td><a href="{slice_data["url"]}" target="_blank">'
                else:
                    html += '<tr>\n<td>'
                
                if slice_data["type"] == "gif":
                    html += f'<img style="display:block" src="{get_image_url(slice_data["name"] + ".gif")}" '
                else:
                    html += f'<img style="display:block" src="{get_image_url(slice_data["name"] + ".jpg")}" '
                
                html += f'width="{slice_data["width"]}" height="{slice_data["height"]}" alt="" />'
                
                if slice_data["has_url"] and slice_data["url"]:
                    html += '</a>'
                html += '</td>\n</tr>\n'
            else:
                html += '<tr>\n<td>\n<table border="0" cellpadding="0" cellspacing="0" width="700">\n<tr>\n'
                
                for slice_data in row:
                    if slice_data["has_url"] and slice_data["url"]:
                        html += f'<td><a href="{slice_data["url"]}" target="_blank">'
                    else:
                        html += '<td>'
                    
                    if slice_data["type"] == "gif":
                        html += f'<img style="display:block" src="{get_image_url(slice_data["name"] + ".gif")}" '
                    else:
                        html += f'<img style="display:block" src="{get_image_url(slice_data["name"] + ".jpg")}" '
                    
                    html += f'width="{slice_data["width"]}" height="{slice_data["height"]}" alt="" />'
                    
                    if slice_data["has_url"] and slice_data["url"]:
                        html += '</a>'
                    html += '</td>\n'
                
                html += '</tr>\n</table>\n</td>\n</tr>\n'
        
        # Footer BGR
        html += f'''<tr>
    <td><table border="0" cellpadding="0" cellspacing="0" width="700">
    <tr>
    <td><img style="display:block" src="{get_image_url('redes_sociales.jpg')}" width="25" height="30" alt="" /></td>
    <td><a href="https://www.facebook.com/BGRoficial?mibextid=LQQJ4d" target="_blank"><img style="display:block" src="{get_image_url('facebook.jpg')}" width="35" height="30" alt="Facebook" /></a></td>
    <td><a href="https://instagram.com/bgr_ecuador?igshid=NTc4MTIwNjQ2YQ==" target="_blank"><img style="display:block" src="{get_image_url('instagram.jpg')}" width="36" height="30" alt="Instagram" /></a></td>
    <td><a href="https://youtube.com/@MERCADEOBGR" target="_blank"><img style="display:block" src="{get_image_url('youtube.jpg')}" width="37" height="30" alt="Youtube" /></a></td>
    <td><img style="display:block" src="{get_image_url('bgr_visa.jpg')}" width="567" height="30" alt="" /></td>
    </tr>
    </table></td>
    </tr>
    <tr>
    <td><img style="display:block" src="{get_image_url('cierre.jpg')}" width="700" height="46" alt="" /></td>
    </tr>
    </table>
    </center>
    </td>
    </tr>
    </table>
    </center>
    </body>
    </html>
    '''
        
        if platform == "braze":
            html += "{{${email_footer}}}"
        else:
            html += "{unsubscribe_text}"
        
        html += '''
    '''
        return html

    def generate_discover_html(self, greeting_html, platform, get_image_url):
        """Genera HTML para Discover con URLs correctas"""
        if platform == "mautic":
            preheader_text = self.preheader_text.get() if self.preheader_text.get() else "Preheader"
            opening = f'''<span class="preheader">
    {preheader_text}
    </span>
    <center>
    <table width="100%">
    <tr>
    <td>
    <center>'''
        else:
            opening = '''<center>
    <table width="100%">
    <tr>
    <td>
    <center>'''
        
        html = '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
    <title>Discover CashBack</title>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <style type="text/css">
    html, body, div, form, fieldset, legend, label, img, tr
    {
    margin: 0;
    padding: 0;
    }
    table
    {
    border-collapse: collapse;
    border-spacing: 0;
    font-size:0;
    }
    th, td
    {
    text-align: left;
    }
    h1, h2, h3, h4, h5, h6, th, td, caption { font-weight:normal; }
    img { border: 0; display:block; padding:0; margin:0;}
    div {
    display:block !important;
    }
    span.preheader { display: none !important; }
    </style>
    </head>
    <body bgcolor="#ffffff">
    '''
        html += opening
        html += f'''
    <table border="0" cellpadding="0" cellspacing="0" width="700">
    <tr>
    <td><img style="display:block" src="{get_image_url('index_r1_c1.jpg')}" width="700" height="89" alt="" /></td>
    </tr>
    <tr>
    '''
        html += greeting_html
        html += '''
    </tr>
    '''
        
        # Organizar recortes en filas
        rows = self.organize_slices_for_html()
        
        # Agregar cada fila
        for row in rows:
            if len(row) == 1:
                slice_data = row[0]
                if slice_data["has_url"] and slice_data["url"]:
                    html += f'<tr>\n<td><a href="{slice_data["url"]}" target="_blank">'
                else:
                    html += '<tr>\n<td>'
                
                if slice_data["type"] == "gif":
                    html += f'<img style="display:block" src="{get_image_url(slice_data["name"] + ".gif")}" '
                else:
                    html += f'<img style="display:block" src="{get_image_url(slice_data["name"] + ".jpg")}" '
                
                html += f'width="{slice_data["width"]}" height="{slice_data["height"]}" alt="" />'
                
                if slice_data["has_url"] and slice_data["url"]:
                    html += '</a>'
                html += '</td>\n</tr>\n'
            else:
                html += '<tr>\n<td>\n<table border="0" cellpadding="0" cellspacing="0" width="700">\n<tr>\n'
                
                for slice_data in row:
                    if slice_data["has_url"] and slice_data["url"]:
                        html += f'<td><a href="{slice_data["url"]}" target="_blank">'
                    else:
                        html += '<td>'
                    
                    if slice_data["type"] == "gif":
                        html += f'<img style="display:block" src="{get_image_url(slice_data["name"] + ".gif")}" '
                    else:
                        html += f'<img style="display:block" src="{get_image_url(slice_data["name"] + ".jpg")}" '
                    
                    html += f'width="{slice_data["width"]}" height="{slice_data["height"]}" alt="" />'
                    
                    if slice_data["has_url"] and slice_data["url"]:
                        html += '</a>'
                    html += '</td>\n'
                
                html += '</tr>\n</table>\n</td>\n</tr>\n'
        
        # Footer Discover
        html += f'''<tr>
    <td><img style="display:block" src="{get_image_url('index_r10_c1.jpg')}" width="700" height="50" alt="" /></td>
    </tr>
    <tr>
             <td><table style="display: inline-table;" align="left" border="0" cellpadding="0" cellspacing="0" width="700">
              <tr>
               <td><img style="display:block" name="index_r11_c1" src="{get_image_url('index_r11_c1.jpg')}" width="453" height="67" id="index_r11_c1" alt="" /></td>
               <td><a href="https://twitter.com/discoverecu?s=21&t=RhDLOB1Gi5VRakyuwoiC8g" target="_blank"><img style="display:block" name="index_r11_c3" src="{get_image_url('index_r11_c3.jpg')}" width="57" height="67" id="index_r11_c3" alt="X Discover" /></a></td>
               <td><a href="https://www.facebook.com/DiscoverEC?mibextid=LQQJ4d" target="_blank"><img style="display:block" name="index_r11_c4" src="{get_image_url('index_r11_c4.jpg')}" width="59" height="67" id="index_r11_c4" alt="Facebook Discover" /></a></td>
               <td><a href="https://www.instagram.com/discover_ec?igsh=MWdjc3g1NmVuaTA2Nw==" target="_blank"><img style="display:block" name="index_r11_c6" src="{get_image_url('index_r11_c6.jpg')}" width="56" height="67" id="index_r11_c6" alt="Instagram Discover" /></a></td>
               <td><a href="https://www.youtube.com/@DiscoverEcuador" target="_blank"><img style="display:block" name="index_r11_c7" src="{get_image_url('index_r11_c7.jpg')}" width="75" height="67" id="index_r11_c7" alt="Youtube Discover" /></a></td>
              </tr>
            </table></td>
            </tr>
            <tr>
             <td><img style="display:block" name="index_r12_c1" src="{get_image_url('index_r12_c1.jpg')}" width="700" height="78" id="index_r12_c1" alt="" /></td>
            </tr>
          </table>
    </center>
    </td>
    </tr>
    </table>
    </center>
    </body>
    </html>
    '''
        
        if platform == "braze":
            html += "{{${email_footer}}}"
        else:
            html += "{unsubscribe_text}"
        
        return html


class ConfigWindow:
    """Ventana de configuración optimizada"""
    def __init__(self, parent, app):
        self.app = app
        self.window = tk.Toplevel(parent)
        self.window.title("🔧 Configuración de Exportación")
        self.window.geometry("950x700")
        self.window.configure(bg="#F0F0F0")
        self.gif_paths = {}
        
        self.setup_ui()
    
    def setup_ui(self):
        # Header
        header_frame = tk.Frame(self.window, bg="#FF6B35", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="🔧# Continuación de ConfigWindow...")
        tk.Label(header_frame, text="🔧 CONFIGURACIÓN DE EXPORTACIÓN", 
                font=("Arial", 16, "bold"), bg="#FF6B35", fg="white").pack(pady=20)
        
        # Frame principal con scroll
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas con scrollbar
        canvas = tk.Canvas(main_frame, bg="white")
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Información del proyecto
        info_frame = ttk.LabelFrame(scrollable_frame, text="📋 Información del Proyecto", padding="15")
        info_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10, padx=10, ipady=10)
        
        info_text = f"""Recortes a procesar: {len(self.app.slices)}
Imagen origen: {os.path.basename(self.app.mockup_path) if self.app.mockup_path else 'Sin imagen'}
Carpeta destino: {self.app.output_folder}
Configuración: {self.app.brand.get().upper()}"""
        
        # Agregar versión de template si es ClubMiles
        if self.app.brand.get() == "clubmiles":
            template_desc = "V2 (Plomo)" if self.app.template_version.get() == "v2" else "V1 (Normal)"
            info_text += f" | Template: {template_desc}"
        
        info_text += f" | {self.app.campaign_type.get().upper()} | {self.app.platform.get().upper()} | {self.app.header_type.get().replace('_', ' ').title()}"
        
        if self.app.upload_to_r2.get():
            brand = self.app.brand.get()
            campaign_type = self.app.campaign_type.get()
            if brand == "discover":
                campaign_type = "redencion"
            
            if brand in self.app.public_base_urls and campaign_type in self.app.public_base_urls[brand]:
                info_text += f"\nDestino R2: {self.app.public_base_urls[brand][campaign_type]}{self.app.output_name_var.get()}/"
        
        if self.app.platform.get() == "mautic" and self.app.preheader_text.get():
            info_text += f"\nPreheader: {self.app.preheader_text.get()}"
        
        tk.Label(info_frame, text=info_text, font=("Consolas", 9), 
                justify=tk.LEFT, bg="white", relief=tk.SUNKEN, padx=10, pady=10).pack(fill=tk.X)
        
        # Título de configuración
        ttk.Label(scrollable_frame, text="⚙️ Configurar cada recorte:", 
                 font=("Arial", 12, "bold")).grid(row=1, column=0, columnspan=3, pady=20)
        
        # Crear configuración para cada recorte
        for i, slice_data in enumerate(self.app.slices):
            self.create_slice_config(scrollable_frame, i, slice_data, i+2)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Botones
        button_frame = tk.Frame(self.window, bg="#F0F0F0", height=80)
        button_frame.pack(fill=tk.X, pady=10)
        button_frame.pack_propagate(False)
        
        tk.Button(button_frame, text="🚀 GENERAR HTML Y EXPORTAR", 
                 command=self.generate,
                 bg="#4CAF50", fg="white", font=("Arial", 12, "bold"),
                 padx=30, pady=15, cursor="hand2").pack(side=tk.RIGHT, padx=20, pady=20)
        
        tk.Button(button_frame, text="❌ Cancelar", 
                 command=self.window.destroy,
                 bg="#757575", fg="white", font=("Arial", 10),
                 padx=20, pady=15).pack(side=tk.RIGHT, padx=10, pady=20)
    
    def create_slice_config(self, parent, index, slice_data, row):
        """Crea la configuración para un recorte"""
        # Frame principal del recorte
        main_frame = ttk.LabelFrame(parent, text=f"🗄️ Recorte {index+1}: {slice_data['name']}", padding="15")
        main_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10, padx=10)
        
        main_frame.columnconfigure(1, weight=1)
        
        # Preview del recorte
        preview_frame = tk.Frame(main_frame, relief=tk.SUNKEN, bd=2)
        preview_frame.grid(row=0, column=0, rowspan=4, padx=15, pady=5)
        
        try:
            img = self.app.mockup_image.crop((
                slice_data["x"], slice_data["y"],
                slice_data["x"] + slice_data["width"],
                slice_data["y"] + slice_data["height"]
            ))
            img.thumbnail((120, 120), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            label = tk.Label(preview_frame, image=photo, relief=tk.SUNKEN, bd=1)
            label.image = photo
            label.pack(padx=5, pady=5)
            
            # Info del recorte
            info_label = tk.Label(preview_frame, 
                                text=f"{slice_data['width']}×{slice_data['height']} px\nPos: {slice_data['x']},{slice_data['y']}", 
                                font=("Consolas", 8), fg="#666")
            info_label.pack()
        except:
            tk.Label(preview_frame, text="Preview\nno disponible", 
                    font=("Arial", 8), fg="#666", width=15, height=8).pack(padx=5, pady=5)
        
        # Configuración del tipo
        type_frame = ttk.LabelFrame(main_frame, text="Tipo de archivo", padding="10")
        type_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=15, pady=5)
        
        type_var = tk.StringVar(value=slice_data.get("type", "image"))
        slice_data["type_var"] = type_var
        
        ttk.Radiobutton(type_frame, text="📷 Imagen JPG (Recomendado)", 
                       variable=type_var, value="image").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(type_frame, text="🎞️ GIF Animado", 
                       variable=type_var, value="gif", 
                       command=lambda: self.on_type_change(index)).pack(anchor=tk.W, pady=2)
        
        # Configuración de URL
        url_frame = ttk.LabelFrame(main_frame, text="Enlace web", padding="10")
        url_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=15, pady=5)
        
        has_url_var = tk.BooleanVar(value=slice_data.get("has_url", False))
        slice_data["has_url_var"] = has_url_var
        
        ttk.Checkbutton(url_frame, text="🔗 Este recorte tiene un enlace web", 
                       variable=has_url_var,
                       command=lambda: self.on_url_change(index)).pack(anchor=tk.W, pady=2)
        
        # Campo URL
        url_input_frame = ttk.Frame(url_frame)
        url_input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(url_input_frame, text="URL completa:").pack(anchor=tk.W)
        url_entry = ttk.Entry(url_input_frame, font=("Consolas", 9))
        url_entry.pack(fill=tk.X, pady=2)
        
        slice_data["url_entry"] = url_entry
        slice_data["url_input_frame"] = url_input_frame
        
        if not has_url_var.get():
            url_input_frame.pack_forget()
        
        # Frame para GIF
        gif_frame = ttk.LabelFrame(main_frame, text="Archivo GIF", padding="10")
        gif_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=15, pady=5)
        
        gif_status_frame = ttk.Frame(gif_frame)
        gif_status_frame.pack(fill=tk.X)
        
        gif_label = ttk.Label(gif_status_frame, text="❌ No seleccionado", 
                             foreground="red", font=("Arial", 9))
        gif_label.pack(side=tk.LEFT)
        
        ttk.Button(gif_status_frame, text="📁 Seleccionar GIF", 
                  command=lambda: self.select_gif(index, gif_label)).pack(side=tk.RIGHT)
        
        slice_data["gif_frame"] = gif_frame
        slice_data["gif_label"] = gif_label
        
        # Mostrar/ocultar según el tipo inicial
        if type_var.get() != "gif":
            gif_frame.grid_remove()
    
    def on_type_change(self, index):
        """Maneja el cambio de tipo"""
        slice_data = self.app.slices[index]
        if slice_data["type_var"].get() == "gif":
            slice_data["gif_frame"].grid()
        else:
            slice_data["gif_frame"].grid_remove()
    
    def on_url_change(self, index):
        """Maneja el cambio de URL"""
        slice_data = self.app.slices[index]
        if slice_data["has_url_var"].get():
            slice_data["url_input_frame"].pack(fill=tk.X, pady=5)
        else:
            slice_data["url_input_frame"].pack_forget()
    
    def select_gif(self, index, label):
        """Selecciona archivo GIF"""
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo GIF animado",
            filetypes=[("Archivos GIF", "*.gif"), ("Todos los archivos", "*.*")]
        )
        
        if file_path:
            self.gif_paths[index] = file_path
            filename = os.path.basename(file_path)
            label.config(text=f"✅ {filename}", foreground="green")
    
    def generate(self):
        """Genera el output con validación"""
        # Validar configuración
        errors = []
        
        for i, slice_data in enumerate(self.app.slices):
            # Actualizar datos
            slice_data["type"] = slice_data["type_var"].get()
            slice_data["has_url"] = slice_data["has_url_var"].get()
            # Eliminar TODOS los espacios en blanco, saltos de línea, tabs, etc.
            if slice_data["has_url"]:
                url = slice_data["url_entry"].get()
                # Método más robusto: elimina CUALQUIER tipo de espacio en blanco
                url = ''.join(url.split())
                slice_data["url"] = url
            else:
                slice_data["url"] = ""
            
            # Validaciones
            if slice_data["type"] == "gif" and i not in self.gif_paths:
                errors.append(f"Recorte {i+1}: Se seleccionó GIF pero no se especificó archivo")
            
            if slice_data["has_url"] and not slice_data["url"]:
                errors.append(f"Recorte {i+1}: Se marcó 'tiene enlace' pero no se especificó URL")
            
            if slice_data["has_url"] and slice_data["url"] and not slice_data["url"].startswith(('http://', 'https://')):
                errors.append(f"Recorte {i+1}: La URL debe comenzar con http:// o https://")
        
        # Mostrar errores si los hay
        if errors:
            messagebox.showerror("Errores de Configuración", 
                               "Se encontraron errores:\n\n" + "\n".join(errors))
            return
        
        # Guardar rutas de GIFs para procesarlas después
        self.app.gif_paths = self.gif_paths
        
        # Cerrar ventana y generar
        self.window.destroy()
        self.app.generate_output()


if __name__ == "__main__":
    app = ManualWebSlicer()
    app.root.mainloop()