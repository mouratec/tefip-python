import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

class TefFileHandler:
    """Manipula a criação de arquivos seguindo o padrão estrito da Auttar."""
    
    @staticmethod
    def ler_arquivo(filepath):
        """Lê o arquivo de resposta tratando a codificação correta (ANSI/CP1252)."""
        dados = {}
        if not os.path.exists(filepath):
            return None
            
        try:
            # 'mbcs' é o encoding padrão para arquivos de texto legados no Windows (ANSI)
            with open(filepath, 'r', encoding='mbcs') as f:
                for linha in f:
                    linha = linha.strip()
                    if '=' in linha:
                        chave, valor = linha.split('=', 1)
                        dados[chave.strip()] = valor.strip()
        except Exception as e:
            print(f"Erro ao ler arquivo: {e}")
        return dados

    @staticmethod
    def escrever_arquivo(diretorio, dados_dict):
        """
        CRÍTICO: Escreve em .tmp e renomeia para .001.
        Isso garante que o TEF só leia o arquivo quando ele estiver completo.
        """
        caminho_tmp = os.path.join(diretorio, "IntPos.tmp")
        caminho_final = os.path.join(diretorio, "IntPos.001")

        try:
            # Força encoding ANSI para compatibilidade total
            with open(caminho_tmp, 'w', encoding='mbcs') as f:
                # O Header 000-000 DEVE ser a primeira linha
                if "000-000" in dados_dict:
                    f.write(f"000-000 = {dados_dict['000-000']}\n")
                    del dados_dict["000-000"]
                
                # Escreve os demais campos
                for k, v in dados_dict.items():
                    if v is not None:
                        f.write(f"{k} = {v}\n")
                
                # Trailer obrigatório
                f.write("999-999 = 0\n")
            
            # Remove o arquivo de destino se já existir (limpeza)
            if os.path.exists(caminho_final):
                os.remove(caminho_final)
                
            # Renomeia (Operação Atômica)
            os.rename(caminho_tmp, caminho_final)
            return True
        except Exception as e:
            print(f"Erro ao escrever arquivo: {e}")
            return False

    @staticmethod
    def limpar_diretorio(diretorio):
        """Remove arquivos .001, .Sts e .tmp antigos."""
        for item in os.listdir(diretorio):
            if item.endswith(".001") or item.endswith(".Sts") or item.endswith(".tmp"):
                try:
                    os.remove(os.path.join(diretorio, item))
                except:
                    pass

class TefApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Integração TEF-IP Auttar | Profissional")
        self.root.geometry("900x650")
        self.root.configure(bg="#2d2d2d")

        # --- CONFIGURAÇÃO DE DIRETÓRIOS ---
        self.dir_base = r"C:\Auttar_TefIP"
        self.dir_req = os.path.join(self.dir_base, "REQ")
        self.dir_resp = os.path.join(self.dir_base, "RESP")
        
        # Variáveis de Controle
        self.seq_id = 1
        self.processando = False

        self.setup_ui()
        self.check_dirs()

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#2d2d2d")
        style.configure("TLabel", background="#2d2d2d", foreground="white", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), background="#007acc", foreground="white")
        
        # Header
        header = ttk.Frame(self.root, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text="MOURATEC TEF", font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)
        self.lbl_status = ttk.Label(header, text="● AGUARDANDO", foreground="#00ff00")
        self.lbl_status.pack(side=tk.RIGHT)

        # Container Principal
        container = ttk.Frame(self.root, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        # Painel Esquerdo
        painel_inputs = ttk.Frame(container)
        painel_inputs.pack(side=tk.LEFT, fill=tk.Y, padx=10)

        self.add_input(painel_inputs, "Valor (R$):", "txt_valor", "10,00")
        self.add_input(painel_inputs, "Doc Fiscal:", "txt_doc", datetime.now().strftime("%H%M%S"))

        ttk.Button(painel_inputs, text="CRÉDITO", command=lambda: self.iniciar("CREDITO")).pack(fill=tk.X, pady=5)
        ttk.Button(painel_inputs, text="DÉBITO", command=lambda: self.iniciar("DEBITO")).pack(fill=tk.X, pady=5)
        ttk.Button(painel_inputs, text="CANCELAR ÚLTIMA (NCN)", command=self.forcar_cancelamento).pack(fill=tk.X, pady=20)

        # Painel Direito (Log)
        painel_log = ttk.Frame(container)
        painel_log.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        ttk.Label(painel_log, text="Log de Execução:").pack(anchor="w")
        self.txt_log = scrolledtext.ScrolledText(painel_log, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 9))
        self.txt_log.pack(fill=tk.BOTH, expand=True)
        self.txt_log.tag_config("INFO", foreground="#569cd6")
        self.txt_log.tag_config("SUCCESS", foreground="#4ec9b0")
        self.txt_log.tag_config("ERROR", foreground="#f44747")

    def add_input(self, parent, label, var_name, default):
        ttk.Label(parent, text=label).pack(anchor="w")
        entry = ttk.Entry(parent)
        entry.insert(0, default)
        entry.pack(fill=tk.X, pady=(0, 10))
        setattr(self, var_name, entry)

    def log(self, msg, tipo="INFO"):
        hora = datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{hora}] {msg}\n", tipo)
        self.txt_log.see(tk.END)

    def check_dirs(self):
        try:
            os.makedirs(self.dir_req, exist_ok=True)
            os.makedirs(self.dir_resp, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível criar pastas: {e}")

    def iniciar(self, operacao):
        if self.processando: return
        threading.Thread(target=self.fluxo_transacao, args=(operacao,)).start()

    def fluxo_transacao(self, operacao):
        self.processando = True
        self.lbl_status.config(text="● PROCESSANDO...", foreground="yellow")
        self.log(f"--- Iniciando {operacao} ---")

        # 1. Limpeza
        TefFileHandler.limpar_diretorio(self.dir_resp)
        TefFileHandler.limpar_diretorio(self.dir_req)

        valor = self.txt_valor.get().replace(",", "").replace(".", "")
        doc = self.txt_doc.get()
        id_transacao = str(self.seq_id).zfill(10)
        self.seq_id += 1

        try:
            # 2. Requisição (CRT)
            req = {
                "000-000": "CRT",
                "001-000": id_transacao,
                "002-000": doc,
                "003-000": valor,
                "011-000": "10" if operacao == "CREDITO" else "20",
                "999-999": "0"
            }
            
            self.log("Enviando solicitação (CRT)...")
            if not TefFileHandler.escrever_arquivo(self.dir_req, req):
                raise Exception("Falha na escrita do arquivo")

            # 3. Aguarda recebimento (IntPos.Sts)
            self.log("Aguardando CTFClient (Sts)...")
            inicio = time.time()
            sts_ok = False
            while time.time() - inicio < 10:
                if os.path.exists(os.path.join(self.dir_resp, "IntPos.Sts")):
                    try:
                        os.remove(os.path.join(self.dir_resp, "IntPos.Sts"))
                        sts_ok = True
                        break
                    except: pass
                time.sleep(0.5)
            
            if not sts_ok:
                raise Exception("Timeout: CTFClient não respondeu (Verifique se está rodando).")

            # 4. Aguarda Resposta Final (IntPos.001)
            self.log("Aguardando senha no Pinpad...")
            resp_dados = None
            caminho_resp = os.path.join(self.dir_resp, "IntPos.001")
            
            while self.processando:
                if os.path.exists(caminho_resp):
                    time.sleep(0.5) # Garante fim da escrita pelo Java
                    resp_dados = TefFileHandler.ler_arquivo(caminho_resp)
                    try: os.remove(caminho_resp)
                    except: pass
                    break
                time.sleep(1)

            if not resp_dados: return

            status = resp_dados.get("009-000", "99")
            msg = resp_dados.get("030-000", "")
            
            if status == "0": # APROVADA
                self.log(f"APROVADA: {msg}", "SUCCESS")
                
                # --- PONTO CRÍTICO: CONFIRMAÇÃO ---
                # É necessário pegar os dados exatos que o servidor retornou
                # para confirmar a transação correta.
                
                rede_adquirente = resp_dados.get("010-000") # Ex: GETNET, REDECARD
                nsu_host = resp_dados.get("012-000")        # Ex: 000000006
                
                if not rede_adquirente or not nsu_host:
                    self.log("ALERTA: Rede ou NSU não retornados. Tentando confirmar mesmo assim...", "ERROR")

                # Simula tempo de impressão e processamento do CTFClient (Evita erro de arquivo travado)
                self.log("Estabilizando (2s)...")
                time.sleep(2)

                confirmar = messagebox.askyesno("Impressão", "O comprovante foi impresso corretamente?")
                
                cnf_req = {
                    "000-000": "CNF" if confirmar else "NCN",
                    "001-000": id_transacao,
                    "002-000": doc,
                    "010-000": rede_adquirente, # OBRIGATÓRIO PARA SUCESSO
                    "012-000": nsu_host,        # OBRIGATÓRIO PARA SUCESSO
                    "027-000": datetime.now().strftime("%d%m%y%H%M%S"), # Data/Hora
                    "999-999": "0"
                }
                
                self.log(f"Enviando {cnf_req['000-000']}...")
                TefFileHandler.escrever_arquivo(self.dir_req, cnf_req)
                
                self.log("Fluxo finalizado.", "SUCCESS")
                messagebox.showinfo("Fim", f"Transação {'CONFIRMADA' if confirmar else 'DESFEITA'}")

            else:
                self.log(f"NEGADA ({status}): {msg}", "ERROR")
                messagebox.showerror("Negada", msg)

        except Exception as e:
            self.log(f"ERRO: {e}", "ERROR")
        
        finally:
            self.processando = False
            self.lbl_status.config(text="● PRONTO", foreground="#00ff00")

    def forcar_cancelamento(self):
        """Função de emergência para destravar transações pendentes."""
        # Cria um NCN genérico para tentar limpar a fila
        req = {
            "000-000": "NCN",
            "001-000": str(self.seq_id).zfill(10),
            "002-000": self.txt_doc.get(),
            "010-000": "PENDENTE", # Tenta forçar
            "999-999": "0"
        }
        TefFileHandler.escrever_arquivo(self.dir_req, req)
        self.log("Enviado NCN de emergência.", "INFO")

if __name__ == "__main__":
    root = tk.Tk()
    app = TefApp(root)
    root.mainloop()