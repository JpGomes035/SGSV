from app import create_app, db
from app.models import Usuario, Solicitacao

app = create_app()

def verificar_banco():
    """
    Roda ao iniciar. 
    Cria e garante que todos os usuários de teste estão no banco.
    """
    print(">>> Iniciando verificação do banco de dados...")
    try:
        with app.app_context():
            db.create_all()
            
            # --- 1. GARANTE ADMIN ---
            admin = Usuario.query.filter_by(login='admin').first()
            if not admin:
                print("--- Criando usuário Admin... ---")
                admin = Usuario(
                    nome_uvis="Administrador", 
                    regiao="CENTRAL", 
                    codigo_setor="00",
                    login="admin",
                    tipo_usuario="admin"
                )
                admin.set_senha("admin123")
                db.session.add(admin)
            else:
                if admin.tipo_usuario != 'admin':
                    admin.tipo_usuario = 'admin'
                print(f"--- Usuário Admin encontrado (ID: {admin.id}) ---")


            # --- 2. GARANTE LAPA ---
            lapa = Usuario.query.filter_by(login='lapa').first()
            if not lapa:
                print("--- Criando usuário UVIS Lapa... ---")
                lapa = Usuario(
                    nome_uvis="UVIS Lapa/Pinheiros", 
                    regiao="OESTE", 
                    codigo_setor="90",
                    login="lapa",
                    tipo_usuario="uvis"
                )
                lapa.set_senha("1234")
                db.session.add(lapa)
            else:
                print(f"--- Usuário Lapa encontrado (ID: {lapa.id}) ---")
            
            
            # --- 3. GARANTE NOVO USUÁRIO DE TESTE (teste) ---
            teste = Usuario.query.filter_by(login='teste').first()
            if not teste:
                print("--- Criando novo usuário de TESTE (teste)... ---")
                teste = Usuario(
                    nome_uvis="UVIS Teste QA", 
                    regiao="SUL", 
                    codigo_setor="10",
                    login="teste",
                    tipo_usuario="uvis"
                )
                teste.set_senha("1234")
                db.session.add(teste)
            else:
                print(f"--- Usuário Teste encontrado (ID: {teste.id}) ---")


            db.session.commit()
            print(">>> Banco de dados verificado com sucesso!")
            
            
            # --- CUIDADO: Cria pedido de teste para o TESTE (se necessário)
            # Vamos garantir que pelo menos o 'teste' tem um pedido para testar a visualização
            if teste and not Solicitacao.query.filter_by(usuario_id=teste.id).first():
                print("--- Criando pedido de teste para o novo usuário 'teste'... ---")
                pedido = Solicitacao(
                    data_agendamento="2026-01-01",
                    hora_agendamento="10:00",
                    endereco="Rua Teste Funcional, 999",
                    foco="Imóvel Abandonado",
                    usuario_id=teste.id,
                    status="EM ANÁLISE"
                )
                db.session.add(pedido)
                db.session.commit()


    except Exception as e:
        print(f"!!! ERRO FATAL NA VERIFICAÇÃO DO BANCO: {e}")
        # AQUI VAI DAR ERRO se você ainda tem um pedido de teste ligado ao Lapa
        # Mas não tem problema, o servidor vai tentar iniciar.

if __name__ == "__main__":
    verificar_banco()
    print(">>> INICIANDO SERVIDOR FLASK...")
    app.run(debug=True)