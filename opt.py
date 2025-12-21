import os
import subprocess
import json
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import concurrent.futures
import threading
import time

# Configurações de Qualidade Alvo
TARGET_BITRATE = 160000  # 160kbps
TARGET_SAMPLERATE = 44100 # 44.1kHz

def get_audio_metadata(file_path):
    """
    Usa ffprobe para pegar dados do arquivo sem precisar abrir o áudio inteiro.
    É extremamente rápido.
    """
    try:
        command = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-select_streams", "a:0",
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        if not data["streams"]:
            return None

        stream = data["streams"][0]
        
        # Pega a Sample Rate (Taxa de Amostragem)
        sample_rate = int(stream.get("sample_rate", 0))
        
        # Pega o Bitrate. As vezes em VBR o ffprobe não mostra o bitrate no stream,
        # mas sim no container format. Se não achar, assumimos que é alto para garantir.
        bit_rate = int(stream.get("bit_rate", 999999)) 
        
        return sample_rate, bit_rate
    except Exception as e:
        print(f"Erro ao ler metadata de {file_path}: {e}")
        return None

def process_file(file_info):
    """
    Versão 2.0: Lógica inteligente que impede o aumento de tamanho
    em arquivos de baixo bitrate.
    """
    file_path, filename = file_info
    
    # 1. Verifica Metadata
    meta = get_audio_metadata(file_path)
    if not meta:
        return f"[ERRO] Não foi possível ler: {filename}"
    
    sample_rate, bit_rate = meta
    
    # --- NOVA LÓGICA INTELIGENTE ---
    
    # Define qual será o bitrate de saída.
    # A função min() escolhe o MENOR valor.
    # Exemplo 1: Original 320k, Alvo 160k -> Saída 160k (Reduziu)
    # Exemplo 2: Original 96k,  Alvo 160k -> Saída 96k  (Manteve, não inflou)
    output_bitrate = min(bit_rate, TARGET_BITRATE)
    
    needs_conversion = False
    
    # Critério 1: Sample Rate errado (acima de 44.1k)?
    if sample_rate > TARGET_SAMPLERATE:
        needs_conversion = True
    
    # Critério 2: Bitrate acima do limite?
    if bit_rate > TARGET_BITRATE:
        needs_conversion = True
        
    # Se a taxa e o bitrate já estão bons, pula
    if not needs_conversion:
        return f"[PULADO] Já otimizado: {filename}"

    # Prepara a string do bitrate para o FFmpeg (ex: converte 128000 para "128k")
    # Adicionamos uma margem de segurança pequena ou arredondamos
    output_bitrate_str = f"{int(output_bitrate / 1000)}k"

    # 2. Conversão
    temp_path = file_path + ".temp.m4a"
    
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i", file_path,
            "-vn", 
            "-c:a", "aac",
            "-b:a", output_bitrate_str,  # <--- AQUI ESTÁ A CORREÇÃO
            "-ar", "44100",              # Força 44.1kHz sempre
            temp_path
        ]
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        os.replace(temp_path, file_path)
        
        return f"[CONVERTIDO] {filename} -> {output_bitrate_str} | 44.1kHz"
        
    except subprocess.CalledProcessError:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return f"[FALHA] Erro ao converter: {filename}"
    except Exception as e:
        return f"[ERRO] {str(e)}: {filename}"

class AudioOptimizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Otimizador de Áudio GDevelop (Multiprocessado)")
        self.root.geometry("600x450")
        
        # Label Instrução
        tk.Label(root, text="Selecione a pasta raiz do seu projeto ou das músicas.", pady=10).pack()
        
        # Botão Selecionar
        self.btn_select = tk.Button(root, text="Selecionar Pasta e Iniciar", command=self.start_thread, bg="#4CAF50", fg="white", font=("Arial", 12, "bold"))
        self.btn_select.pack(pady=5)
        
        # Área de Log
        self.log_area = scrolledtext.ScrolledText(root, state='disabled', height=20)
        self.log_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        # Status
        self.status_label = tk.Label(root, text="Aguardando...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def start_thread(self):
        folder_selected = filedialog.askdirectory()
        if not folder_selected:
            return
        
        # Roda em thread separada para não travar a UI
        self.btn_select.config(state='disabled')
        threading.Thread(target=self.run_optimization, args=(folder_selected,), daemon=True).start()

    def run_optimization(self, root_folder):
        self.log(f"Iniciando varredura em: {root_folder}")
        self.log(f"Usando {os.cpu_count()} núcleos do processador.")
        
        files_to_process = []
        
        # 1. Coleta todos os arquivos
        for dirpath, _, filenames in os.walk(root_folder):
            for f in filenames:
                if f.lower().endswith('.aac'):
                    full_path = os.path.join(dirpath, f)
                    files_to_process.append((full_path, f))
        
        total_files = len(files_to_process)
        self.log(f"Encontrados {total_files} arquivos .aac. Iniciando processamento...")
        
        if total_files == 0:
            self.log("Nenhum arquivo encontrado.")
            self.btn_select.config(state='normal')
            return

        # 2. Processamento Paralelo
        # ProcessPoolExecutor é o segredo da velocidade aqui.
        start_time = time.time()
        
        with concurrent.futures.ProcessPoolExecutor() as executor:
            # Mapeia a função process_file para a lista de arquivos
            results = executor.map(process_file, files_to_process)
            
            for i, result in enumerate(results):
                self.log(result)
                # Atualiza status visualmente (opcional)
                self.status_label.config(text=f"Processando: {i+1}/{total_files}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        self.log("-" * 30)
        self.log(f"Concluído em {duration:.2f} segundos!")
        self.status_label.config(text="Concluído.")
        messagebox.showinfo("Sucesso", "Otimização finalizada!")
        self.btn_select.config(state='normal')

if __name__ == "__main__":
    # Fix necessário para Multiprocessing no Windows com PyInstaller ou Scripts diretos
    from multiprocessing import freeze_support
    freeze_support()
    
    root = tk.Tk()
    app = AudioOptimizerApp(root)
    root.mainloop()