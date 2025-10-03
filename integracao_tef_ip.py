import os
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

class TEFIPIntegration:
    def __init__(self, root):
        self.root = root
        self.root.title("Integração TEF-IP Auttar")
        self.root.geometry("800x600")
        
        # Diretórios
        self.req_dir = r"C:\TEF_DIAL\REQ"
        self.resp_dir = r"C:\TEF_DIAL\RESP"
        
        # Variáveis
        self.running = False
        self.last_id = 0
        
        # Criar interface
        self.create_widgets()
        
        # Verificar diretórios
        self.verify_directories()
        
        # Iniciar monitoramento
        self.start_monitoring()
    
    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Frame de operações
        op_frame = ttk.LabelFrame(main_frame, text="Operações", padding="10")
        op_frame.pack(fill=tk.X, pady=5)
        
        # Botões de operações
        ttk.Button(op_frame, text="Crédito à Vista", command=self.credito_vista).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(op_frame, text="Débito", command=self.debito).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(op_frame, text="Crédito Parcelado", command=self.credito_parcelado).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(op_frame, text="Cancelar", command=self.cancelar).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(op_frame, text="PIX QRCODE", command=self.pix_qrcode).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(op_frame, text="Administrativa", command=self.administrativa).grid(row=1, column=2, padx=5, pady=5)
        
        # Frame de dados
        data_frame = ttk.LabelFrame(main_frame, text="Dados", padding="10")
        data_frame.pack(fill=tk.X, pady=5)
        
        # Campos
        ttk.Label(data_frame, text="Valor:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.valor_entry = ttk.Entry(data_frame)
        self.valor_entry.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(data_frame, text="Doc. Fiscal:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.doc_fiscal_entry = ttk.Entry(data_frame)
        self.doc_fiscal_entry.grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Label(data_frame, text="NSU:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.nsu_entry = ttk.Entry(data_frame)
        self.nsu_entry.grid(row=2, column=1, padx=5, pady=2)
        
        # Frame de parcelamento
        parcel_frame = ttk.LabelFrame(main_frame, text="Parcelamento", padding="10")
        parcel_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(parcel_frame, text="Tipo:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.tipo_parcelamento_var = tk.StringVar(value="0")
        ttk.Radiobutton(parcel_frame, text="Estabelecimento", variable=self.tipo_parcelamento_var, value="0").grid(row=0, column=1, padx=5, pady=2)
        ttk.Radiobutton(parcel_frame, text="Administradora", variable=self.tipo_parcelamento_var, value="1").grid(row=0, column=2, padx=5, pady=2)
        
        ttk.Label(parcel_frame, text="Parcelas:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.parcelas_entry = ttk.Entry(parcel_frame, width=10)
        self.parcelas_entry.grid(row=1, column=1, padx=5, pady=2)
        
        # Frame de logs
        log_frame = ttk.LabelFrame(main_frame, text="Logs", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Barra de status
        self.status_var = tk.StringVar()
        self.status_var.set("Pronto")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=5)
    
    def verify_directories(self):
        """Verifica e cria os diretórios necessários"""
        try:
            os.makedirs(self.req_dir, exist_ok=True)
            os.makedirs(self.resp_dir, exist_ok=True)
            self.log("Diretórios verificados")
        except Exception as e:
            self.log(f"ERRO: {str(e)}")
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def create_request_file(self, operation, fields=None):
        """Cria arquivo de requisição"""
        try:
            # Criar arquivo temporário
            tmp_file = os.path.join(self.req_dir, "IntPos.tmp")
            
            with open(tmp_file, 'w') as f:
                f.write(f"000-000 = {operation}\n")
                f.write(f"001-000 = {self.generate_id()}\n")
                
                if fields:
                    for field, value in fields.items():
                        f.write(f"{field} = {value}\n")
                
                f.write("999-999 = 0\n")
            
            # Renomear para arquivo final
            final_file = os.path.join(self.req_dir, "IntPos.001")
            os.rename(tmp_file, final_file)
            
            self.log(f"Arquivo criado: {operation}")
            return True
        except Exception as e:
            self.log(f"ERRO: {str(e)}")
            return False
    
    def generate_id(self):
        self.last_id += 1
        return str(self.last_id).zfill(10)
    
    def credito_vista(self):
        """Crédito à Vista"""
        valor = self.valor_entry.get()
        doc_fiscal = self.doc_fiscal_entry.get()
        
        if not valor or not doc_fiscal:
            messagebox.showerror("Erro", "Preencha Valor e Documento Fiscal")
            return
        
        valor = valor.replace(",", "").replace(".", "")
        
        fields = {
            "002-000": doc_fiscal,
            "003-000": valor,
            "011-000": "10"
        }
        
        self.log(f"Crédito à Vista: R$ {valor}")
        self.create_request_file("CRT", fields)
        self.status_var.set("Aguardando resposta...")
    
    def debito(self):
        """Débito"""
        valor = self.valor_entry.get()
        doc_fiscal = self.doc_fiscal_entry.get()
        
        if not valor or not doc_fiscal:
            messagebox.showerror("Erro", "Preencha Valor e Documento Fiscal")
            return
        
        valor = valor.replace(",", "").replace(".", "")
        
        fields = {
            "002-000": doc_fiscal,
            "003-000": valor,
            "011-000": "20"
        }
        
        self.log(f"Débito: R$ {valor}")
        self.create_request_file("CRT", fields)
        self.status_var.set("Aguardando resposta...")
    
    def credito_parcelado(self):
        """Crédito Parcelado"""
        valor = self.valor_entry.get()
        doc_fiscal = self.doc_fiscal_entry.get()
        parcelas = self.parcelas_entry.get()
        tipo = self.tipo_parcelamento_var.get()
        
        if not valor or not doc_fiscal or not parcelas:
            messagebox.showerror("Erro", "Preencha todos os campos")
            return
        
        valor = valor.replace(",", "").replace(".", "")
        tipo_transacao = "11" if tipo == "0" else "12"
        
        fields = {
            "002-000": doc_fiscal,
            "003-000": valor,
            "011-000": tipo_transacao,
            "017-000": tipo,
            "018-000": parcelas
        }
        
        self.log(f"Crédito Parcelado: R$ {valor} em {parcelas}x")
        self.create_request_file("CRT", fields)
        self.status_var.set("Aguardando resposta...")
    
    def cancelar(self):
        """Cancelamento"""
        nsu = self.nsu_entry.get()
        doc_fiscal = self.doc_fiscal_entry.get()
        
        if not nsu or not doc_fiscal:
            messagebox.showerror("Erro", "Preencha NSU e Documento Fiscal")
            return
        
        fields = {
            "002-000": doc_fiscal,
            "012-000": nsu
        }
        
        self.log(f"Cancelamento: NSU {nsu}")
        self.create_request_file("CNC", fields)
        self.status_var.set("Aguardando resposta...")
    
    def pix_qrcode(self):
        """PIX QRCODE"""
        valor = self.valor_entry.get()
        doc_fiscal = self.doc_fiscal_entry.get()
        
        if not valor or not doc_fiscal:
            messagebox.showerror("Erro", "Preencha Valor e Documento Fiscal")
            return
        
        valor = valor.replace(",", "").replace(".", "")
        
        fields = {
            "002-000": doc_fiscal,
            "003-000": valor
        }
        
        self.log(f"PIX QRCODE: R$ {valor}")
        self.create_request_file("QRC", fields)
        self.status_var.set("Aguardando resposta...")
    
    def administrativa(self):
        """Operação Administrativa - executa diretamente"""
        # Executa diretamente a operação de cancelamento administrativo
        fields = {}
        
        # Se houver NSU preenchido, usa-o
        nsu = self.nsu_entry.get()
        if nsu:
            fields["012-000"] = nsu
        
        self.log("ADM: CANCELAMENTO")
        self.create_request_file("ADM", fields)
        self.status_var.set("Executando CANCELAMENTO...")
    
    def start_monitoring(self):
        self.running = True
        monitor_thread = threading.Thread(target=self.monitor_directories)
        monitor_thread.daemon = True
        monitor_thread.start()
    
    def monitor_directories(self):
        while self.running:
            try:
                # Verificar arquivo de status
                sts_file = os.path.join(self.resp_dir, "IntPos.Sts")
                if os.path.exists(sts_file):
                    with open(sts_file, 'r') as f:
                        content = f.read()
                        self.log(f"Status: {content.strip()}")
                    os.remove(sts_file)
                    self.status_var.set("CTFClient processando...")
                
                # Verificar arquivo de resposta
                resp_file = os.path.join(self.resp_dir, "IntPos.001")
                if os.path.exists(resp_file):
                    with open(resp_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("009-000 ="):
                                status = line.split("=")[1].strip()
                                self.status_var.set("APROVADO" if status == "0" else f"NEGADO ({status})")
                            elif line.startswith("012-000 ="):
                                nsu = line.split("=")[1].strip()
                                self.nsu_entry.delete(0, tk.END)
                                self.nsu_entry.insert(0, nsu)
                    
                    os.remove(resp_file)
                
                time.sleep(0.5)
            except Exception as e:
                self.log(f"ERRO: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = TEFIPIntegration(root)
    root.mainloop()