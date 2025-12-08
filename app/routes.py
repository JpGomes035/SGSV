from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import Usuario, Solicitacao
from sqlalchemy.exc import IntegrityError # Importando para tratar erros no salvamento

print("--- ROTAS CARREGADAS COM SUCESSO ---")

bp = Blueprint('main', __name__)

# --- Context Processor: Simula o 'current_user' para o HTML ---
@bp.context_processor
def inject_user():
    class MockUser:
        is_authenticated = 'user_id' in session
        name = session.get('user_nome')
        id = session.get('user_id')
        role = session.get('user_tipo')
    return dict(current_user=MockUser())

# --- DASHBOARD UVIS (Visão da Unidade) ---
@bp.route('/')
def dashboard():
    # 1. Login obrigatório
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    # 2. Se for admin, redireciona para o painel de admin
    if session.get('user_tipo') == 'admin':
        return redirect(url_for('main.admin_dashboard'))

    # 3. Busca apenas solicitações do próprio usuário logado
    
    # GARANTIA: Converte para INT
    try:
        user_id = int(session.get('user_id')) 
    except (ValueError, TypeError):
        session.clear()
        flash('Sessão Inválida. Por favor, faça login novamente.', 'warning')
        return redirect(url_for('main.login'))
    
    # Consulta ao banco
    query = Solicitacao.query.filter_by(usuario_id=user_id).order_by(Solicitacao.data_criacao.desc())
    
    # --- DEBUG BRUTAL (OLHE O TERMINAL) ---
    print("\n===============================")
    print(f"DEBUG: USUÁRIO LOGADO ID (SESSÃO): {user_id}")
    print(f"DEBUG: FILTRO SQL A SER EXECUTADO: {query.statement.compile(compile_kwargs={'literal_binds': True})}")
    print("===============================\n")
    # -------------------------------------
    
    lista_solicitacoes = query.all()
    
    return render_template('dashboard.html', nome=session.get('user_nome'), solicitacoes=lista_solicitacoes)

# --- PAINEL ADMIN (Visualizar Pedidos) ---
@bp.route('/admin')
def admin_dashboard():
    # Verifica se é admin mesmo
    if 'user_id' not in session or session.get('user_tipo') != 'admin':
        return redirect(url_for('main.login'))

    # Busca TODOS os pedidos do banco (para o admin ver tudo)
    todos_pedidos = Solicitacao.query.order_by(Solicitacao.data_criacao.desc()).all()
    
    return render_template('admin.html', pedidos=todos_pedidos)

# --- ROTA DE ATUALIZAÇÃO (Salvar dados do Admin) ---
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
    flash(f'Pedido atualizado com sucesso!', 'success')
    
    return redirect(url_for('main.admin_dashboard'))

# --- NOVO PEDIDO (Cadastro da UVIS) ---
@bp.route('/novo_cadastro', methods=['GET', 'POST'], endpoint='novo')
def novo():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        try:
            # Garante que o ID da sessão está limpo e é um inteiro
            user_id_int = int(session['user_id'])

            nova_solicitacao = Solicitacao(
                data_agendamento=request.form.get('data'),
                hora_agendamento=request.form.get('hora'),
                endereco=request.form.get('endereco'),
                foco=request.form.get('foco'),
                usuario_id=user_id_int, # Usa o ID inteiro garantido
                status='EM ANÁLISE'
            )
            db.session.add(nova_solicitacao)
            db.session.commit()
            
            # --- DEBUG EXTRA (OLHE O TERMINAL) ---
            print(f"SALVAMENTO: Pedido salvo com sucesso! ID do criador: {user_id_int}")
            # -----------------------------------
            
            flash('Pedido enviado para análise!', 'success')
            return redirect(url_for('main.dashboard'))
        except IntegrityError:
            db.session.rollback()
            flash("Erro de integridade no banco de dados. Tente fazer login novamente.", "danger")
        except Exception as e:
            flash(f"Erro ao salvar: {e}", "danger")

    return render_template('cadastro.html')

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
            # SALVA ID como INTEIRO para evitar conflito com o banco
            session['user_id'] = int(user.id)
            session['user_nome'] = user.nome_uvis
            session['user_tipo'] = user.tipo_usuario
            
            if user.tipo_usuario == 'admin':
                return redirect(url_for('main.admin_dashboard'))
            return redirect(url_for('main.dashboard'))
        else:
            flash('Login incorreto.', 'danger')

    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))