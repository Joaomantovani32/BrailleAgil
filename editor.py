import tkinter as tk
from tkinter.filedialog import askopenfilename, asksaveasfilename
from tkinter import font as tk_font
from pathlib import Path
import pyglet, os, re, roman, pyphen


class editor(tk.Tk):
    def __init__(self):
        super().__init__() # Inicializa a janela Tkinter
        self.title("BrailleÁgil")
        self.geometry("1200x800")
        self.grid_propagate(False)
        # 1. ATRIBUTOS (Variáveis de Controle)
        # Todos os tk.StringVar/IntVar viram atributos da instância (self.)
        self.modo = tk.StringVar(value='AUTO')
        self.linhas_por_pagina = tk.IntVar(value=25)
        self.caracteres_por_linha = tk.IntVar(value=40)
        self.cabecalho = tk.StringVar(value='')
        self.modo_cabecalho = tk.IntVar(value=1)
        self.brFont = 'BraillePT_v2'
        self.numPaginas = tk.StringVar(value="Páginas: 1")
        self.path = Path("pt_BR.dic")
        self.separador = pyphen.Pyphen(filename=self.path)
        self.separacao_silabas = tk.BooleanVar()
        self.tam_br = tk.IntVar(value=16)
        self.tam_txt = tk.IntVar(value=10)

        # --- NOVO ---
        # Mapa para ligar linhas de text_view -> text_edit
        # O índice é a linha da view (base 0), o valor é a linha da edit (base 1)
        self.line_map = []

        # 2. CRIAÇÃO DE WIDGETS
        # Todos os widgets (text_edit, text_view, botões) também viram atributos
        self._create_widgets()

        # 3. LIGAÇÃO INICIAL
        self._initial_binds()

    def _create_widgets(self):
            # --- Janela principal ---

        # --- Área de texto (esquerda) ---
        self.text_edit = tk.Text(self, font=('Hack', self.tam_txt.get()), wrap="word")
        self.text_edit.grid(row=1, column=0, sticky="nsew")

        # --- Visualização em Braille (direita) ---
        self.criar_regua()

        # --- MODIFICADO ---
        # Removido state="disabled" para permitir cliques e tags
        self.text_view = tk.Text(self, font=(self.brFont, self.tam_br.get()), wrap="word")
        self.text_view.grid(row=1, column=1, sticky="nsew")

        # --- NOVO: Tag para highlighting (Req #2) ---
        self.text_view.tag_configure("highlight", background="#add8e6") # lightblue


        # --- Frame com botões ---
        self.frame = tk.Frame(self)
        self.save_button = tk.Button(self.frame, text="Salvar", command=self.save_file)
        self.open_button = tk.Button(self.frame, text="Abrir", command=self.open_file)
        self.braille_button = tk.Button(self.frame, text="Braille/Texto", command=self.brtotxt)
        self.auto_button = tk.Button(self.frame, textvariable=self.modo, command=self.toggle_mode)
        self.update_button = tk.Button(self.frame, text="Atualizar", command=self.atualizar_braille)
        self.config_button = tk.Button(self.frame, text="Config. Página", command=self.menu_config)
        self.contador_paginas = tk.Label(self, textvariable=self.numPaginas, font=('Arial', 10, "bold"))
        self.help_button = tk.Button(self.frame, text="?", command=self.help_menu)

        self.save_button.grid(row=0, column=0, padx=5, pady=5)
        self.open_button.grid(row=0, column=1, padx=5, pady=5)
        self.braille_button.grid(row=0, column=2, padx=5, pady=5)
        self.help_button.grid(row=0, column=3)
        self.auto_button.grid(row=0, column=4, padx=5, pady=5)
        self.config_button.grid(row=0, column=6, padx=5, pady=5) # Coloque-o na próxima coluna livre
        self.contador_paginas.grid(row=0, column=1, sticky="e")
        self.frame.grid(row=0, column=0, columnspan=2, sticky="w")

        # --- Configuração de grid para redimensionar corretamente ---
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

    def criar_regua(self):
        texto = "".join(str(i % 10) for i in range(1, self.caracteres_por_linha.get() + 1))
        self.regua = tk.Label(
            self,
            text=texto,
            font=(self.brFont, 16), # Use a fonte Braille e o tamanho da text_view
            anchor="w",             # Alinha o texto à esquerda (West)
            bg="lightgray"          # Cor de fundo para destacar
        )
        self.regua.grid(row=0, column=1, sticky="ews")

    # --- MODIFICADO ---
    def _initial_binds(self):
        # Atualiza braille ao digitar (chama _sync_scroll_and_highlight no final)
        self.text_edit.bind("<KeyRelease>", self.atualizar_braille)

        # --- NOVO: Binds para Req #1 e #2 ---
        # Sincroniza ao mover o cursor sem digitar (mouse ou setas)
        self.text_edit.bind("<ButtonRelease-1>", self._sync_scroll_and_highlight)
        for key in ["<Up>", "<Down>", "<Left>", "<Right>", "<Home>", "<End>", "<Prior>", "<Next>"]:
            self.text_edit.bind(f"<{key}>", self._sync_scroll_and_highlight)

        # --- NOVO: Binds para Req #3 ---
        # Trava o text_view para ser "read-only"
        self.text_view.bind("<Key>", self._lock_text_view)
        self.text_view.bind("<KeyPress>", self._lock_text_view)
        self.text_view.bind("<<Paste>>", self._lock_text_view)
        self.text_view.bind("<<Cut>>", self._lock_text_view)

        # O bind do clique duplo
        self.text_view.bind("<Double-Button-1>", self._on_view_double_click)

    # --- NOVO (Helper para Req #3) ---
    def _lock_text_view(self, event=None):
        """ Impede a edição no text_view, mas permite eventos de mouse. """
        return "break"

    # --- NOVO (Função para Req #1 e #2) ---
    def _sync_scroll_and_highlight(self, event=None):
        """ Sincroniza o scroll e destaca a linha na view com base no cursor da edit. """

        # 1. Remove o highlight antigo
        self.text_view.tag_remove("highlight", "1.0", tk.END)

        try:
            # 2. Pega a linha atual no editor (ex: "5.10" -> 5)
            cursor_index = self.text_edit.index(tk.INSERT)
            edit_line_num = int(cursor_index.split('.')[0])

            # 3. Encontra a linha correspondente na view usando o mapa
            # O mapa (self.line_map) tem índices 0-based
            # Os valores (edit_line_num) são 1-based
            if not self.line_map: # Mapa ainda não foi construído
                return

            view_line_index = self.line_map.index(edit_line_num)
            view_line_num = view_line_index + 1 # Converte índice para linha Tkinter (1-based)

        except (ValueError, AttributeError, IndexError):
            # Linha não encontrada no mapa (ex: linha 0, ou mapa desatualizado)
            return

        # 4. Adiciona o novo highlight (Req #2)
        view_line_start = f"{view_line_num}.0"
        view_line_end = f"{view_line_num}.end"
        self.text_view.tag_add("highlight", view_line_start, view_line_end)

        # 5. Rola a view para a linha (Req #1)
        self.text_view.see(view_line_start)


    # --- NOVO (Função para Req #3) ---
    def _on_view_double_click(self, event):
        """ Move o cursor no text_edit para a linha correspondente ao clique no text_view. """
        try:
            # 1. Pega a linha que foi clicada na view (ex: "12.5" -> 12)
            clicked_index = self.text_view.index(f"@{event.x},{event.y}")
            view_line_num = int(clicked_index.split('.')[0])

            # 2. Converte para o índice 0-based do nosso mapa
            view_line_index = view_line_num - 1

            if view_line_index < 0 or view_line_index >= len(self.line_map):
                return # Clique fora dos limites do mapa

            # 3. Pega a linha de edição correspondente no mapa
            edit_line_num = self.line_map[view_line_index]

            if edit_line_num == 0:
                # É um cabeçalho (0). Acha a próxima linha de texto válida.
                for i in range(view_line_index + 1, len(self.line_map)):
                    if self.line_map[i] != 0:
                        edit_line_num = self.line_map[i]
                        break
                if edit_line_num == 0: # Se ainda for 0, não faz nada
                    return

        except (AttributeError, IndexError, ValueError):
            return # Mapa não existe ou clique inválido

        # 4. Move o cursor no text_edit
        target_index = f"{edit_line_num}.0"
        self.text_edit.mark_set(tk.INSERT, target_index)
        self.text_edit.see(target_index)

        # 5. Devolve o "foco" para a janela de edição
        self.text_edit.focus_set()


    def marcar_maiusculas(self):
        """
        Adiciona os indicadores Braille, processa tags de formatação
        e formata o texto em linhas e páginas.
        AGORA TAMBÉM GERA O self.line_map
        """

        # --- Funções Internas de Regras Braille (copiadas do seu código) ---
        # ... (processar_numeros e processar_palavra sem modificações) ...
        def processar_numeros(palavra):
            sinal = False
            if palavra.isdigit():
                return '#' + palavra
            final = ''
            escaped = False
            for c in palavra:
                if c == '`':
                    escaped = True
                    continue
                if c.isdigit():
                    if not sinal:
                        sinal = True
                        final += '#'
                elif c.isalpha():
                    if sinal:
                        final += '~'
                    sinal = False
                elif c in '()[]':
                    if sinal:
                        final += '~'
                    sinal = False
                elif c not in {'.', ','}:
                    if sinal:
                        final += '~'
                    sinal = False
                if escaped:
                    final += c
                    escaped = False
                elif c.isalpha() and c.isupper():
                    final += '.' + c
                elif c in '([':
                    final += c + '.'
                elif c in ')]':
                    final += 'ý' + c
                else:
                    final += c
            return final

        def processar_palavra(palavra):
            if any(c.isdigit() for c in palavra):
                return processar_numeros(palavra)
            final = ''
            escaped = False
            for c in palavra:
                if c == '`':
                    escaped = True
                    continue
                if escaped:
                    final += c
                    escaped = False
                elif c.isupper():
                    final += '.' + c
                elif c in '([':
                    final += c + '.'
                elif c in ')]':
                    final += 'ý' + c
                else:
                    final += c
            return final

        # --- Variáveis de Paginação e Estado de Formatação ---

        linhas_finais = []
        linha_braille_atual = ""
        num_linhas_pagina = 0
        pagina_atual = 1
        paginas_totais = 0
        pagina_texto = ''
        paginas_romanas = False
        esta_recuado = False
        primeira_linha_do_bloco = True
        indice_numero_pagina = 0

        # --- NOVO: Reinicia o mapa de linhas ---
        self.line_map = []
        # Linha de origem atual (base 1), 0 = linha do sistema (cabeçalho/etc)
        source_line_num = 0

        modo_formatado = True

        try:
            max_chars = self.caracteres_por_linha.get()
            max_linhas = self.linhas_por_pagina.get()
        except Exception:
            max_chars = 40
            max_linhas = 25

        # --- Funções Helper de Paginação (MODIFICADAS para o mapa) ---

        def adicionar_header():
            # --- MODIFICADO ---
            nonlocal num_linhas_pagina, pagina_atual, indice_numero_pagina, paginas_totais, source_line_num
            tipo = self.modo_cabecalho.get()
            if tipo==1 or pagina_atual%2 == 1:
                linha = gerar_header(pagina_atual)
                linhas_finais.append(linha)
                self.line_map.append(0) # 0 = Linha do sistema
                indice_numero_pagina = len(linhas_finais) - 1
                num_linhas_pagina += 1
            paginas_totais += 1

        def gerar_header(pagina_atual):
            # ... (sem modificações) ...
            nonlocal paginas_romanas
            if paginas_romanas:
                num_pagina = '..' + roman.toRoman(pagina_atual)
            else:
                num_pagina = '#'+str(pagina_atual)
            head = self.cabecalho.get()
            head_len = len(head)
            espacos = max_chars - len(head) - len(num_pagina) - len(pagina_texto)
            espacos_antes = espacos // 2
            espacos_depois = espacos - espacos_antes
            return (pagina_texto + (' ' * espacos_antes) + head + (' ' * espacos_depois) + num_pagina)

        def numeracao_pagina(tipo, numero):
            # ... (sem modificações) ...
            nonlocal pagina_atual, paginas_romanas
            if tipo == '*':
                paginas_romanas = True
            if tipo == '+':
                paginas_romanas = False
            pagina_atual = int(numero)
            tipo = self.modo_cabecalho.get()
            if tipo==1 or pagina_atual%2 == 1:
                linhas_finais[indice_numero_pagina] = gerar_header(pagina_atual)

        def numeracao_pagina_texto(numero):
            # ... (sem modificações) ...
            nonlocal pagina_atual, pagina_texto
            pagina_texto = '  #' + str(numero)
            if pagina_atual == 0:
                pagina_atual = 1
            linhas_finais[indice_numero_pagina] = gerar_header(pagina_atual)

        def verificar_paginacao():
            # --- MODIFICADO ---
            nonlocal num_linhas_pagina, pagina_atual, source_line_num
            if num_linhas_pagina > 0 and num_linhas_pagina % max_linhas == 0:
                linhas_finais.append("-" * max_chars)
                self.line_map.append(0) # 0 = Linha do sistema (quebra de pág)
                num_linhas_pagina = 0
                pagina_atual += 1
                adicionar_header()

        def finalizar_linha_atual():
            """ Salva a linha Braille atual, atualiza contagens e verifica paginação. """
            # --- MODIFICADO ---
            nonlocal linha_braille_atual, num_linhas_pagina, source_line_num
            if linha_braille_atual:
                linhas_finais.append(linha_braille_atual)
                self.line_map.append(source_line_num) # <-- A MÁGICA
            else:
                if not linhas_finais or linhas_finais[-1] != "":
                     linhas_finais.append("")
                     self.line_map.append(source_line_num) # <-- A MÁGICA

            num_linhas_pagina += 1
            verificar_paginacao()
            linha_braille_atual = ""

        def forcar_quebra_pagina():
            """ Processa a tag <p>. """
            # --- MODIFICADO ---
            nonlocal num_linhas_pagina, pagina_atual, quebra_manual, source_line_num
            quebra_manual = True
            finalizar_linha_atual()

            linhas_finais.append("-" * max_chars)
            self.line_map.append(0) # 0 = Linha do sistema (quebra de pág)

            num_linhas_pagina = 0
            pagina_atual += 1
            adicionar_header()

        # --- FUNÇÃO HELPER DE QUEBRA (FORMATADA) ---
        def proxima_linha(palavra_a_mover):
            # ... (sem modificações) ...
            nonlocal primeira_linha_do_bloco, linha_braille_atual
            finalizar_linha_atual()
            primeira_linha_do_bloco = False
            margem_atual = 2 if esta_recuado else 0
            linha_braille_atual = " " * margem_atual
            comprimento_palavra = len(palavra_a_mover)
            espaco_disponivel = max_chars - margem_atual
            if comprimento_palavra > espaco_disponivel:
                linha_braille_atual += palavra_a_mover[:espaco_disponivel]
                finalizar_linha_atual()
                linha_braille_atual = (" " * margem_atual) + palavra_a_mover[espaco_disponivel:]
            else:
                linha_braille_atual += palavra_a_mover

        # --- NOVA FUNÇÃO HELPER DE QUEBRA (LITERAL) ---
        def proxima_linha_literal(palavra_a_mover):
            # ... (sem modificações) ...
            nonlocal linha_braille_atual
            finalizar_linha_atual()
            linha_braille_atual = ""
            comprimento_palavra = len(palavra_a_mover)
            if comprimento_palavra > max_chars:
                linha_braille_atual += palavra_a_mover[:max_chars]
                finalizar_linha_atual()
                linha_braille_atual = palavra_a_mover[max_chars:]
            else:
                linha_braille_atual += palavra_a_mover

        # --- Processamento Principal com Tags ---

        adicionar_header() # Para a primeira página

        texto = self.text_edit.get("1.0", tk.END)
        linhas_de_texto_originais = texto.split('\n')

        # --- MODIFICADO ---
        for i, linha_txt in enumerate(linhas_de_texto_originais):
            source_line_num = i + 1 # Linha 1-based do text_edit

            quebra_manual = False

            if not linha_txt:
                # Se a linha de origem estiver vazia, apenas finaliza
                finalizar_linha_atual()
                primeira_linha_do_bloco = True
                continue

            partes_da_linha = re.split(r'(<[^>]+>)', linha_txt)

            for parte in partes_da_linha:
                if not parte:
                    continue

                # --- CASO A: A PARTE É UMA TAG ---
                if parte.startswith('<') and parte.endswith('>'):
                    # ... (lógica de tags sem modificação) ...
                    palavra_lower = parte.lower()
                    if palavra_lower == '<f->':
                        modo_formatado = False
                        continue
                    if palavra_lower == '<f+>':
                        modo_formatado = True
                        continue
                    if not modo_formatado:
                        continue
                    if palavra_lower == '<r+>':
                        esta_recuado = True
                        primeira_linha_do_bloco = True
                        continue
                    if palavra_lower == '<r->':
                        esta_recuado = False
                        primeira_linha_do_bloco = True
                        continue
                    if palavra_lower == '<p>':
                        forcar_quebra_pagina()
                        continue
                    padrao = r'^<t(\+|\*)([0-9]+)>$'
                    match = re.match(padrao, palavra_lower)
                    if match:
                        numeracao_pagina(match.group(1), match.group(2))
                        continue
                    padrao = r'^<([0-9]+)>$'
                    match = re.match(padrao, palavra_lower)
                    if match:
                        numeracao_pagina_texto(match.group(1))
                        continue
                    continue

                # --- CASO B: A PARTE É TEXTO ---
                if modo_formatado:
                    # ... (lógica do modo formatado sem modificação) ...
                    espacos_inicio_len = len(parte) - len(parte.lstrip(' '))
                    if espacos_inicio_len > 0 and not linha_braille_atual:
                         linha_braille_atual += " " * espacos_inicio_len
                    palavras_desta_parte = parte.split()
                    for palavra_txt in palavras_desta_parte:
                        palavra_braille = processar_palavra(palavra_txt)
                        if not palavra_braille:
                            continue
                        margem_atual = 0
                        if esta_recuado and not primeira_linha_do_bloco:
                            margem_atual = 2
                        if not linha_braille_atual:
                            linha_braille_atual = " " * margem_atual
                        comprimento_palavra = len(palavra_braille)
                        comprimento_linha = len(linha_braille_atual)
                        espaco = 1 if comprimento_linha > margem_atual else 0
                        if comprimento_linha + espaco + comprimento_palavra <= max_chars:
                            linha_braille_atual += (" " * espaco) + palavra_braille
                        else:
                            pode_hifenizar = ((num_linhas_pagina < max_linhas - 1) and self.separacao_silabas.get())
                            espaco_livre = max_chars - comprimento_linha - espaco
                            partes_hifen = None
                            if pode_hifenizar and espaco_livre > 2:
                                partes_hifen = self.separador.wrap(palavra_txt, espaco_livre)
                            if partes_hifen:
                                braille_p1 = processar_palavra(partes_hifen[0])
                                braille_p2 = processar_palavra(partes_hifen[1])
                                linha_braille_atual += (" " * espaco) + braille_p1
                                proxima_linha(braille_p2)
                            else:
                                proxima_linha(palavra_braille)
                else:
                    # ... (lógica do modo literal sem modificação) ...
                    palavra_literal = parte
                    comprimento_palavra = len(palavra_literal)
                    comprimento_linha = len(linha_braille_atual)
                    if comprimento_linha + comprimento_palavra <= max_chars:
                        linha_braille_atual += palavra_literal
                    else:
                        espaco_livre = max_chars - comprimento_linha
                        linha_braille_atual += palavra_literal[:espaco_livre]
                        proxima_linha_literal(palavra_literal[espaco_livre:])

            # --- Fim do loop de 'partes' ---
            if quebra_manual != True:
                finalizar_linha_atual()
                quebra_manual = False
            primeira_linha_do_bloco = True

        # --- Fim do loop de 'linhas' ---

        # --- MODIFICADO ---
        if linha_braille_atual:
            linhas_finais.append(linha_braille_atual)
            self.line_map.append(source_line_num) # Mapeia a última linha
            paginas_totais +=1

        self.numPaginas.set("Páginas: " + str(paginas_totais))
        return "\n".join(linhas_finais)

    def open_file(self):
        # ... (sem modificações) ...
        filepath = askopenfilename(
            filetypes=[('Text Files', '*.txt'), ('All Files', '*.*')]
        )
        if not filepath:
            return
        self.text_edit.delete(1.0, tk.END)
        with open(filepath, 'r') as input_file:
            text = input_file.read()
            self.text_edit.insert(tk.END, text)
        self.title(f'Braille Editor - {filepath}') # 'window' trocado por 'self'
        self.atualizar_braille() # 'atualizar_braille' trocado por 'self.atualizar_braille'

    def save_file(self):
        # ... (sem modificações, exceto 'window' e 'text_edit') ...
        filepath = asksaveasfilename(
            defaultextension='txt',
            filetypes=[('Text Files', '*.txt'), ('All Files', '*.*')],
        )
        if not filepath:
            return
        with open(filepath, 'w') as output_file:
            text = self.text_edit.get(1.0, tk.END) # 'text_edit' trocado por 'self.text_edit'
            output_file.write(text)
        self.title(f'Braille Editor - {filepath}') # 'window' trocado por 'self'

    def brtotxt(self):
        # ... (sem modificações) ...
        if self.brFont == 'Hack':
            self.brFont = 'BraillePT_v2'
        else:
            self.brFont = 'Hack'
        self.text_view.config(font=(self.brFont, self.tam_br.get()))
        self.atualizar_braille()
        self.criar_regua()

    def help_menu(self):
        # ... (sem modificações) ...
        help_window = tk.Toplevel(self)
        help_window.title("Ajuda Comandos")
        tk.Label(help_window, text="<p> Quebra de página").grid(row=0, column=0, sticky="w")
        tk.Label(help_window, text="<r+> Recuo de 2 espaços").grid(row=1, column=0, sticky="w")
        tk.Label(help_window, text="<r-> Fim do recuo de 2").grid(row=2, column=0, sticky="w")
        tk.Label(help_window, text="<f+> Formatação automática").grid(row=3, column=0, sticky="w")
        tk.Label(help_window, text="<f-> Sem formatação").grid(row=4, column=0, sticky="w")
        tk.Label(help_window, text="<t+x> Página Braille x").grid(row=5, column=0, sticky="w")
        tk.Label(help_window, text="<t*y> Paǵina romana y").grid(row=6, column=0, sticky="w")
        tk.Label(help_window, text="<xx> xx é o número da página do livro texto").grid(row=7, column=0, sticky="w")

    def menu_config(self):
        # ... (sem modificações) ...
        config_window = tk.Toplevel(self)
        config_window.title("Configurações de Página")
        def salvar_cfg():
            self.caracteres_por_linha.get()
            self.linhas_por_pagina.get()
            self.cabecalho.get()
            self.atualizar_braille()
            self.criar_regua()
            self.text_view.config(font=(self.brFont, self.tam_br.get()))
            self.text_edit.config(font=("Hack", self.tam_txt.get()))
            config_window.destroy()
        def cancelar_cfg():
            config_window.destroy()
        tk.Label(config_window, text="Linhas por página:").grid(row=0, column=0)
        linhas_spinbox = tk.Spinbox(
            config_window,
            from_=10, to=80,
            textvariable=self.linhas_por_pagina,
            width=5
        )
        linhas_spinbox.grid(row=0, column=1)
        tk.Label(config_window, text="Caracteres por Linha:").grid(row=1, column=0)
        caracteres_spinbox = tk.Spinbox(
            config_window,
            from_=10, to=80,
            textvariable=self.caracteres_por_linha,
            width=5
        )
        caracteres_spinbox.grid(row=1, column=1)
        tk.Label(config_window, text="Texto do cabeçalho:").grid(row=2, column=0)
        entrada = tk.Entry(config_window, textvariable=self.cabecalho, width=30)
        entrada.grid(row=2, column=1)
        r1 = tk.Radiobutton(config_window, text='Frente e verso', value=1, variable=self.modo_cabecalho)
        r2 = tk.Radiobutton(config_window, text='Somente Frente', value=2, variable=self.modo_cabecalho)
        r1.grid(row=3, column=0)
        r2.grid(row=3, column=1)
        tk.Label(config_window, text="Separa sílabas").grid(row=4, column=0)
        check_silabas = tk.Checkbutton(
            config_window,
            variable=self.separacao_silabas,
            onvalue=True,
            offvalue=False
        )
        check_silabas.grid(row=4, column=1, sticky="w")
        tk.Label(config_window, text="Tamanho da fonte Texto:").grid(row=5, column=0)
        tamtxt_spinbox = tk.Spinbox(
            config_window,
            from_=5, to=40,
            textvariable=self.tam_txt,
            width=5
        )
        tamtxt_spinbox.grid(row=5, column=1)
        tk.Label(config_window, text="Tamanho da fonte Braille:").grid(row=6, column=0)
        tambr_spinbox = tk.Spinbox(
            config_window,
            from_=5, to=40,
            textvariable=self.tam_br,
            width=5
        )
        tambr_spinbox.grid(row=6, column=1)
        salvar_cfg_button = tk.Button(config_window, text="salvar", command=salvar_cfg)
        cancelar_cfg_button = tk.Button(config_window, text="cancelar", command=cancelar_cfg)
        salvar_cfg_button.grid(row=7, column=0)
        cancelar_cfg_button.grid(row=7, column=1)

    # --- MODIFICADO ---
    def atualizar_braille(self, event=None):
        convertido = self.marcar_maiusculas()

        # self.text_view.config(state="normal") # Não é mais necessário
        self.text_view.delete("1.0", tk.END)
        self.text_view.insert(tk.END, convertido)
        # self.text_view.config(state="disabled") # Não é mais necessário

        # --- NOVO ---
        # Chama a função de sync/highlight após a atualização
        self._sync_scroll_and_highlight()


    def toggle_mode(self):
        if self.modo.get() == "AUTO":
            self.modo.set("MANUAL")
            self.text_edit.unbind("<KeyRelease>")
            self.update_button.grid(row=0, column=5, padx=5)
        else:
            self.modo.set("AUTO")
            self.update_button.grid_remove()
            self.atualizar_braille(self)
            self.text_edit.bind("<KeyRelease>", self.atualizar_braille)

if __name__ == '__main__':
    app = editor()
    app.mainloop()
