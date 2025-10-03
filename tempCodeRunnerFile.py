atus (IntPos.Sts)
                sts_file = os.path.join(self.resp_dir, "IntPos.Sts")
                if os.path.exists(sts_file):
                    self.process_status_file(sts_file)
                
                # Verificar arquivo de resposta (IntPos.001)
                resp_file = os.path.join(self.resp_dir, "IntPos.001")
                if os.path.exists(resp_file):
                    self.process_response_file(resp_file)
                    
                time.sleep(0.5)  # Verificar a cada 500ms
            except Exception as e:
                self.log(f"ERRO no monitoramento: {str(e)}")
                
    def process_status_file(self, file_path):
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
            self.log(f"Arquivo de status recebido: {content}")
            self.status_var.set("CTFClient processando solicitação...")
            
            # Remover arquivo após processamento
            os.remove(file_path)
        except Exception as e:
            self.log(f"ERRO ao processar arquivo de status: {str(e)}")
            
    def process_response_file(self, file_path):
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
                
            self.log("Arquivo de resposta recebido:")
            
            # Processar cada linha do arquivo
            for line in lines:
                line = line.strip()
                if line:
                    self.log(f"  {line}")
                    
                    # Verificar status da transação
                    if line.startswith("009-000 ="):
                        status = line.split("=")[1].strip()
                        if status == "0":
                            self.status_var.set("Transação APROVADA!")
                        else:
                            self.status_var.set(f"Transação NEGADA (Status: {status})")
                    
                    # Verificar NSU
                    if line.startswith("012-000 ="):
                        nsu = line.split("=")[1].strip()
                        self.nsu_entry.delete(0, tk.END)
                        self.nsu_entry.insert(0, nsu)
            
            # Remover arquivo após processamento
            os.remove(file_path)
        except Exception as e:
            self.log(f"ERRO ao processar arquivo de resposta: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = TEFIPIntegration(root)
    root.mainloop()