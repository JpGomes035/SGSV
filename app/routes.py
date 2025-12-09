from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import Usuario, Solicitacao
from sqlalchemy.exc import IntegrityError
from datetime import datetime


print("--- ROTAS CARREGADAS COM SUCESSO ---")

bp = Blueprint('main', __name__)
@bp.app_template_filter('datetimeformat')
def datetimeformat(value, format='%d-%m-%y'):
    try:
        # tenta converter string do tipo "2025-12-09"
        return datetime.strptime(value, "%Y-%m-%d").strftime(format)
    except:
        return value  # se falhar, retorna como está
# --- Context Processor: Simula o 'current_user' para o HTML ---
@bp.context_processor
def inject_user():
    class MockUser:
        is_authenticated = 'user_id' in session
        name = session.get('user_nome')
        id = session.get('user_id')
        role = session.get('user_tipo')
    return dict(current_user=MockUser())

# --- DASHBOARD UVIS ---
@bp.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    if session.get('user_tipo') == 'admin':
        return redirect(url_for('main.admin_dashboard'))

    try:
        user_id = int(session.get('user_id'))
    except (ValueError, TypeError):
        session.clear()
        flash('Sessão Inválida. Por favor, faça login novamente.', 'warning')
        return redirect(url_for('main.login'))
    
    query = Solicitacao.query.filter_by(usuario_id=user_id).order_by(Solicitacao.data_criacao.desc())
    
    print("\n===============================")
    print(f"DEBUG: USUÁRIO LOGADO ID (SESSÃO): {user_id}")
    print(f"DEBUG: FILTRO SQL A SER EXECUTADO: {query.statement.compile(compile_kwargs={'literal_binds': True})}")
    print("===============================\n")
    
    lista_solicitacoes = query.all()
    return render_template('dashboard.html', nome=session.get('user_nome'), solicitacoes=lista_solicitacoes)

# --- PAINEL ADMIN (com filtros) ---
@bp.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('user_tipo') != 'admin':
        return redirect(url_for('main.login'))
    
    # --- Captura filtros enviados pelo GET ---
    filtro_status = request.args.get("status")
    filtro_unidade = request.args.get("unidade")
    filtro_regiao = request.args.get("regiao")

    # --- Query base ---
    query = Solicitacao.query.join(Usuario)

    # --- Filtros aplicáveis ---
    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)

    if filtro_unidade:
        query = query.filter(Usuario.nome_uvis.ilike(f"%{filtro_unidade}%"))

    if filtro_regiao:
        query = query.filter(Usuario.regiao.ilike(f"%{filtro_regiao}%"))

    pedidos_filtrados = query.order_by(Solicitacao.data_criacao.desc()).all()

    return render_template('admin.html', pedidos=pedidos_filtrados)

@bp.route('/admin/exportar_excel')
def exportar_excel():
    if 'user_id' not in session or session.get('user_tipo') != 'admin':
        return redirect(url_for('main.login'))

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO
    from flask import send_file

    # --- Captura filtros ---
    filtro_status = request.args.get("status")
    filtro_unidade = request.args.get("unidade")
    filtro_regiao = request.args.get("regiao")

    # Query base
    query = Solicitacao.query.join(Usuario)

    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)

    if filtro_unidade:
        query = query.filter(Usuario.nome_uvis.ilike(f"%{filtro_unidade}%"))

    if filtro_regiao:
        query = query.filter(Usuario.regiao.ilike(f"%{filtro_regiao}%"))

    pedidos = query.order_by(Solicitacao.data_criacao.desc()).all()

    # --- CRIA EXCEL ---
    wb = Workbook()
    ws = wb.active
    ws.title = "Relatório de Solicitações"

    # Cabeçalho
    headers = [
        "ID",
        "Unidade (UVIS)",
        "Região",
        "CEP",
        "Endereço Completo",
        "UF",
        "Foco da Ação",
        "Data Agendamento",
        "Hora Agendamento",
        "Status",
        "Protocolo DECEA",
        "Coordenadas",
        "Justificativa"
    ]

    # Estilos
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Escreve cabeçalho
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    # Conteúdo
    row_num = 2
    for p in pedidos:

        # Monta o endereço completo
        endereco_completo = f"{p.logradouro or ''}, {getattr(p, 'numero', '') or ''} - {p.bairro or ''}, {p.cidade or ''}".strip()
        endereco_completo = endereco_completo.replace(" ,", "").replace(" - ,", "").replace(", ,", ",")


    # Formata a data
        if p.data_agendamento:
            try:
                data_formatada = datetime.strptime(p.data_agendamento, "%Y-%m-%d").strftime("%d-%m-%y")
            except ValueError:
                data_formatada = p.data_agendamento
        else:
            data_formatada = ""
            
        row = [
        p.id,
        p.autor.nome_uvis,
        p.autor.regiao,
        p.cep,
        endereco_completo,
        p.uf,
        p.foco,
        data_formatada,  # << aqui usamos a data formatada
        p.hora_agendamento,
        p.status,
        p.protocolo,
        p.coords,
        p.justificativa
    ]

        for col_num, value in enumerate(row, 1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center", wrap_text=True)

        row_num += 1

    # Freeze Pane
    ws.freeze_panes = "A2"

    # Ajuste automático de largura
    for col in ws.columns:
        max_length = 0
        column = col[0].column  # Número da coluna

        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass

        adjusted_width = max_length + 2
        ws.column_dimensions[get_column_letter(column)].width = adjusted_width

    # Salvar em memória
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Enviar arquivo
    return send_file(
        output,
        download_name="relatorio_solicitacoes.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# --- ROTA DE ATUALIZAÇÃO ---
@bp.route('/admin/atualizar/<int:id>', methods=['POST'])
def atualizar(id):
    if session.get('user_tipo') != 'admin':
        return redirect(url_for('main.login'))
    
    pedido = Solicitacao.query.get_or_404(id)
    
    pedido.coords = request.form.get('coords')
    pedido.protocolo = request.form.get('protocolo')
    pedido.status = request.form.get('status')
    pedido.justificativa = request.form.get('justificativa')
    
    db.session.commit()
    flash('Pedido atualizado com sucesso!', 'success')
    
    return redirect(url_for('main.admin_dashboard'))

# --- NOVO PEDIDO ---
@bp.route('/novo_cadastro', methods=['GET', 'POST'], endpoint='novo')
def novo():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    from datetime import date
    #Trava data aqui pra não inserir uma anterior que hoje
    hoje = date.today().isoformat() 

    if request.method == 'POST':
        try:
            user_id_int = int(session['user_id'])

            nova_solicitacao = Solicitacao(
                data_agendamento=request.form.get('data'),
                hora_agendamento=request.form.get('hora'),

                cep=request.form.get('cep'),
                logradouro=request.form.get('logradouro'),
                bairro=request.form.get('bairro'),
                cidade=request.form.get('cidade'),
                numero=request.form.get('numero'),
                uf=request.form.get('uf'),

                foco=request.form.get('foco'),
                usuario_id=user_id_int,
                status='EM ANÁLISE'
            )

            db.session.add(nova_solicitacao)
            db.session.commit()

            flash('Pedido enviado para análise!', 'success')
            return redirect(url_for('main.dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar: {e}", "danger")

    return render_template('cadastro.html', hoje=hoje)

# --- LOGIN ---
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('user_tipo') == 'admin':
            return redirect(url_for('main.admin_dashboard'))
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        user = Usuario.query.filter_by(login=request.form.get('login')).first()

        if user and user.check_senha(request.form.get('senha')):
            session['user_id'] = int(user.id)
            session['user_nome'] = user.nome_uvis
            session['user_tipo'] = user.tipo_usuario
            
            if user.tipo_usuario == 'admin':
                return redirect(url_for('main.admin_dashboard'))
            return redirect(url_for('main.dashboard'))
        else:
            flash('Login incorreto.', 'danger')

    return render_template('login.html')

# --- LOGOUT ---
@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))