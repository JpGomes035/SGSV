from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import Usuario, Solicitacao
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date
from flask import json
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from io import BytesIO
from flask import send_file


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
        tipo_usuario = session.get('user_tipo')
    return dict(current_user=MockUser())

# --- DASHBOARD UVIS ---

@bp.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    # AJUSTE CHAVE: Se for admin, operario OU visualizar, redireciona para o painel de gestão
    if session.get('user_tipo') in ['admin', 'operario', 'visualizar']:
        return redirect(url_for('main.admin_dashboard'))

    try:
        user_id = int(session.get('user_id'))
    except (ValueError, TypeError):
        session.clear()
        flash('Sessão Inválida. Por favor, faça login novamente.', 'warning')
        return redirect(url_for('main.login'))

    # 1. Query Base: Pega os pedidos SÓ deste usuário
    query = Solicitacao.query.filter_by(usuario_id=user_id)

    # 2. Lógica do Filtro: Verifica se veio algo na URL (ex: ?status=PENDENTE)
    filtro_status = request.args.get('status')

    if filtro_status:
        query = query.filter(Solicitacao.status == filtro_status)

    # 3. Lógica da Paginação:
    page = request.args.get("page", 1, type=int)

    paginacao = query.order_by(
        Solicitacao.data_criacao.desc()
    ).paginate(page=page, per_page=6, error_out=False)

    return render_template(
        'dashboard.html',
        nome=session.get('user_nome'),
        solicitacoes=paginacao.items,
        paginacao=paginacao
    )

# --- PAINEL DE GESTÃO (Visualização para todos) ---
@bp.route('/admin')
def admin_dashboard():
    # AJUSTE CHAVE: Permite 'admin', 'operario' E 'visualizar'
    if 'user_id' not in session or session.get('user_tipo') not in ['admin', 'operario', 'visualizar']:
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.login'))
    
    # Flag para controlar a renderização dos botões de edição no template
    is_editable = session.get('user_tipo') in ['admin', 'operario']
    
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

    page = request.args.get("page", 1, type=int)

    paginacao = query.order_by(
    Solicitacao.data_criacao.desc()
    ).paginate(page=page, per_page=6)

    return render_template(
    'admin.html',
    pedidos=paginacao.items,
    paginacao=paginacao,
    is_editable=is_editable # Variável enviada ao template para controle de formulário
)

@bp.route('/admin/exportar_excel')
def exportar_excel():
    # AJUSTE CHAVE: Permite APENAS 'admin' E 'operario'
    if 'user_id' not in session or session.get('user_tipo') not in ['admin', 'operario']:
        flash('Permissão negada para exportar.', 'danger')
        return redirect(url_for('main.admin_dashboard'))

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

    # Cabeçalho ATUALIZADO (do segundo código, com mais campos)
    headers = [
        "ID", "Unidade", "Região",
        "Data Agendada", "Hora",
        "CEP", "Logradouro", "Número", "Bairro", "Cidade/UF", "Complemento",
        "Latitude", "Longitude",
        "Foco", "Tipo Visita", "Altura", "Criadouro?", "Apoio CET?",
        "Observação",
        "Status", "Protocolo", "Justificativa"
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
        # Tratamento de Endereço (baseado no segundo código, mas mantendo a UF separada para clareza)
        cidade_uf = f"{p.cidade or ''}/{p.uf or ''}"
        logradouro_num = f"{p.logradouro or ''}"

        # Tratamento de Booleans (Sim/Não) do segundo código
        criadouro_txt = "SIM" if getattr(p, 'criadouro', None) else "NÃO"
        cet_txt = "SIM" if getattr(p, 'apoio_cet', None) else "NÃO"

        # Formatação de data (Corrigido o erro de importação de datetime)
        if p.data_agendamento:
            try:
                if isinstance(p.data_agendamento, (date, datetime)): 
                    data_formatada = p.data_agendamento.strftime("%d-%m-%y")
                # Se for string (caso do primeiro código)
                else:
                    data_formatada = datetime.strptime(str(p.data_agendamento), "%Y-%m-%d").strftime("%d-%m-%y")
            except ValueError:
                data_formatada = str(p.data_agendamento)
        else:
            data_formatada = ""

        row = [
            p.id,
            p.autor.nome_uvis,
            p.autor.regiao,
            data_formatada,
            p.hora_agendamento,
            p.cep,
            logradouro_num,
            getattr(p, 'numero', ''),
            p.bairro,
            cidade_uf,
            getattr(p, 'complemento', ''),
            getattr(p, 'latitude', ''),
            getattr(p, 'longitude', ''),
            p.foco,
            getattr(p, 'tipo_visita', ''),
            getattr(p, 'altura_voo', ''),
            criadouro_txt,
            cet_txt,
            getattr(p, 'observacao', ''),
            p.status,
            p.protocolo,
            p.justificativa
        ]

        for col_num, value in enumerate(row, 1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center", wrap_text=True)

        row_num += 1

    # Freeze Pane (Mantido do primeiro código)
    ws.freeze_panes = "A2"

    # Ajuste automático de largura (Lógica do primeiro código, mas com a correção de 'column' para 'column_letter')
    for col in ws.columns:
        max_length = 0
        column_letter = col[0].column_letter 

        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass

        adjusted_width = max_length + 2
        ws.column_dimensions[column_letter].width = adjusted_width

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
    # AJUSTE CHAVE: Permite APENAS 'admin' E 'operario'
    if session.get('user_tipo') not in ['admin', 'operario']:
        flash('Permissão negada para esta ação.', 'danger')
        return redirect(url_for('main.admin_dashboard'))

    pedido = Solicitacao.query.get_or_404(id)

    # Campos de Geo do segundo código:
    pedido.protocolo = request.form.get('protocolo')
    pedido.status = request.form.get('status')
    pedido.justificativa = request.form.get('justificativa')
    pedido.latitude = request.form.get('latitude')
    pedido.longitude = request.form.get('longitude')


    db.session.commit()
    flash('Pedido atualizado com sucesso!', 'success')

    return redirect(url_for('main.admin_dashboard'))

# --- NOVO PEDIDO ---
@bp.route('/novo_cadastro', methods=['GET', 'POST'], endpoint='novo')
def novo():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    hoje = date.today().isoformat()

    if request.method == 'POST':
        try:
            user_id_int = int(session['user_id'])

            data_str = request.form.get('data')
            hora_str = request.form.get('hora')

            if data_str:
                data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
            else:
                data_obj = None

            if hora_str:
                hora_obj = datetime.strptime(hora_str, '%H:%M').time()
            else:
                hora_obj = None

            criadouro_bool = request.form.get('criadouro') == 'sim'
            apoio_cet_bool = request.form.get('apoio_cet') == 'sim'


            nova_solicitacao = Solicitacao(
                data_agendamento=data_obj,
                hora_agendamento=hora_obj,

                cep=request.form.get('cep'),
                logradouro=request.form.get('logradouro'),
                bairro=request.form.get('bairro'),
                cidade=request.form.get('cidade'),
                numero=request.form.get('numero'),
                uf=request.form.get('uf'),
                complemento=request.form.get('complemento'), 

                foco=request.form.get('foco'),

                tipo_visita=request.form.get('tipo_visita'),
                altura_voo=request.form.get('altura_voo'),
                criadouro=criadouro_bool,
                apoio_cet=apoio_cet_bool,
                observacao=request.form.get('observacao'),

                latitude=request.form.get('latitude'),
                longitude=request.form.get('longitude'),

                usuario_id=user_id_int,
                status='PENDENTE'
            )

            db.session.add(nova_solicitacao)
            db.session.commit()

            flash('Pedido enviado!', 'success')
            return redirect(url_for('main.dashboard'))

        except ValueError as ve:
            db.session.rollback()
            flash(f"Erro no formato de data/hora: {ve}", "warning")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar: {e}", "danger")

    return render_template('cadastro.html', hoje=hoje)

# --- LOGIN ---
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        # AJUSTE CHAVE: Redireciona para admin_dashboard se for admin, operario OU visualizar
        if session.get('user_tipo') in ['admin', 'operario', 'visualizar']:
            return redirect(url_for('main.admin_dashboard'))
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        user = Usuario.query.filter_by(login=request.form.get('login')).first()

        if user and user.check_senha(request.form.get('senha')):
            session['user_id'] = int(user.id)
            session['user_nome'] = user.nome_uvis
            session['user_tipo'] = user.tipo_usuario

            flash(f'Bem-vindo, {user.nome_uvis}! Login realizado com sucesso.', 'success')

            # AJUSTE CHAVE: Redireciona para admin_dashboard se for admin, operario OU visualizar
            if user.tipo_usuario in ['admin', 'operario', 'visualizar']:
                return redirect(url_for('main.admin_dashboard'))
            return redirect(url_for('main.dashboard'))
        else:
            flash('Login ou senha incorretos. Tente novamente.', 'danger')

    return render_template('login.html')

# --- LOGOUT ---
@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))

@bp.route("/forcar_erro")
def forcar_erro():
    1 / 0  # erro proposital
    return "nunca vai chegar aqui"

@bp.route('/relatorios', methods=['GET'])
def relatorios():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    # filtros de mês/ano (valores inteiros)
    mes_atual = request.args.get('mes', datetime.now().month, type=int)
    ano_atual = request.args.get('ano', datetime.now().year, type=int)
    filtro_data = f"{ano_atual}-{mes_atual:02d}"

    # ----- HISTÓRICO MENSAL (para montar anos disponíveis) -----
    dados_mensais_raw = (
        db.session.query(
            db.func.strftime('%Y-%m', Solicitacao.data_criacao).label('mes'),
            db.func.count(Solicitacao.id)
        )
        .group_by('mes')
        .order_by('mes')
        .all()
    )
    dados_mensais = [tuple(row) for row in dados_mensais_raw]

    anos_disponiveis = sorted(list(set([d[0].split('-')[0] for d in dados_mensais])), reverse=True)
    if not anos_disponiveis:
        anos_disponiveis = [ano_atual]

    # ----- TOTALIZAÇÕES -----
    total_solicitacoes = (
        db.session.query(Solicitacao)
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .count()
    )

    total_aprovadas = (
        db.session.query(Solicitacao)
        .filter(Solicitacao.status == "APROVADO")
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .count()
    )

    total_recusadas = (
        db.session.query(Solicitacao)
        .filter(Solicitacao.status == "NEGADO")
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .count()
    )

    total_analise = (
        db.session.query(Solicitacao)
        .filter(Solicitacao.status == "EM ANÁLISE")
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .count()
    )

    total_pendentes = (
        db.session.query(Solicitacao)
        .filter(Solicitacao.status == "PENDENTE")
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .count()
    )

    dados_regiao_raw = (
    db.session.query(Usuario.regiao, db.func.count(Solicitacao.id))
    .join(Usuario, Usuario.id == Solicitacao.usuario_id)
    .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
    .group_by(Usuario.regiao)
    .order_by(db.func.count(Solicitacao.id).desc())   # ← ORDEM DECRESCENTE
    .all()
 )

    dados_regiao = [tuple(row) for row in dados_regiao_raw]

    # ----- STATUS -----
    dados_status_raw = (
    db.session.query(Solicitacao.status, db.func.count(Solicitacao.id))
    .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
    .group_by(Solicitacao.status)
    .order_by(db.func.count(Solicitacao.id).desc())   # ← ORDEM DECRESCENTE
    .all()
)

    dados_status = [tuple(row) for row in dados_status_raw]

    # ----- FOCO -----
    dados_foco_raw = (
    db.session.query(Solicitacao.foco, db.func.count(Solicitacao.id))
    .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
    .group_by(Solicitacao.foco)
    .order_by(db.func.count(Solicitacao.id).desc())   # ← ORDEM DECRESCENTE
    .all()
)

    dados_foco = [tuple(row) for row in dados_foco_raw]

    # ----- TIPO VISITA -----
    dados_tipo_visita_raw = (
    db.session.query(Solicitacao.tipo_visita, db.func.count(Solicitacao.id))
    .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
    .group_by(Solicitacao.tipo_visita)
    .order_by(db.func.count(Solicitacao.id).desc())   # ← ORDEM DECRESCENTE
    .all()
)

    dados_tipo_visita = [tuple(row) for row in dados_tipo_visita_raw]

    # ----- ALTURA DE VOO -----
    dados_altura_voo_raw = (
    db.session.query(Solicitacao.altura_voo, db.func.count(Solicitacao.id))
    .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
    .group_by(Solicitacao.altura_voo)
    .order_by(db.func.count(Solicitacao.id).desc())   # ← ORDEM DECRESCENTE
    .all()
)

    dados_altura_voo = [tuple(row) for row in dados_altura_voo_raw]

    # ----- SOLICITAÇÕES POR UNIDADE (UVIS) - usa Usuario.nome_uvis e filtra tipo_usuario == 'uvis' -----
    dados_unidade_raw = (
        db.session.query(Usuario.nome_uvis, db.func.count(Solicitacao.id))
        .join(Usuario, Usuario.id == Solicitacao.usuario_id)
        .filter(Usuario.tipo_usuario == 'uvis')
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .group_by(Usuario.nome_uvis)
        .order_by(db.func.count(Solicitacao.id).desc())
        .all()
    )
    dados_unidade = [tuple(row) for row in dados_unidade_raw]

    # ----- já temos dados_mensais acima -----

    # ----- RETORNO -----
    return render_template(
        'relatorios.html',
        total_solicitacoes=total_solicitacoes,
        total_aprovadas=total_aprovadas,
        total_recusadas=total_recusadas,
        total_analise=total_analise,
        total_pendentes=total_pendentes,
        dados_regiao=dados_regiao,
        dados_status=dados_status,
        dados_foco=dados_foco,
        dados_tipo_visita=dados_tipo_visita,
        dados_altura_voo=dados_altura_voo,
        dados_unidade=dados_unidade,
        dados_mensais=dados_mensais,
        mes_selecionado=mes_atual,
        ano_selecionado=ano_atual,
        anos_disponiveis=anos_disponiveis
    )

# imports necessários (adicione no topo do arquivo se preferir)
import tempfile
from collections import Counter
from datetime import datetime
from flask import request, send_file

# reportlab (PDF)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

# openpyxl (Excel)
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# ---------------------------
# ROTA: EXPORTAR PDF (Tema Azul Moderno)
# ---------------------------
@bp.route('/admin/exportar_relatorio_pdf')
def exportar_relatorio_pdf():
    # filtros
    mes = int(request.args.get('mes', datetime.now().month))
    ano = int(request.args.get('ano', datetime.now().year))
    filtro_data = f"{ano}-{mes:02d}"

    # --- Buscas (mesmo padrão dos relatórios) ---
    # Registros com join para pegar dados do Usuario
    query_results = (
        db.session.query(Solicitacao, Usuario)
        .join(Usuario, Usuario.id == Solicitacao.usuario_id)
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .order_by(Solicitacao.data_criacao.desc())
        .all()
    )

    # Totais
    total_solicitacoes = len(query_results)
    total_aprovadas = sum(1 for s, u in query_results if s.status == "APROVADO")
    total_recusadas = sum(1 for s, u in query_results if s.status == "NEGADO")
    total_analise = sum(1 for s, u in query_results if s.status == "EM ANÁLISE")
    total_pendentes = sum(1 for s, u in query_results if s.status == "PENDENTE")

    # Dados por região
    dados_regiao_raw = (
        db.session.query(Usuario.regiao, db.func.count(Solicitacao.id))
        .join(Usuario, Usuario.id == Solicitacao.usuario_id)
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .group_by(Usuario.regiao)
        .all()
    )
    dados_regiao = [(r or "Não informado", c) for r, c in dados_regiao_raw]

    # Dados por status
    dados_status_raw = (
        db.session.query(Solicitacao.status, db.func.count(Solicitacao.id))
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .group_by(Solicitacao.status)
        .all()
    )
    dados_status = [(s or "Não informado", c) for s, c in dados_status_raw]

    # Dados por foco
    dados_foco_raw = (
        db.session.query(Solicitacao.foco, db.func.count(Solicitacao.id))
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .group_by(Solicitacao.foco)
        .all()
    )
    dados_foco = [(f or "Não informado", c) for f, c in dados_foco_raw]

    # Tipo de visita
    dados_tipo_visita_raw = (
        db.session.query(Solicitacao.tipo_visita, db.func.count(Solicitacao.id))
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .group_by(Solicitacao.tipo_visita)
        .all()
    )
    dados_tipo_visita = [(t or "Não informado", c) for t, c in dados_tipo_visita_raw]

    # Altura de voo
    dados_altura_raw = (
        db.session.query(Solicitacao.altura_voo, db.func.count(Solicitacao.id))
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .group_by(Solicitacao.altura_voo)
        .all()
    )
    dados_altura_voo = [(a or "Não informado", c) for a, c in dados_altura_raw]

    # Unidades (UVIS)
    dados_unidade_raw = (
        db.session.query(Usuario.nome_uvis, db.func.count(Solicitacao.id))
        .join(Usuario, Usuario.id == Solicitacao.usuario_id)
        .filter(Usuario.tipo_usuario == 'uvis')
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .group_by(Usuario.nome_uvis)
        .order_by(db.func.count(Solicitacao.id).desc())
        .all()
    )
    dados_unidade = [(u or "Não informado", c) for u, c in dados_unidade_raw]

    # Histórico mensal (todos os meses)
    dados_mensais_raw = (
        db.session.query(
            db.func.strftime('%Y-%m', Solicitacao.data_criacao).label('mes'),
            db.func.count(Solicitacao.id)
        )
        .group_by('mes')
        .order_by('mes')
        .all()
    )
    dados_mensais = [(m, c) for m, c in dados_mensais_raw]

    # --- Montar PDF estilizado (Tema Azul) ---
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    caminho_pdf = tmp.name
    tmp.close()

    doc = SimpleDocTemplate(caminho_pdf, pagesize=A4,
                            leftMargin=16*mm, rightMargin=16*mm,
                            topMargin=16*mm, bottomMargin=16*mm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', parent=styles['Title'], fontSize=18, alignment=1, spaceAfter=6)
    section_h = ParagraphStyle('sec', parent=styles['Heading3'], fontSize=12, spaceAfter=6)
    normal = styles['Normal']
    small = ParagraphStyle('small', parent=styles['BodyText'], fontSize=9, textColor=colors.HexColor('#555'))

    story = []

    # Header
    story.append(Paragraph(f"Relatório Mensal — {mes:02d}/{ano}", title_style))
    story.append(Paragraph("Sistema de Gestão de Solicitações", small))
    story.append(Spacer(1, 6))

    # Decorative bar
    story.append(Table([['']], colWidths=[170*mm], style=[('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0d6efd')), ('LINEBELOW', (0,0), (-1,-1), 0, colors.white)], hAlign='LEFT'))
    story.append(Spacer(1, 10))

    # SUMMARY BOX
    resumo = [
        ['Métrica', 'Quantidade'],
        ['Total de Solicitações', str(total_solicitacoes)],
        ['Aprovadas', str(total_aprovadas)],
        ['Recusadas', str(total_recusadas)],
        ['Em Análise', str(total_analise)],
        ['Pendentes', str(total_pendentes)]
    ]
    t_resumo = Table(resumo, colWidths=[110*mm, 50*mm])
    t_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(t_resumo)
    story.append(Spacer(1, 12))

    # SECTION: Regiões
    story.append(Paragraph("Solicitações por Região", section_h))
    rows = [['Região', 'Total']] + [[r, str(c)] for r, c in dados_regiao]
    tbl = Table(rows, colWidths=[110*mm, 50*mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 10))

    # SECTION: Status
    story.append(Paragraph("Status Detalhado", section_h))
    rows = [['Status', 'Total']] + [[s, str(c)] for s, c in dados_status]
    t_status = Table(rows, colWidths=[110*mm, 50*mm])
    t_status.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
    ]))
    story.append(t_status)
    story.append(Spacer(1, 10))

    # SECTION: Foco / Tipo / Altura
    story.append(Paragraph("Solicitações por Foco", section_h))
    rows = [['Foco', 'Total']] + [[f, str(c)] for f, c in dados_foco]
    story.append(Table(rows, colWidths=[110*mm, 50*mm], style=[
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
    ]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Solicitações por Tipo de Visita", section_h))
    rows = [['Tipo de Visita', 'Total']] + [[t, str(c)] for t, c in dados_tipo_visita]
    story.append(Table(rows, colWidths=[110*mm, 50*mm], style=[
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
    ]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Solicitações por Altura de Voo", section_h))
    rows = [['Altura (m)', 'Total']] + [[str(a), str(c)] for a, c in dados_altura_voo]
    story.append(Table(rows, colWidths=[110*mm, 50*mm], style=[
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
    ]))
    story.append(Spacer(1, 10))

    # SECTION: UVIS
    story.append(Paragraph("Solicitações por Unidade (UVIS) — Top", section_h))
    rows = [['Unidade', 'Total']] + [[u, str(c)] for u, c in dados_unidade]
    story.append(Table(rows, colWidths=[110*mm, 50*mm], style=[
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
    ]))
    story.append(Spacer(1, 10))

    # SECTION: Histórico Mensal (pequeno)
    story.append(Paragraph("Histórico Mensal (Total por Mês)", section_h))
    rows = [['Mês', 'Total']] + [[m, str(c)] for m, c in dados_mensais]
    story.append(Table(rows, colWidths=[70*mm, 40*mm], style=[
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
    ]))
    story.append(Spacer(1, 12))

    # SECTION: Registros Detalhados (lista)
    story.append(PageBreak())
    story.append(Paragraph("Registros Detalhados", ParagraphStyle('h', parent=styles['Heading2'], fontSize=14)))
    story.append(Spacer(1, 6))

    # Cabeçalho da tabela detalhada
    registros_header = ['Data', 'Hora', 'Unidade', 'Protocolo', 'Status', 'Região', 'Foco', 'Tipo Visita', 'Observação']
    registros_rows = [registros_header]

    for s, u in query_results:
        # data/hora safe formatting
        data_str = ''
        try:
            if getattr(s, 'data_agendamento', None):
                data_str = s.data_agendamento.strftime("%d/%m/%Y") if hasattr(s.data_agendamento, 'strftime') else str(s.data_agendamento)
            else:
                data_str = s.data_criacao.strftime("%d/%m/%Y") if hasattr(s.data_criacao, 'strftime') else str(s.data_criacao)
        except:
            data_str = str(getattr(s, 'data_agendamento', '') or getattr(s, 'data_criacao', ''))

        hora = getattr(s, 'hora_agendamento', '')
        hora_str = hora.strftime("%H:%M") if hasattr(hora, 'strftime') else str(hora or '')

        unidade = getattr(u, 'nome_uvis', '') or "Não informado"
        protocolo = getattr(s, 'protocolo', '') or ''
        status = getattr(s, 'status', '') or ''
        regiao = getattr(u, 'regiao', '') or ''
        foco = getattr(s, 'foco', '') or ''
        tipo_visita = getattr(s, 'tipo_visita', '') or ''
        obs = getattr(s, 'observacao', '') or ''

        registros_rows.append([data_str, hora_str, unidade, protocolo, status, regiao, foco, tipo_visita, obs])

    # tabela detalhada (pode quebrar em várias páginas automaticamente)
    tbl_det = Table(registros_rows, repeatRows=1,
                    colWidths=[18*mm, 14*mm, 35*mm, 26*mm, 22*mm, 28*mm, 28*mm, 30*mm, 45*mm])
    tbl_det.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fbfdff')]),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))

    story.append(tbl_det)

    # rodapé / gerado em
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", small))

    # build
    doc.build(story)

    return send_file(
        caminho_pdf,
        as_attachment=True,
        download_name=f"relatorio_SGSV_{ano}_{mes:02d}.pdf",
        mimetype="application/pdf"
    )

@bp.route('/admin/exportar_relatorio_excel')
def exportar_relatorio_excel():
    # IMPORTS necessários dentro da função
    from datetime import datetime
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    # filtros de mês/ano (agora datetime já está disponível)
    mes = request.args.get('mes', datetime.now().month, type=int)
    ano = request.args.get('ano', datetime.now().year, type=int)
    filtro_data = f"{ano}-{mes:02d}"

    # IMPORTANTE: JOIN entre Solicitacao e Usuario
    dados = (
        db.session.query(
            Solicitacao.id,
            Solicitacao.data_criacao,
            Solicitacao.status,
            Solicitacao.foco,
            Solicitacao.tipo_visita,
            Solicitacao.altura_voo,
            Solicitacao.data_agendamento,
            Solicitacao.hora_agendamento,
            Solicitacao.cep,
            Solicitacao.logradouro,
            Solicitacao.numero,
            Solicitacao.bairro,
            Solicitacao.cidade,
            Solicitacao.uf,
            Solicitacao.latitude,
            Solicitacao.longitude,
            Usuario.nome_uvis,
            Usuario.regiao
        )
        .join(Usuario, Usuario.id == Solicitacao.usuario_id)
        .filter(db.func.strftime('%Y-%m', Solicitacao.data_criacao) == filtro_data)
        .all()
    )

    # Criar arquivo Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Relatório"

    # Cabeçalho
    colunas = [
        "ID", "Status", "Foco", "Tipo Visita", "Altura Voo",
        "Data Agendamento", "Hora Agendamento",
        "CEP", "Logradouro", "Número", "Bairro", "Cidade", "UF",
        "Latitude", "Longitude", "UVIS", "Região"
    ]

    # Estilos
    header_fill = PatternFill(start_color="1E90FF", end_color="1E90FF", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    center = Alignment(horizontal="center", vertical="center")
    thin = Side(style='thin', color="000000")
    thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)
    zebra1 = PatternFill(start_color="FFFFFFFF", end_color="FFFFFFFF", fill_type="solid")  # white
    zebra2 = PatternFill(start_color="FFF7FBFF", end_color="FFF7FBFF", fill_type="solid")  # very light blue

    # Escrita do cabeçalho
    for col_num, col_name in enumerate(colunas, 1):
        cell = ws.cell(row=1, column=col_num, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = thin_border

    # Preenchimento das linhas com formatação de data/hora
    for row_num, row in enumerate(dados, 2):

        # ---- FORMATAR DATAS ----
        data_criacao_fmt = ""
        if row.data_criacao:
            try:
                # pode ser datetime
                data_criacao_fmt = row.data_criacao.strftime("%d/%m/%Y")
            except:
                # fallback para string
                data_criacao_fmt = str(row.data_criacao)

        data_agendamento_fmt = ""
        if row.data_agendamento:
            try:
                data_agendamento_fmt = row.data_agendamento.strftime("%d/%m/%Y")
            except:
                data_agendamento_fmt = str(row.data_agendamento)

        # ---- FORMATAR HORA ----
        hora_agendamento_fmt = ""
        if row.hora_agendamento:
            try:
                hora_agendamento_fmt = row.hora_agendamento.strftime("%H:%M")
            except:
                hora_agendamento_fmt = str(row.hora_agendamento)

        # ---- PREENCHER LINHAS ----
        values = [
            row.id,            
            row.status,
            row.foco,
            row.tipo_visita,
            row.altura_voo,
            data_agendamento_fmt,
            hora_agendamento_fmt,
            row.cep,
            row.logradouro,
            row.numero,
            row.bairro,
            row.cidade,
            row.uf,
            row.latitude,
            row.longitude,
            row.nome_uvis,
            row.regiao
        ]

        for col_index, value in enumerate(values, 1):
            cell = ws.cell(row=row_num, column=col_index, value=value)
            # borda e alinhamento
            cell.border = thin_border
            if col_index in (1, 3, 6, 8, 15, 16):  # id/status/altura/hora/lat/lon centralizados
                cell.alignment = center
            else:
                cell.alignment = Alignment(vertical="top", horizontal="left")

        # zebra stripes
        fill = zebra1 if (row_num % 2 == 0) else zebra2
        for col_index in range(1, len(colunas) + 1):
            ws.cell(row=row_num, column=col_index).fill = fill

    # Ajustar largura das colunas automaticamente (estimativa)
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if cell.value is not None:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        ws.column_dimensions[column].width = max(10, min(max_length + 2, 60))

    # Congelar cabeçalho e ativar filtro
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(colunas))}1"

    # Gerar arquivo em memória
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    nome_arquivo = f"relatorio_SGSV_{ano}_{mes:02d}.xlsx"

    return send_file(
        output,
        download_name=nome_arquivo,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
