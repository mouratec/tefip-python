import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

# =============================================================================
# CONFIGURAÇÕES E UTILITÁRIOS
# =============================================================================
class TefConfig:
    # Diretórios conforme Manual pág 11 
    DIR_BASE = r"C:\Auttar_TefIP"
    DIR_REQ = os.path.join(DIR_BASE, "REQ")
    DIR_RESP = os.path.join(DIR_BASE, "RESP")
    FILE_SEQ = "tef_sequence.dat"

class SequenceManager:
    """Gerencia o ID único da transação (Campo 001-000) [cite: 250]"""
    @staticmethod
    def get_next_id():
        current_id = 1
        if os.path.exists(TefConfig.FILE_SEQ):
            try:
                with open(TefConfig.FILE_SEQ, "r") as f:
                    content = f.read().strip()
                    if content.isdigit():
                        current_id = int(content)
            except: pass
        
        next_id = current_id + 1
        try:
            with open(TefConfig.FILE_SEQ, "w") as f:
                f.write(str(next_id))
        except: pass
            
        return str(current_id).zfill(10)

class TefFileHandler:
    """Manipulação de arquivos REQ/RESP conforme protocolo Auttar"""
    
    @staticmethod
    def setup_directories():
        os.makedirs(TefConfig.DIR_REQ, exist_ok=True)
        os.makedirs(TefConfig.DIR_RESP, exist_ok=True)
        # Limpeza preventiva
        for f in os.listdir(TefConfig.DIR_REQ):
            try: os.remove(os.path.join(TefConfig.DIR_REQ, f))
            except: pass
        for f in os.listdir(TefConfig.DIR_RESP):
            try: os.remove(os.path.join(TefConfig.DIR_RESP, f))
            except: pass

    @staticmethod
    def write_request(data_dict):
        """Escreve IntPos.tmp e renomeia para IntPos.001 [cite: 202]"""
        tmp_path = os.path.join(TefConfig.DIR_REQ, "IntPos.tmp")
        final_path = os.path.join(TefConfig.DIR_REQ, "IntPos.001")
        
        try:
            with open(tmp_path, 'w', encoding='mbcs') as f:
                # Header primeiro
                if "000-000" in data_dict:
                    f.write(f"000-000 = {data_dict['000-000']}\n")
                
                for k, v in data_dict.items():
                    if k not in ["000-000", "999-999"] and v is not None:
                        f.write(f"{k} = {v}\n")
                
                # Trailer [cite: 441]
                f.write("999-999 = 0\n")
            
            if os.path.exists(final_path):
                os.remove(final_path)
            os.rename(tmp_path, final_path)
            return True
        except Exception as e:
            print(f"Erro escrita: {e}")
            return False

    @staticmethod
    def wait_response(timeout=60):
        """
        Aguarda IntPos.Sts (confirmação de recebimento) e depois IntPos.001 (resposta)
        Fluxo descrito na página 5[cite: 47, 48].
        """
        # 1. Aguarda STS (Max 7s) [cite: 47]
        start = time.time()
        sts_ok = False
        sts_path = os.path.join(TefConfig.DIR_RESP, "IntPos.Sts")
        
        while time.time() - start < 7:
            if os.path.exists(sts_path):
                try: os.remove(sts_path)
                except: pass
                sts_ok = True
                break
            time.sleep(0.1)
            
        if not sts_ok:
            return None, "Erro: CTFClient não respondeu (Sem STS)."

        # 2. Aguarda Resposta
        resp_path = os.path.join(TefConfig.DIR_RESP, "IntPos.001")
        start = time.time()
        while time.time() - start < timeout:
            if os.path.exists(resp_path):
                # Pequeno delay para garantir escrita completa
                time.sleep(0.2)
                data = {}
                try:
                    with open(resp_path, 'r', encoding='mbcs') as f:
                        for line in f:
                            if '=' in line:
                                k, v = line.strip().split('=', 1)
                                data[k.strip()] = v.strip()
                    os.remove(resp_path)
                    return data, "Sucesso"
                except Exception as e:
                    return None, f"Erro leitura: {e}"
            time.sleep(0.5)
            
        return None, "Timeout aguardando resposta do TEF."

# =============================================================================
# INTERFACE GRÁFICA E LÓGICA DE NEGÓCIO
# =============================================================================
class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDV TEF Auttar - Fluxo Controlado")
        self.root.geometry("1000x600")
        self.root.configure(bg="#f0f2f5")
        
        TefFileHandler.setup_directories()
        
        # Estado da Venda
        self.valor_total_venda = 0.0
        self.valor_restante = 0.0
        self.transacoes_pendentes = [] # Lista de transações aprovadas mas não confirmadas
        self.lock = False # Mutex simples para UI
        self.doc_fiscal = "1001" # Exemplo

        self.setup_ui()

    def setup_ui(self):
        # --- Estilos ---
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", rowheight=25, font=('Arial', 10))
        style.configure("Header.TLabel", font=('Segoe UI', 12, 'bold'), background="#f0f2f5")
        
        # --- Layout Principal ---
        left_panel = tk.Frame(self.root, bg="white", padx=15, pady=15, relief=tk.RAISED, bd=1)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        
        right_panel = tk.Frame(self.root, bg="#f0f2f5", padx=15, pady=15)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # === PAINEL ESQUERDO (Ações de Venda) ===
        tk.Label(left_panel, text="PDV - CAIXA LIVRE", font=("Segoe UI", 16, "bold"), bg="white", fg="#2c3e50").pack(pady=(0, 20))
        
        tk.Label(left_panel, text="Valor Total da Venda (R$):", bg="white", font=("Segoe UI", 10)).pack(anchor="w")
        self.entry_valor = ttk.Entry(left_panel, font=("Segoe UI", 14))
        self.entry_valor.insert(0, "100.00")
        self.entry_valor.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(left_panel, text="Doc. Fiscal:", bg="white").pack(anchor="w")
        self.entry_doc = ttk.Entry(left_panel)
        self.entry_doc.insert(0, self.doc_fiscal)
        self.entry_doc.pack(fill=tk.X, pady=(0, 20))

        tk.Label(left_panel, text="Operações:", bg="white", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        
        self.btn_credito = tk.Button(left_panel, text="CRÉDITO", bg="#3498db", fg="white", font=("Segoe UI", 10, "bold"),
                                     command=lambda: self.iniciar_transacao("CREDITO"))
        self.btn_credito.pack(fill=tk.X, pady=5, ipady=5)

        self.btn_debito = tk.Button(left_panel, text="DÉBITO", bg="#3498db", fg="white", font=("Segoe UI", 10, "bold"),
                                    command=lambda: self.iniciar_transacao("DEBITO"))
        self.btn_debito.pack(fill=tk.X, pady=5, ipady=5)

        tk.Button(left_panel, text="ADMINISTRATIVO (ADM)", bg="#95a5a6", fg="white",
                  command=lambda: self.iniciar_transacao("ADM")).pack(fill=tk.X, pady=20)
        
        self.lbl_status = tk.Label(left_panel, text="Aguardando...", bg="white", fg="gray")
        self.lbl_status.pack(side=tk.BOTTOM)

        # === PAINEL DIREITO (Lista de Pendências e Decisão) ===
        
        tk.Label(right_panel, text="Transações Aprovadas (Aguardando Decisão)", font=("Segoe UI", 12, "bold"), bg="#f0f2f5").pack(anchor="w")
        
        # Treeview
        columns = ("nsu", "rede", "valor", "modalidade")
        self.tree = ttk.Treeview(right_panel, columns=columns, show="headings", height=10)
        self.tree.heading("nsu", text="NSU")
        self.tree.heading("rede", text="Rede")
        self.tree.heading("valor", text="Valor")
        self.tree.heading("modalidade", text="Modo")
        
        self.tree.column("nsu", width=80)
        self.tree.column("rede", width=100)
        self.tree.column("valor", width=80)
        self.tree.column("modalidade", width=100)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)

        # Painel de Saldos
        frame_totais = tk.Frame(right_panel, bg="#dfe6e9", padx=10, pady=10)
        frame_totais.pack(fill=tk.X)
        
        self.lbl_restante = tk.Label(frame_totais, text="Restante a Pagar: R$ 0,00", font=("Segoe UI", 12, "bold"), bg="#dfe6e9", fg="#c0392b")
        self.lbl_restante.pack(side=tk.RIGHT)

        # Botões de Decisão (O requisito principal)
        frame_actions = tk.Frame(right_panel, bg="#f0f2f5", pady=20)
        frame_actions.pack(fill=tk.X)

        self.btn_confirmar = tk.Button(frame_actions, text="CONFIRMAR TRANSAÇÃO(ÕES)", bg="#27ae60", fg="white", font=("Segoe UI", 11, "bold"),
                                       state=tk.DISABLED, command=self.acao_confirmar_tudo)
        self.btn_confirmar.pack(side=tk.RIGHT, padx=5)

        self.btn_desfazer = tk.Button(frame_actions, text="DESFAZER / ESTORNAR", bg="#e74c3c", fg="white", font=("Segoe UI", 11, "bold"),
                                      state=tk.DISABLED, command=self.acao_desfazer_tudo)
        self.btn_desfazer.pack(side=tk.RIGHT, padx=5)
        
        self.btn_ignorar = tk.Button(frame_actions, text="Limpar Tela (Ignorar)", bg="#7f8c8d", fg="white",
                                     state=tk.DISABLED, command=self.acao_ignorar)
        self.btn_ignorar.pack(side=tk.LEFT, padx=5)

    # =========================================================================
    # LÓGICA DE TRANSAÇÃO
    # =========================================================================
    
    def atualizar_saldos(self):
        try:
            total = float(self.entry_valor.get())
        except:
            total = 0.0
            
        pago = sum(t['valor_float'] for t in self.transacoes_pendentes)
        restante = total - pago
        
        self.valor_restante = restante
        self.lbl_restante.config(text=f"Restante a Pagar: R$ {restante:.2f}")
        
        # Controle de Estado dos Botões
        if len(self.transacoes_pendentes) > 0:
            self.btn_confirmar.config(state=tk.NORMAL)
            self.btn_desfazer.config(state=tk.NORMAL)
            self.btn_ignorar.config(state=tk.NORMAL)
            
            # Trava inputs se já pagou tudo ou está em processo parcial
            # (Opcional, mas boa prática para evitar mudança de valor total no meio)
            self.entry_valor.config(state=tk.DISABLED)
        else:
            self.btn_confirmar.config(state=tk.DISABLED)
            self.btn_desfazer.config(state=tk.DISABLED)
            self.btn_ignorar.config(state=tk.DISABLED)
            self.entry_valor.config(state=tk.NORMAL)

    def iniciar_transacao(self, tipo):
        if self.lock: return
        
        # Se for ADM, vai direto
        if tipo == "ADM":
            threading.Thread(target=self.thread_tef, args=(tipo, 0)).start()
            return

        # Lógica de valor
        try:
            valor_total_ini = float(self.entry_valor.get())
            if self.valor_restante <= 0 and len(self.transacoes_pendentes) == 0:
                # Primeira transação
                self.valor_restante = valor_total_ini
            elif self.valor_restante <= 0:
                messagebox.showinfo("Aviso", "Valor total já foi atingido. Confirme ou Desfaça.")
                return
        except ValueError:
            messagebox.showerror("Erro", "Valor inválido.")
            return

        # Pergunta valor parcial se for múltiplos cartões
        valor_processar = self.valor_restante
        
        # Se quiser permitir dividir explicitamente agora:
        if len(self.transacoes_pendentes) > 0 or messagebox.askyesno("Valor", f"Valor Restante: {self.valor_restante:.2f}\nDeseja passar o valor total restante?"):
            pass
        else:
            v_str = simpledialog.askstring("Parcial", "Digite o valor para este cartão:")
            if v_str:
                try: valor_processar = float(v_str.replace(',', '.'))
                except: return
            else:
                return

        if valor_processar > self.valor_restante + 0.01: # Tolerância float
            messagebox.showerror("Erro", "Valor maior que o restante.")
            return

        # Converter para centavos (string sem ponto) [cite: 250]
        valor_cents = str(int(round(valor_processar * 100)))
        
        threading.Thread(target=self.thread_tef, args=(tipo, valor_cents)).start()

    def thread_tef(self, tipo, valor_cents):
        self.lock = True
        self.lbl_status.config(text="Processando TEF...", fg="blue")
        
        try:
            id_req = SequenceManager.get_next_id()
            doc = self.entry_doc.get()
            
            # Monta Requisição
            req = {
                "001-000": id_req,
                "002-000": doc,
            }
            
            if tipo == "ADM":
                req["000-000"] = "ADM" # [cite: 250]
            else:
                req["000-000"] = "CRT" # [cite: 250]
                req["003-000"] = valor_cents
                # 10=Crédito, 20=Débito [cite: 260]
                req["011-000"] = "10" if tipo == "CREDITO" else "20" 
                
                # Flag Múltiplos Cartões 
                # Se já tem pendente ou se o valor é parcial, indicamos Múltiplos
                if len(self.transacoes_pendentes) > 0 or float(valor_cents)/100 < self.valor_restante:
                     req["099-000"] = "1"

            # Envia
            if not TefFileHandler.write_request(req):
                raise Exception("Falha ao criar arquivo de requisição.")
            
            # Aguarda
            resp, status_msg = TefFileHandler.wait_response()
            
            if not resp:
                raise Exception(status_msg)
            
            # Processa Resposta
            cod_resp = resp.get("009-000") # 0 = Aprovada [cite: 250]
            msg_op = resp.get("030-000", "") # Mensagem Operador 
            
            if cod_resp == "0":
                if tipo == "ADM":
                    messagebox.showinfo("ADM", f"Operação realizada:\n{msg_op}")
                else:
                    # SUCESSO NA TRANSAÇÃO DE PAGAMENTO
                    # Armazena dados críticos para CNF/NCN
                    dados_aprovados = {
                        "nsu": resp.get("012-000"), # [cite: 265]
                        "rede": resp.get("010-000"), # [cite: 260]
                        "finalizacao": resp.get("027-000"), # CRÍTICO 
                        "id_original": id_req,
                        "valor_float": float(valor_cents)/100,
                        "modo": tipo,
                        "doc": doc
                    }
                    
                    # Atualiza UI na thread principal
                    self.root.after(0, lambda: self.adicionar_pendencia(dados_aprovados))
                    
            else:
                messagebox.showwarning("Negada", f"Erro TEF: {msg_op}")

        except Exception as e:
            messagebox.showerror("Erro", str(e))
        finally:
            self.lock = False
            self.lbl_status.config(text="Caixa Livre", fg="gray")

    def adicionar_pendencia(self, dados):
        self.transacoes_pendentes.append(dados)
        self.tree.insert("", "end", values=(dados['nsu'], dados['rede'], f"{dados['valor_float']:.2f}", dados['modo']))
        self.atualizar_saldos()

    # =========================================================================
    # AÇÕES DE DECISÃO (CONFIRMAR, DESFAZER, IGNORAR)
    # =========================================================================

    def enviar_confirmacao_final(self, confirmar=True):
        """
        Envia CNF ou NCN para TODAS as transações pendentes.
        Obrigatório enviar o campo 099-000=1 se houver múltiplos cartões envolvidos[cite: 140, 154].
        """
        if not self.transacoes_pendentes: return

        comando = "CNF" if confirmar else "NCN" # [cite: 178]
        acao_txt = "Confirmando" if confirmar else "Desfazendo"
        
        self.lbl_status.config(text=f"{acao_txt} lote...", fg="orange")
        
        # Cópia da lista para iterar
        pendentes = list(self.transacoes_pendentes)
        
        def processar():
            erros = []
            for trx in pendentes:
                id_cnf = SequenceManager.get_next_id()
                req = {
                    "000-000": comando,
                    "001-000": id_cnf,
                    "002-000": trx['doc'],
                    "010-000": trx['rede'],     # Obrigatório [cite: 117]
                    "012-000": trx['nsu'],      # Obrigatório [cite: 117]
                    "027-000": trx.get('finalizacao', '') # Obrigatório devolver 
                }
                
                # Se há mais de uma transação ou foi marcado como múltiplo, a confirmação deve ter a flag
                # Nota: Auttar recomenda sempre enviar 099=1 se o fluxo original foi de múltiplos [cite: 287, 456]
                req["099-000"] = "1"

                TefFileHandler.write_request(req)
                # O comando CNF/NCN geralmente não gera resposta visual (IntPos.001) por padrão,
                # a menos que configurado HABILITA_RESP_TODAS_OPE=1[cite: 235].
                # Assumimos fire-and-forget com pequeno delay.
                time.sleep(1.5)
            
            # Limpa UI
            self.root.after(0, self.limpar_tudo)
            msg = "Venda Finalizada com Sucesso!" if confirmar else "Venda Cancelada/Estornada."
            self.root.after(0, lambda: messagebox.showinfo("Fim", msg))

        threading.Thread(target=processar).start()

    def acao_confirmar_tudo(self):
        if not self.transacoes_pendentes: return
        if self.valor_restante > 0.01:
            if not messagebox.askyesno("Aviso", f"Ainda falta R$ {self.valor_restante:.2f}. Deseja finalizar (CNF) o que já foi aprovado?"):
                return
        
        if messagebox.askyesno("Confirmar", "Deseja CONFIRMAR EFETIVAMENTE todas as transações listadas?"):
            self.enviar_confirmacao_final(confirmar=True)

    def acao_desfazer_tudo(self):
        if not self.transacoes_pendentes: return
        if messagebox.askyesno("Desfazer", "Deseja ESTORNAR (NCN) todas as transações listadas?"):
            self.enviar_confirmacao_final(confirmar=False)

    def acao_ignorar(self):
        """Limpa a tela sem enviar nada ao TEF (Perigoso, mas solicitado)"""
        if messagebox.askyesno("Cuidado", "Isso removerá as transações da tela SEM enviar Confirmação ou Desfazimento.\n\nAs transações podem ficar pendentes no servidor TEF.\n\nContinuar?"):
            self.limpar_tudo()

    def limpar_tudo(self):
        self.transacoes_pendentes = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.atualizar_saldos()
        # Novo Doc Fiscal simulado
        try:
            novo_doc = int(self.entry_doc.get()) + 1
            self.entry_doc.delete(0, tk.END)
            self.entry_doc.insert(0, str(novo_doc))
        except: pass
        self.lbl_status.config(text="Pronto", fg="gray")

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()