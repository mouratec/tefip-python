import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================
class TefConfig:
    DIR_BASE = r"C:\Auttar_TefIP"
    DIR_REQ = os.path.join(DIR_BASE, "REQ")
    DIR_RESP = os.path.join(DIR_BASE, "RESP")
    FILE_SEQ = "tef_sequence.dat"

class SequenceManager:
    """
    Gerencia o ID sequencial com Thread Lock para evitar números repetidos
    no log em operações rápidas.
    """
    _lock = threading.Lock()

    @staticmethod
    def reset_sequence():
        """Reseta para 0 apenas ao abrir o sistema"""
        with SequenceManager._lock:
            try:
                with open(TefConfig.FILE_SEQ, "w") as f:
                    f.write("0")
            except: pass

    @staticmethod
    def get_next_id():
        """Lê, incrementa e salva de forma atômica (Thread-Safe)"""
        with SequenceManager._lock:
            current_id = 0
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
            
            return str(next_id).zfill(10)

class TefFileHandler:
    @staticmethod
    def setup_directories():
        os.makedirs(TefConfig.DIR_REQ, exist_ok=True)
        os.makedirs(TefConfig.DIR_RESP, exist_ok=True)
        for p in [TefConfig.DIR_REQ, TefConfig.DIR_RESP]:
            for f in os.listdir(p):
                try: os.remove(os.path.join(p, f))
                except: pass

    @staticmethod
    def write_request(data_dict):
        tmp_path = os.path.join(TefConfig.DIR_REQ, "IntPos.tmp")
        final_path = os.path.join(TefConfig.DIR_REQ, "IntPos.001")
        try:
            with open(tmp_path, 'w', encoding='mbcs') as f:
                if "000-000" in data_dict:
                    f.write(f"000-000 = {data_dict['000-000']}\n")
                for k, v in data_dict.items():
                    if k not in ["000-000", "999-999"] and v is not None:
                        f.write(f"{k} = {v}\n")
                f.write("999-999 = 0\n")
            
            if os.path.exists(final_path): os.remove(final_path)
            os.rename(tmp_path, final_path)
            return True
        except Exception as e:
            print(f"Erro escrita: {e}")
            return False

    @staticmethod
    def wait_response(timeout=60):
        start = time.time()
        sts_path = os.path.join(TefConfig.DIR_RESP, "IntPos.Sts")
        # Aguarda STS
        while time.time() - start < 7:
            if os.path.exists(sts_path):
                try: os.remove(sts_path)
                except: pass
                break
            time.sleep(0.1)
        else:
            return None, "Erro: CTFClient não respondeu (Sem STS)."

        # Aguarda Resposta
        resp_path = os.path.join(TefConfig.DIR_RESP, "IntPos.001")
        start = time.time()
        while time.time() - start < timeout:
            if os.path.exists(resp_path):
                time.sleep(0.3)
                data = {}
                try:
                    with open(resp_path, 'r', encoding='mbcs') as f:
                        for line in f:
                            if '=' in line:
                                k, v = line.strip().split('=', 1)
                                data[k.strip()] = v.strip()
                    os.remove(resp_path)
                    return data, "Sucesso"
                except: pass
            time.sleep(0.5)
        return None, "Timeout aguardando resposta TEF."

# =============================================================================
# JANELAS DE INPUT
# =============================================================================
class InputDialog(tk.Toplevel):
    def __init__(self, parent, title, fields):
        super().__init__(parent)
        self.title(title)
        self.geometry("350x350")
        self.result = None
        self.entries = {}
        
        container = tk.Frame(self, padx=20, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        for label_text, key in fields:
            tk.Label(container, text=label_text, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(5, 0))
            entry = ttk.Entry(container)
            entry.pack(fill=tk.X)
            self.entries[key] = entry

        tk.Button(container, text="Confirmar", bg="#27ae60", fg="white", command=self.on_ok).pack(fill=tk.X, pady=20)

    def on_ok(self):
        data = {}
        for key, entry in self.entries.items():
            val = entry.get().strip()
            # Permite campos opcionais em cenários específicos
            if not val and key not in ['rede']: 
                messagebox.showwarning("Aviso", "Preencha todos os campos obrigatórios")
                return
            data[key] = val
        self.result = data
        self.destroy()

# =============================================================================
# PDV PRINCIPAL
# =============================================================================
class ModernPDV:
    def __init__(self, root):
        self.root = root
        self.root.title("PDV TEF Auttar - Parcelado & Sequencial")
        self.root.geometry("1150x780") # Aumentei um pouco a altura
        self.root.configure(bg="#f4f6f9")
        
        TefFileHandler.setup_directories()
        SequenceManager.reset_sequence()
        
        # Estrutura: {id_req, nsu, rede, finalizacao, valor, tipo, data_operacao, hora_operacao, status}
        self.historico_transacoes = [] 
        
        self.valor_restante = 0.0
        self.lock = False 
        self.doc_fiscal = "1001"

        self.setup_layout()

    def setup_layout(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Card.TFrame", background="white", relief="raised")
        style.configure("Treeview", font=('Segoe UI', 10), rowheight=28)
        
        container = tk.Frame(self.root, bg="#f4f6f9")
        container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # === ESQUERDA (OPERAÇÕES) ===
        left_panel = ttk.Frame(container, style="Card.TFrame", padding=15)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        tk.Label(left_panel, text="Operação de Venda", font=("Segoe UI", 14, "bold"), bg="white").pack(anchor="w", pady=(0, 15))

        tk.Label(left_panel, text="VALOR TOTAL (R$)", bg="white", fg="#7f8c8d").pack(anchor="w")
        self.entry_total = ttk.Entry(left_panel, font=("Segoe UI", 16))
        self.entry_total.insert(0, "100.00")
        self.entry_total.pack(fill=tk.X, pady=(0, 10))

        tk.Label(left_panel, text="PAGAMENTO ATUAL (R$)", bg="white", fg="#27ae60").pack(anchor="w")
        self.entry_pagamento = ttk.Entry(left_panel, font=("Segoe UI", 16))
        self.entry_pagamento.insert(0, "100.00")
        self.entry_pagamento.pack(fill=tk.X, pady=(0, 20))

        btn_cfg = {'font': ("Segoe UI", 10, "bold"), 'bg': "#3498db", 'fg': "white", 'relief': "flat", 'bd': 0, 'cursor': "hand2"}
        
        # Botões de Crédito
        tk.Button(left_panel, text="CRÉDITO À VISTA", command=lambda: self.iniciar_tef("CREDITO"), **btn_cfg).pack(fill=tk.X, pady=4, ipady=5)
        
        # NOVO BOTÃO: CRÉDITO PARCELADO
        btn_parc = btn_cfg.copy()
        btn_parc['bg'] = "#2980b9" # Azul um pouco mais escuro
        tk.Button(left_panel, text="CRÉDITO PARCELADO (S/ JUROS)", command=lambda: self.iniciar_tef("CREDITO_PARCELADO"), **btn_parc).pack(fill=tk.X, pady=4, ipady=5)

        tk.Button(left_panel, text="DÉBITO", command=lambda: self.iniciar_tef("DEBITO"), **btn_cfg).pack(fill=tk.X, pady=4, ipady=5)
        
        btn_pix_style = btn_cfg.copy()
        btn_pix_style['bg'] = "#27ae60"
        tk.Button(left_panel, text="PIX (PAGAMENTO)", command=lambda: self.iniciar_tef("PIX_PAGAMENTO"), **btn_pix_style).pack(fill=tk.X, pady=4, ipady=5)

        tk.Frame(left_panel, height=2, bg="#ecf0f1").pack(fill=tk.X, pady=20)
        
        tk.Label(left_panel, text="Administrativo / Cancelamento", font=("Segoe UI", 12, "bold"), bg="white", fg="#e67e22").pack(anchor="w", pady=(0, 10))
        
        btn_adm = btn_cfg.copy()
        btn_adm['bg'] = "#95a5a6"
        tk.Button(left_panel, text="MENU ADMINISTRATIVO", command=lambda: self.iniciar_tef("ADM_GENERICO"), **btn_adm).pack(fill=tk.X, pady=4, ipady=5)
        
        btn_danger = btn_cfg.copy()
        btn_danger['bg'] = "#e74c3c"
        tk.Button(left_panel, text="CANCELAR ITEM SELECIONADO / MANUAL", command=self.cancelar_inteligente, **btn_danger).pack(fill=tk.X, pady=4, ipady=5)

        self.lbl_status = tk.Label(left_panel, text="Caixa Livre", bg="white", fg="gray", font=("Segoe UI", 9))
        self.lbl_status.pack(side=tk.BOTTOM, pady=10)

        # === DIREITA (HISTÓRICO) ===
        right_panel = ttk.Frame(container, style="Card.TFrame", padding=15)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(right_panel, text="Histórico de Transações (Todas)", font=("Segoe UI", 12, "bold"), bg="white").pack(anchor="w")

        cols = ("rede", "nsu", "valor", "tipo", "status", "data")
        self.tree = ttk.Treeview(right_panel, columns=cols, show="headings", height=15)
        self.tree.heading("rede", text="Rede")
        self.tree.heading("nsu", text="NSU")
        self.tree.heading("valor", text="Valor")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("status", text="Status")
        self.tree.heading("data", text="Data")
        
        self.tree.column("rede", width=80)
        self.tree.column("nsu", width=80)
        self.tree.column("valor", width=80)
        self.tree.column("tipo", width=100) # Aumentei um pouco para caber "CRED PARC"
        self.tree.column("status", width=100)
        self.tree.column("data", width=80)
        
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copiar NSU", command=self.copiar_nsu)
        self.context_menu.add_command(label="Copiar Valor", command=self.copiar_valor)
        self.context_menu.add_command(label="Cancelar Este Item", command=self.cancelar_inteligente)
        self.tree.bind("<Button-3>", self.mostrar_menu_contexto)

        footer = tk.Frame(right_panel, bg="white")
        footer.pack(fill=tk.X)
        
        self.lbl_restante = tk.Label(footer, text="RESTANTE: R$ 0,00", font=("Segoe UI", 14, "bold"), bg="white", fg="#c0392b")
        self.lbl_restante.pack(side=tk.TOP, pady=10)

        tk.Button(footer, text="CONFIRMAR PENDENTES (F5)", bg="#2ecc71", fg="white", font=("Segoe UI", 10, "bold"), command=lambda: self.finalizar_pendentes(True)).pack(side=tk.RIGHT, padx=5)
        tk.Button(footer, text="ESTORNAR PENDENTES", bg="#e74c3c", fg="white", font=("Segoe UI", 10, "bold"), command=lambda: self.finalizar_pendentes(False)).pack(side=tk.RIGHT, padx=5)
        tk.Button(footer, text="Nova Venda (Limpar)", command=self.nova_venda).pack(side=tk.LEFT)

        self.atualizar_interface()

    # =========================================================================
    # LÓGICA DE DADOS & UTILS
    # =========================================================================
    def get_valor(self, entry):
        try: return float(entry.get().replace(",", "."))
        except: return 0.0

    def atualizar_interface(self):
        total = self.get_valor(self.entry_total)
        pagos = [t['valor_float'] for t in self.historico_transacoes if t['status'] in ["PENDENTE", "CONFIRMADO"]]
        pago_total = sum(pagos)
        restante = round(max(0, total - pago_total), 2)
        
        self.valor_restante = restante
        self.lbl_restante.config(text=f"RESTANTE: R$ {restante:.2f}", fg="#c0392b" if restante > 0 else "#27ae60")
        
        if restante > 0:
            self.entry_pagamento.delete(0, tk.END)
            self.entry_pagamento.insert(0, f"{restante:.2f}")
        else:
            self.entry_pagamento.delete(0, tk.END)
            self.entry_pagamento.insert(0, "0.00")

    def mostrar_menu_contexto(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def copiar_nsu(self):
        sel = self.tree.selection()
        if not sel: return
        item = self.tree.item(sel[0])
        self.root.clipboard_clear()
        self.root.clipboard_append(item['values'][1])

    def copiar_valor(self):
        sel = self.tree.selection()
        if not sel: return
        item = self.tree.item(sel[0])
        self.root.clipboard_clear()
        self.root.clipboard_append(item['values'][2])

    def atualizar_treeview(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for t in self.historico_transacoes:
            tipo_display = t['tipo']
            if tipo_display == "CREDITO_PARCELADO":
                tipo_display = f"CRED PARC ({t.get('parcelas', '?')}x)"
            
            self.tree.insert("", "end", values=(
                t['rede'], t['nsu'], f"{t['valor_float']:.2f}", tipo_display, t['status'], t.get('data_operacao', '-')
            ))

    # =========================================================================
    # CANCELAMENTO INTELIGENTE
    # =========================================================================
    def cancelar_inteligente(self):
        sel = self.tree.selection()
        
        if sel:
            idx_tree = self.tree.index(sel[0])
            if idx_tree < len(self.historico_transacoes):
                transacao = self.historico_transacoes[idx_tree]
                
                if messagebox.askyesno("Cancelar", f"Cancelar transação?\n\nNSU: {transacao['nsu']}\nValor: {transacao['valor_float']}"):
                    val_cents = str(int(round(transacao['valor_float'] * 100)))
                    
                    hora_padrao = datetime.now().strftime("%H%M%S")
                    
                    dados_extras = {
                        'nsu': transacao['nsu'],
                        'data': transacao.get('data_operacao', datetime.now().strftime("%d%m%Y")),
                        'hora': transacao.get('hora_operacao', hora_padrao),
                        'rede': transacao['rede']
                    }

                    if "PIX" in transacao['tipo']:
                        threading.Thread(target=self.thread_tef, args=("DEVOLUCAO_PIX", val_cents, dados_extras)).start()
                    else:
                        threading.Thread(target=self.thread_tef, args=("CNC", val_cents, dados_extras)).start()
            return
        
        self.popup_cancelamento_cnc_manual()

    def popup_cancelamento_cnc_manual(self):
        fields = [
            ("NSU Original:", "nsu"),
            ("Data Original (DDMMAAAA):", "data"),
            ("Hora Original (HHMMSS):", "hora"),
            ("Valor a Cancelar (Ex: 10.00):", "valor")
        ]
        dialog = InputDialog(self.root, "Cancelamento Manual (Cartão)", fields)
        self.root.wait_window(dialog)
        
        if dialog.result:
            try:
                val_cents = str(int(round(float(dialog.result['valor'].replace(",", ".")) * 100)))
                dialog.result['rede'] = "" 
                threading.Thread(target=self.thread_tef, args=("CNC", val_cents, dialog.result)).start()
            except ValueError:
                messagebox.showerror("Erro", "Valor inválido")

    # =========================================================================
    # TEF CORE
    # =========================================================================
    def iniciar_tef(self, tipo):
        if self.lock: return
        
        if tipo == "ADM_GENERICO":
             threading.Thread(target=self.thread_tef, args=("ADM", 0, None)).start()
             return

        val_pagar = self.get_valor(self.entry_pagamento)
        if val_pagar <= 0: return

        if "PIX" in tipo or "CREDITO" in tipo or "DEBITO" in tipo:
            if val_pagar > self.valor_restante + 0.01 and any(t['status'] == "PENDENTE" for t in self.historico_transacoes):
                messagebox.showerror("Erro", "Valor excede o restante.")
                return

        val_cents = str(int(round(val_pagar * 100)))
        dados_extras = None

        # TRATAMENTO PARA PARCELADO
        if tipo == "CREDITO_PARCELADO":
            parcelas = simpledialog.askinteger("Parcelamento", "Quantidade de Parcelas (2 a 99):", minvalue=2, maxvalue=99)
            if not parcelas: return
            dados_extras = {'parcelas': parcelas}

        threading.Thread(target=self.thread_tef, args=(tipo, val_cents, dados_extras)).start()

    def thread_tef(self, tipo, valor_cents, dados_extras):
        self.lock = True
        self.lbl_status.config(text=f"Processando {tipo}...", fg="blue")
        
        try:
            # Garante ID sequencial único para o log
            id_req = SequenceManager.get_next_id()
            req = {"001-000": id_req}

            if tipo == "ADM":
                req["000-000"] = "ADM"
            
            elif tipo == "DEVOLUCAO_PIX":
                req["000-000"] = "ADM"
                req["003-000"] = valor_cents
                req["012-000"] = dados_extras['nsu']
                req["719-000"] = dados_extras['data']
                
            elif tipo == "CNC":
                req["000-000"] = "CNC"
                req["002-000"] = self.doc_fiscal
                req["003-000"] = valor_cents
                req["012-000"] = dados_extras['nsu']
                req["022-000"] = dados_extras['data']
                if dados_extras.get('hora'):
                     req["023-000"] = dados_extras['hora']
                if dados_extras.get('rede'):
                     req["010-000"] = dados_extras['rede']

            elif tipo == "PIX_PAGAMENTO":
                req["000-000"] = "QRC"
                req["002-000"] = self.doc_fiscal
                req["003-000"] = valor_cents
                
            else: # CREDITO / DEBITO / PARCELADO
                req["000-000"] = "CRT"
                req["002-000"] = self.doc_fiscal
                req["003-000"] = valor_cents
                
                if tipo == "CREDITO":
                    req["011-000"] = "10"
                elif tipo == "DEBITO":
                    req["011-000"] = "20"
                elif tipo == "CREDITO_PARCELADO":
                    # 11 = Parcelado Loja (Sem Juros)
                    req["011-000"] = "11" 
                    # 018-000 = Quantidade de parcelas (formato 02, 03...)
                    if dados_extras and 'parcelas' in dados_extras:
                        req["018-000"] = str(dados_extras['parcelas']).zfill(2)

            # Flag Múltiplos
            pendentes = [t for t in self.historico_transacoes if t['status'] == "PENDENTE"]
            if tipo in ["CRT", "PIX_PAGAMENTO", "CREDITO", "DEBITO", "CREDITO_PARCELADO"] and (float(valor_cents)/100 < self.valor_restante or pendentes):
                req["099-000"] = "1"

            if not TefFileHandler.write_request(req): raise Exception("Erro ao gravar arquivo.")
            resp, status = TefFileHandler.wait_response()
            if not resp: raise Exception(status)

            cod = resp.get("009-000")
            msg = resp.get("030-000", "")

            if cod == "0":
                if tipo == "DEVOLUCAO_PIX":
                    messagebox.showinfo("Sucesso", f"PIX Devolvido!\n{msg}")
                    if dados_extras and dados_extras.get('nsu'):
                        for t in self.historico_transacoes:
                            if t['nsu'] == dados_extras['nsu']:
                                t['status'] = "DEVOLVIDO (PIX)"
                        self.root.after(0, self.atualizar_treeview)
                
                elif tipo == "CNC":
                    if messagebox.askyesno("Confirmar Estorno", f"Estorno Aprovado.\n{msg}\nConfirmar operação?"):
                        self.enviar_confirmacao_imediata(id_req, resp)
                        if dados_extras and dados_extras.get('nsu'):
                            for t in self.historico_transacoes:
                                if t['nsu'] == dados_extras['nsu']:
                                    t['status'] = "CANCELADO"
                        self.root.after(0, self.atualizar_treeview)

                elif tipo == "ADM":
                    messagebox.showinfo("ADM", f"{msg}")

                else:
                    data_op = resp.get("022-000") or resp.get("015-000")
                    hora_op = resp.get("023-000") or resp.get("016-000")

                    if data_op and len(data_op) > 8: data_op = data_op[:8] 
                    if hora_op and len(hora_op) > 6: hora_op = hora_op[:6]

                    dados = {
                        "id_req": id_req,
                        "nsu": resp.get("012-000"),
                        "rede": resp.get("010-000"),
                        "finalizacao": resp.get("027-000"),
                        "valor_float": float(valor_cents)/100,
                        "tipo": tipo,
                        "parcelas": dados_extras['parcelas'] if dados_extras and 'parcelas' in dados_extras else "",
                        "data_operacao": data_op if data_op else datetime.now().strftime("%d%m%Y"),
                        "hora_operacao": hora_op if hora_op else datetime.now().strftime("%H%M%S"),
                        "status": "PENDENTE"
                    }
                    self.historico_transacoes.append(dados)
                    self.root.after(0, self.atualizar_treeview)
                    self.root.after(0, self.atualizar_interface)
            else:
                messagebox.showwarning("Recusado", f"Erro TEF: {msg}")

        except Exception as e:
            messagebox.showerror("Erro", str(e))
        finally:
            self.lock = False
            self.root.after(0, lambda: self.lbl_status.config(text="Livre", fg="gray"))

    def enviar_confirmacao_imediata(self, id_original, resp_dados):
        id_cnf = SequenceManager.get_next_id()
        req = {
            "000-000": "CNF",
            "001-000": id_cnf,
            "002-000": self.doc_fiscal,
            "010-000": resp_dados.get("010-000"),
            "012-000": resp_dados.get("012-000"),
            "027-000": resp_dados.get("027-000")
        }
        TefFileHandler.write_request(req)

    def finalizar_pendentes(self, confirmar):
        pendentes = [t for t in self.historico_transacoes if t['status'] == "PENDENTE"]
        if not pendentes: return
        
        acao = "CONFIRMAR" if confirmar else "ESTORNAR"
        if not messagebox.askyesno("Finalizar", f"Deseja {acao} {len(pendentes)} transações?"): return

        def process_batch():
            self.lock = True
            cmd = "CNF" if confirmar else "NCN"
            novo_status = "CONFIRMADO" if confirmar else "ESTORNADO"
            
            for item in pendentes:
                # Cada CNF ganha um ID SEQUENCIAL ÚNICO
                id_cnf = SequenceManager.get_next_id()
                req = {
                    "000-000": cmd,
                    "001-000": id_cnf,
                    "002-000": self.doc_fiscal,
                    "010-000": item['rede'],
                    "012-000": item['nsu'],
                    "027-000": item['finalizacao'],
                    "099-000": "1"
                }
                TefFileHandler.write_request(req)
                item['status'] = novo_status
                time.sleep(1.0) 

            self.root.after(0, self.atualizar_treeview)
            self.root.after(0, self.atualizar_interface)
            
            msg = "Finalizado com Sucesso!" if confirmar else "Estornos Solicitados."
            self.root.after(0, lambda: messagebox.showinfo("Fim", msg))
            self.lock = False

        threading.Thread(target=process_batch).start()

    def nova_venda(self):
        self.historico_transacoes = []
        self.doc_fiscal = str(int(self.doc_fiscal) + 1)
        self.entry_total.config(state=tk.NORMAL)
        self.entry_total.delete(0, tk.END)
        self.entry_total.insert(0, "100.00")
        self.atualizar_treeview()
        self.atualizar_interface()

if __name__ == "__main__":
    root = tk.Tk()
    app = ModernPDV(root)
    root.mainloop()