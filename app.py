from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import qrcode
from io import BytesIO
import base64
import requests
import json
from flask_migrate import Migrate

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///production_pointer.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
# ========== MODELOS DE BANCO DE DADOS ==========

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    codigo_qr = db.Column(db.String(100), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default='operador')
    setor = db.Column(db.String(50))
    ativo = db.Column(db.Boolean, default=True)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

class Maquina(db.Model):
    __tablename__ = 'maquinas'
    id = db.Column(db.Integer, primary_key=True)
    codigo_qr = db.Column(db.String(100), unique=True, nullable=False)
    codigo = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    setor = db.Column(db.String(50), nullable=False)
    tipo_maquina = db.Column(db.String(50))
    status = db.Column(db.String(20), default='parada')
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    op_atual = db.relationship('OrdemProducao', backref='maquina_atual_rel', lazy=True, 
                               foreign_keys='OrdemProducao.maquina_atual')

class OrdemProducao(db.Model):
    __tablename__ = 'ordens_producao'
    id = db.Column(db.Integer, primary_key=True)
    op = db.Column(db.Integer, unique=True, nullable=False)
    produto = db.Column(db.String(50), nullable=False)
    narrativa = db.Column(db.Text, nullable=False)
    grupo = db.Column(db.String(20))
    qtde_programado = db.Column(db.Float, nullable=False)
    qtde_carregado = db.Column(db.Float, nullable=False)
    qtde_produzida = db.Column(db.Float, default=0)
    unidade_medida = db.Column(db.String(5), default='M')
    estagio_atual = db.Column(db.String(50))
    estagio_posicao = db.Column(db.String(50))
    status_op = db.Column(db.String(20), default='pendente')
    maquina_atual = db.Column(db.Integer, db.ForeignKey('maquinas.id'))
    data_importacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_inicio = db.Column(db.DateTime)
    data_termino = db.Column(db.DateTime)
    sincronizado_em = db.Column(db.DateTime)
    observacao = db.Column(db.Text)
    origem_api = db.Column(db.Boolean, default=False)
    
    # Relacionamentos
    apontamentos = db.relationship('Apontamento', backref='op_rel', lazy=True)

class Apontamento(db.Model):
    __tablename__ = 'apontamentos'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    maquina_id = db.Column(db.Integer, db.ForeignKey('maquinas.id'), nullable=False)
    op_id = db.Column(db.Integer, db.ForeignKey('ordens_producao.id'), nullable=False)
    data_hora_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    data_hora_fim = db.Column(db.DateTime)
    metros_processados = db.Column(db.Float, nullable=False)
    observacao = db.Column(db.Text)
    status_apontamento = db.Column(db.String(20), default='em_andamento')
    tipo_apontamento = db.Column(db.String(20), default='producao')
    
    # Relacionamentos
    usuario = db.relationship('Usuario', backref='apontamentos')
    maquina = db.relationship('Maquina', backref='apontamentos')
    op = db.relationship('OrdemProducao', backref='apontamentos_rel')

class MotivoParada(db.Model):
    __tablename__ = 'motivos_parada'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    descricao = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    cor = db.Column(db.String(20))
    requer_justificativa = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    ordem_exibicao = db.Column(db.Integer, default=0)

class ParadaMaquina(db.Model):
    __tablename__ = 'paradas_maquina'
    id = db.Column(db.Integer, primary_key=True)
    apontamento_id = db.Column(db.Integer, db.ForeignKey('apontamentos.id'))
    maquina_id = db.Column(db.Integer, db.ForeignKey('maquinas.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    motivo_id = db.Column(db.Integer, db.ForeignKey('motivos_parada.id'))
    motivo_personalizado = db.Column(db.String(100))
    data_hora_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    data_hora_fim = db.Column(db.DateTime)
    duracao_minutos = db.Column(db.Integer)
    justificativa = db.Column(db.Text)
    categoria = db.Column(db.String(50))

class LogSincronizacao(db.Model):
    __tablename__ = 'log_sincronizacao'
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)
    data_execucao = db.Column(db.DateTime, default=datetime.utcnow)
    registros_processados = db.Column(db.Integer, default=0)
    registros_novos = db.Column(db.Integer, default=0)
    registros_atualizados = db.Column(db.Integer, default=0)
    duracao_segundos = db.Column(db.Float)
    status = db.Column(db.String(20))
    mensagem = db.Column(db.Text)
    detalhes = db.Column(db.Text)


# ========== CONTEXT PROCESSOR ==========
@app.context_processor
def inject_datetime():
    """Injeta datetime e now em todos os templates"""
    return dict(datetime=datetime, now=datetime.utcnow)


# ========== CLIENTE API SYSTÊXTIL ==========

class SystextilAPIClient:
    def __init__(self):
        self.base_url = os.getenv('SYSTEXTIL_API_BASE_URL', 'https://promoda.systextil.com.br/apexbd/erp')
        self.token_url = os.getenv('SYSTEXTIL_TOKEN_URL', 'https://promoda.systextil.com.br/apexbd/erp/oauth/token')
        self.client_id = os.getenv('SYSTEXTIL_CLIENT_ID', 'vM_z3JIQSR7fMml912X4Wg..')
        self.client_secret = os.getenv('SYSTEXTIL_CLIENT_SECRET', 'v6CnE7I6vI6JkYn7DOIQ6A..')
        self.access_token = None
        self.token_expiry = None
    
    def _get_access_token(self):
        """Obtém token OAuth2 usando client credentials"""
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_encoded = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {auth_encoded}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'client_credentials'
        }
        
        try:
            response = requests.post(self.token_url, headers=headers, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                self.token_expiry = datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 3600))
                return True
            else:
                raise Exception(f"Erro ao obter token: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Falha na comunicação com API de autenticação: {str(e)}")
    
    def _ensure_token_valid(self):
        """Verifica se o token é válido e renova se necessário"""
        if not self.access_token or not self.token_expiry or datetime.utcnow() >= self.token_expiry:
            self._get_access_token()
    
    def get_production_orders(self, ultima_sincronizacao=None):
        """Busca ordens de produção do endpoint api_pcp_ops"""
        self._ensure_token_valid()
        
        endpoint = f"{self.base_url}/systextil-intg-plm/api_pcp_ops"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        params = {}
        if ultima_sincronizacao:
            # Formatar data para a API (se necessário)
            params['data_inicio'] = ultima_sincronizacao.strftime('%Y-%m-%d')
        
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                
                # Processa os dados conforme estrutura fornecida
                processed_orders = []
                for item in data.get('items', []):
                    order = {
                        'op': item['OP'],
                        'produto': item['PRODUTO'],
                        'narrativa': item['NARRATIVA'],
                        'grupo': item['GRUPO'],
                        'qtde_programado': item['QTDE_PROGRAMADO'],
                        'qtde_carregado': item['QTDE_CARREGADO'],
                        'qtde_produzida': item['QTDE_PRODUZIDA'],
                        'estagio_atual': item['ESTAGIO'],
                        'estagio_posicao': item['ESTAGIO_POSICAO'],
                        'maquina_op': item.get('MAQUINA_OP', ''),
                        'maquina_op_nome': item.get('MAQUINA_OP_NOME', ''),
                        'deposito_final': item.get('DEPOSITO_FINAL', ''),
                        'qualidade_tecido': item.get('QUALIDADE_TECIDO', ''),
                        'metros_1_qualidade': item.get('QTDE_METROS_1_QUALIDADE', 0),
                        'metros_2_qualidade': item.get('QTDE_METROS_2_QUALIDADE', 0),
                        'calculado_quebra': item.get('CALCULO_QUEBRA', 0),
                        'rolos_gerados': item.get('QTDE_ROLOS_GERADOS', 0),
                        'pecas_vinculadas': item.get('PECAS_VINCULADAS', ''),
                        'observacao': item.get('OBS', ''),
                        'periodo': item.get('PERIODO', 0),
                        'processo': item.get('PROCESSO', 0),
                        'unidade_medida': item.get('UM', 'M'),
                        'nivel': item.get('NIVEL', ''),
                        'subgrupo': item.get('SUB', ''),
                        'item': item.get('ITEM', '')
                    }
                    processed_orders.append(order)
                
                return processed_orders
            else:
                raise Exception(f"Erro API: {response.status_code} - {response.text}")
                
        except Exception as e:
            raise Exception(f"Falha na comunicação com API de OPs: {str(e)}")
    
    def sync_orders_to_database(self):
        """Sincroniza ordens da API para o banco local"""
        start_time = datetime.utcnow()
        
        try:
            # Buscar última sincronização bem-sucedida
            last_sync = LogSincronizacao.query.filter_by(
                tipo='ops', 
                status='sucesso'
            ).order_by(LogSincronizacao.data_execucao.desc()).first()
            
            ultima_sincronizacao = last_sync.data_execucao if last_sync else None
            
            # Buscar ordens da API
            orders = self.get_production_orders(ultima_sincronizacao)
            
            stats = {
                'total': len(orders),
                'novos': 0,
                'atualizados': 0,
                'erros': 0
            }
            
            for order_data in orders:
                try:
                    # Verificar se OP já existe
                    existing = OrdemProducao.query.filter_by(op=order_data['op']).first()
                    
                    if existing:
                        # Atualiza apenas se não estiver finalizada
                        if existing.status_op != 'finalizada':
                            # Atualiza campos
                            existing.qtde_produzida = order_data['qtde_produzida']
                            existing.estagio_atual = order_data['estagio_atual']
                            existing.estagio_posicao = order_data['estagio_posicao']
                            existing.maquina_atual = self._get_maquina_id_by_code(order_data['maquina_op'])
                            existing.sincronizado_em = datetime.utcnow()
                            existing.observacao = order_data['observacao']
                            stats['atualizados'] += 1
                    else:
                        # Cria nova OP
                        nova_op = OrdemProducao(
                            op=order_data['op'],
                            produto=order_data['produto'],
                            narrativa=order_data['narrativa'],
                            grupo=order_data['grupo'],
                            qtde_programado=order_data['qtde_programado'],
                            qtde_carregado=order_data['qtde_carregado'],
                            qtde_produzida=order_data['qtde_produzida'],
                            estagio_atual=order_data['estagio_atual'],
                            estagio_posicao=order_data['estagio_posicao'],
                            maquina_atual=self._get_maquina_id_by_code(order_data['maquina_op']),
                            status_op=self._determine_status(order_data['estagio_posicao']),
                            origem_api=True,
                            sincronizado_em=datetime.utcnow(),
                            observacao=order_data['observacao'],
                            unidade_medida=order_data['unidade_medida']
                        )
                        db.session.add(nova_op)
                        stats['novos'] += 1
                        
                except Exception as e:
                    stats['erros'] += 1
                    print(f"Erro processando OP {order_data.get('op', 'N/A')}: {e}")
            
            db.session.commit()
            
            # Log da sincronização
            duracao = (datetime.utcnow() - start_time).total_seconds()
            
            log = LogSincronizacao(
                tipo='ops',
                registros_processados=stats['total'],
                registros_novos=stats['novos'],
                registros_atualizados=stats['atualizados'],
                duracao_segundos=duracao,
                status='sucesso',
                mensagem=f"Sincronização realizada com sucesso. {stats['novos']} novos, {stats['atualizados']} atualizados."
            )
            
            db.session.add(log)
            db.session.commit()
            
            return {
                'success': True,
                'stats': stats,
                'message': f"Sincronização concluída: {stats['novos']} novas OPs, {stats['atualizados']} atualizadas"
            }
            
        except Exception as e:
            # Log do erro
            duracao = (datetime.utcnow() - start_time).total_seconds()
            
            log = LogSincronizacao(
                tipo='ops',
                registros_processados=0,
                duracao_segundos=duracao,
                status='erro',
                mensagem=str(e)
            )
            
            db.session.add(log)
            db.session.commit()
            
            return {
                'success': False,
                'message': f"Erro na sincronização: {str(e)}"
            }
    
    def _get_maquina_id_by_code(self, codigo_maquina):
        """Busca ID da máquina pelo código"""
        if not codigo_maquina:
            return None
        
        maquina = Maquina.query.filter_by(codigo=codigo_maquina).first()
        if maquina:
            return maquina.id
        
        return None
    
    def _determine_status(self, estagio_posicao):
        """Determina status da OP baseado no estágio"""
        if estagio_posicao == '99-Finalizado':
            return 'finalizada'
        elif estagio_posicao and estagio_posicao != '99-Finalizado':
            return 'em_andamento'
        return 'pendente'

# ========== FUNÇÕES AUXILIARES ==========

def generate_qr_code(text):
    """Gera QR Code e retorna como base64"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

def init_database():
    """Inicializa o banco de dados com dados de exemplo"""
    with app.app_context():
        db.create_all()
        
        # Verificar se já existem dados
        if Usuario.query.count() == 0:
            # Criar usuários de exemplo
            usuarios = [
                Usuario(codigo_qr='OPERADOR001', nome='João Silva', tipo='operador', setor='tingimento'),
                Usuario(codigo_qr='OPERADOR002', nome='Maria Santos', tipo='operador', setor='preparacao'),
                Usuario(codigo_qr='SUPERVISOR001', nome='Carlos Oliveira', tipo='supervisor', setor='produção'),
                Usuario(codigo_qr='ADMIN001', nome='Admin Sistema', tipo='admin'),
            ]
            
            for usuario in usuarios:
                db.session.add(usuario)
            
            # Criar máquinas de exemplo
            maquinas = [
                Maquina(codigo_qr='JIGGER01', codigo='TING.001.00001', nome='Jigger 1', setor='tingimento', tipo_maquina='jigger'),
                Maquina(codigo_qr='JIGGER02', codigo='TING.001.00002', nome='Jigger 2', setor='tingimento', tipo_maquina='jigger'),
                Maquina(codigo_qr='TURBO01', codigo='TING.002.00001', nome='Turbo 1', setor='tingimento', tipo_maquina='turbo'),
                Maquina(codigo_qr='STORK01', codigo='EST.001.00001', nome='Stork 1', setor='estampagem', tipo_maquina='stork'),
            ]
            
            for maquina in maquinas:
                db.session.add(maquina)
            
            # Criar ordens de produção de exemplo
            ops = [
                OrdemProducao(
                    op=193,
                    produto='2.K1820.TIN.000051',
                    narrativa='TECIDO LENÇOL ELEGANCE 150FIOS TINTO AZUL',
                    grupo='K1820',
                    qtde_programado=3200,
                    qtde_carregado=3000,
                    qtde_produzida=1500,
                    estagio_atual='ACABAMENTO RAMA',
                    estagio_posicao='45',
                    status_op='em_andamento'
                ),
                OrdemProducao(
                    op=222,
                    produto='2.K1820.TIN.000052',
                    narrativa='TECIDO LENÇOL ELEGANCE 150FIOS BRANCO',
                    grupo='K1820',
                    qtde_programado=2800,
                    qtde_carregado=2500,
                    qtde_produzida=0,
                    estagio_atual='PREPARAÇÃO',
                    estagio_posicao='10',
                    status_op='pendente'
                ),
                OrdemProducao(
                    op=245,
                    produto='2.K1825.TIN.000067',
                    narrativa='TECIDO LENÇOL PREMIUM 200FIOS CINZA',
                    grupo='K1825',
                    qtde_programado=4000,
                    qtde_carregado=3800,
                    qtde_produzida=3800,
                    estagio_atual='FINALIZADO',
                    estagio_posicao='99',
                    status_op='finalizada'
                ),
            ]
            
            for op in ops:
                db.session.add(op)
            
            # Criar motivos de parada
            motivos = [
                MotivoParada(codigo='ENE001', descricao='Falta de energia', categoria='tecnica', cor='vermelho'),
                MotivoParada(codigo='GAS001', descricao='Falta de gás', categoria='tecnica', cor='vermelho'),
                MotivoParada(codigo='MAN001', descricao='Manutenção corretiva', categoria='tecnica', cor='laranja'),
                MotivoParada(codigo='MAN002', descricao='Manutenção preventiva', categoria='planejada', cor='amarelo'),
                MotivoParada(codigo='QUAL001', descricao='Aguardando qualidade', categoria='organizacional', cor='azul'),
                MotivoParada(codigo='MAT001', descricao='Falta de matéria-prima', categoria='logistica', cor='roxo'),
                MotivoParada(codigo='OPE001', descricao='Falta de operador', categoria='organizacional', cor='cinza'),
                MotivoParada(codigo='OUT001', descricao='Outros', categoria='diversos', cor='cinza', requer_justificativa=True),
            ]
            
            for motivo in motivos:
                db.session.add(motivo)
            
            db.session.commit()
            print("Banco de dados inicializado com dados de exemplo!")

# ========== ROTAS PRINCIPAIS ==========

@app.route('/')
def index():
    """Página inicial"""
    return render_template('index.html')

@app.route('/scanner')
def scanner():
    """Tela de scanner de QR Code"""
    return render_template('scanner.html')

@app.route('/scanner_maquina')
def scanner_maquina():
    """Scanner para máquina"""
    if 'usuario_id' not in session:
        return redirect('/')
    return render_template('scanner_maquina.html')

@app.route('/selecionar_op')
def selecionar_op():
    """Seleção de OP para a máquina"""
    if 'maquina_id' not in session:
        return redirect('/')
    
    maquina = Maquina.query.get(session['maquina_id'])
    ops = OrdemProducao.query.filter(
        OrdemProducao.status_op.in_(['pendente', 'pausado']),
        OrdemProducao.qtde_produzida < OrdemProducao.qtde_carregado
    ).order_by(OrdemProducao.op).all()
    
    return render_template('selecionar_op.html', ops=ops, maquina=maquina)

@app.route('/production')
def production():
    """Tela de apontamento de produção"""
    if 'usuario_id' not in session or 'maquina_id' not in session or 'op_id' not in session:
        return redirect('/')
    
    usuario = Usuario.query.get(session['usuario_id'])
    maquina = Maquina.query.get(session['maquina_id'])
    op = OrdemProducao.query.get(session['op_id'])
    
    if not usuario or not maquina or not op:
        return redirect('/')
    
    metros_disponiveis = op.qtde_carregado - op.qtde_produzida
    
    return render_template('production.html',
                         usuario=usuario,
                         maquina=maquina,
                         op=op,
                         metros_disponiveis=metros_disponiveis)

# ========== API ROUTES ==========

@app.route('/api/validate_qr', methods=['POST'])
def validate_qr():
    """Valida QR Code escaneado"""
    data = request.json
    qr_code = data.get('qr_code', '').strip()
    
    # Verificar se é usuário
    usuario = Usuario.query.filter_by(codigo_qr=qr_code, ativo=True).first()
    if usuario:
        session['usuario_id'] = usuario.id
        session['usuario_nome'] = usuario.nome
        session['usuario_tipo'] = usuario.tipo
        
        if usuario.tipo == 'operador':
            return jsonify({
                'success': True,
                'redirect': '/scanner_maquina',
                'usuario': {
                    'id': usuario.id,
                    'nome': usuario.nome,
                    'tipo': usuario.tipo
                }
            })
        else:
            return jsonify({
                'success': True,
                'redirect': '/admin/dashboard',
                'usuario': {
                    'id': usuario.id,
                    'nome': usuario.nome,
                    'tipo': usuario.tipo
                }
            })
    
    # Verificar se é máquina
    maquina = Maquina.query.filter_by(codigo_qr=qr_code).first()
    if maquina:
        session['maquina_id'] = maquina.id
        session['maquina_nome'] = maquina.nome
        
        op_ativa = OrdemProducao.query.filter_by(
            maquina_atual=maquina.id,
            status_op='em_andamento'
        ).first()
        
        if op_ativa:
            session['op_id'] = op_ativa.id
            return jsonify({
                'success': True,
                'redirect': '/production',
                'maquina': {
                    'id': maquina.id,
                    'nome': maquina.nome,
                    'status': maquina.status
                },
                'op_ativa': {
                    'id': op_ativa.id,
                    'op': op_ativa.op,
                    'produto': op_ativa.produto
                }
            })
        else:
            return jsonify({
                'success': True,
                'redirect': '/selecionar_op',
                'maquina': {
                    'id': maquina.id,
                    'nome': maquina.nome,
                    'status': maquina.status
                }
            })
    
    return jsonify({'success': False, 'message': 'QR Code não reconhecido'})

@app.route('/api/selecionar_op/<int:op_id>', methods=['POST'])
def selecionar_op_api(op_id):
    """Seleciona OP para produção"""
    if 'maquina_id' not in session:
        return jsonify({'success': False, 'message': 'Sessão inválida'})
    
    op = OrdemProducao.query.get(op_id)
    if not op:
        return jsonify({'success': False, 'message': 'OP não encontrada'})
    
    op.maquina_atual = session['maquina_id']
    op.status_op = 'em_andamento'
    if not op.data_inicio:
        op.data_inicio = datetime.utcnow()
    
    maquina = Maquina.query.get(session['maquina_id'])
    maquina.status = 'trabalhando'
    
    session['op_id'] = op.id
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'redirect': '/production',
        'op': {
            'id': op.id,
            'numero': op.op,
            'produto': op.produto
        }
    })

@app.route('/api/registrar_apontamento', methods=['POST'])
def registrar_apontamento():
    """Registra apontamento de produção"""
    data = request.json
    
    if 'usuario_id' not in session or 'maquina_id' not in session or 'op_id' not in session:
        return jsonify({'success': False, 'message': 'Sessão inválida'})
    
    try:
        apontamento = Apontamento(
            usuario_id=session['usuario_id'],
            maquina_id=session['maquina_id'],
            op_id=session['op_id'],
            metros_processados=float(data['metros_processados']),
            observacao=data.get('observacao', ''),
            data_hora_fim=datetime.utcnow(),
            status_apontamento='finalizado'
        )
        
        db.session.add(apontamento)
        
        op = OrdemProducao.query.get(session['op_id'])
        op.qtde_produzida += float(data['metros_processados'])
        
        if op.qtde_produzida >= op.qtde_carregado:
            op.status_op = 'finalizada'
            op.data_termino = datetime.utcnow()
            
            maquina = Maquina.query.get(session['maquina_id'])
            maquina.status = 'parada'
            
            session.pop('maquina_id', None)
            session.pop('op_id', None)
            redirect_url = '/scanner_maquina'
        else:
            redirect_url = '/production?continue=true'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Produção registrada com sucesso!',
            'redirect': redirect_url
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@app.route('/api/get_motivos_parada')
def get_motivos_parada():
    """Retorna lista de motivos de parada"""
    motivos = MotivoParada.query.filter_by(ativo=True).order_by(MotivoParada.ordem_exibicao).all()
    
    motivos_list = []
    for motivo in motivos:
        motivos_list.append({
            'id': motivo.id,
            'codigo': motivo.codigo,
            'descricao': motivo.descricao,
            'categoria': motivo.categoria,
            'cor': motivo.cor
        })
    
    return jsonify(motivos_list)

@app.route('/api/registrar_parada', methods=['POST'])
def registrar_parada():
    """Registra parada de máquina"""
    data = request.json
    
    if 'usuario_id' not in session or 'maquina_id' not in session:
        return jsonify({'success': False, 'message': 'Sessão inválida'})
    
    try:
        parada = ParadaMaquina(
            maquina_id=session['maquina_id'],
            usuario_id=session['usuario_id'],
            motivo_id=data.get('motivo_id'),
            motivo_personalizado=data.get('motivo_personalizado', ''),
            justificativa=data.get('justificativa', ''),
            categoria=data.get('categoria', 'nao_planejada'),
            data_hora_inicio=datetime.utcnow()
        )
        
        db.session.add(parada)
        
        maquina = Maquina.query.get(session['maquina_id'])
        maquina.status = 'parada'
        
        if 'op_id' in session:
            op = OrdemProducao.query.get(session['op_id'])
            if op and op.status_op == 'em_andamento':
                op.status_op = 'pausado'
        
        db.session.commit()
        
        session.pop('maquina_id', None)
        session.pop('op_id', None)
        
        return jsonify({
            'success': True,
            'message': 'Parada registrada com sucesso!',
            'redirect': '/'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

# ========== ADMIN ROUTES ==========

@app.route('/admin')
def admin_redirect():
    """Redireciona para o dashboard admin"""
    if session.get('usuario_tipo') != 'admin':
        return redirect('/')
    return redirect('/admin/dashboard')

@app.route('/admin/dashboard')
def admin_dashboard():
    """Dashboard administrativo"""
    if session.get('usuario_tipo') != 'admin':
        return redirect('/')
    
    # Estatísticas
    total_ops = OrdemProducao.query.count()
    ops_andamento = OrdemProducao.query.filter_by(status_op='em_andamento').count()
    ops_finalizadas = OrdemProducao.query.filter_by(status_op='finalizada').count()
    maquinas_ativas = Maquina.query.filter_by(status='trabalhando').count()
    total_maquinas = Maquina.query.count()
    
    # Últimos apontamentos
    ultimos_apontamentos = Apontamento.query.order_by(Apontamento.data_hora_inicio.desc()).limit(10).all()
    
    # Status das máquinas
    maquinas = Maquina.query.order_by(Maquina.setor, Maquina.nome).all()
    
    # Produção do dia
    hoje = datetime.utcnow().date()
    producao_hoje = db.session.query(
        db.func.sum(Apontamento.metros_processados)
    ).filter(
        db.func.date(Apontamento.data_hora_inicio) == hoje
    ).scalar() or 0
    
    # Contar usuários para o dashboard
    usuarios_com_qr = []
    usuarios = Usuario.query.all()
    for usuario in usuarios:
        qr_data = generate_qr_code(usuario.codigo_qr)
        usuarios_com_qr.append({
            'usuario': usuario,
            'qr_code': qr_data
        })
    
    return render_template('admin_dashboard.html',
                         total_ops=total_ops,
                         ops_andamento=ops_andamento,
                         ops_finalizadas=ops_finalizadas,
                         maquinas_ativas=maquinas_ativas,
                         total_maquinas=total_maquinas,
                         producao_hoje=producao_hoje,
                         ultimos_apontamentos=ultimos_apontamentos,
                         maquinas=maquinas,
                         usuarios_com_qr=usuarios_com_qr)

@app.route('/admin/setup')
def admin_setup():
    """Página de setup inicial"""
    return render_template('admin_setup.html')

@app.route('/admin/ops')
def admin_ops_page():
    """Página de gerenciamento de OPs"""
    if session.get('usuario_tipo') != 'admin':
        return redirect('/')
    
    ops = OrdemProducao.query.order_by(OrdemProducao.op.desc()).all()
    maquinas = Maquina.query.all()
    
    return render_template('admin_ops.html', ops=ops, maquinas=maquinas)

@app.route('/admin/maquinas')
def admin_maquinas_page():
    """Página de gerenciamento de máquinas"""
    if session.get('usuario_tipo') != 'admin':
        return redirect('/')
    
    maquinas = Maquina.query.order_by(Maquina.setor, Maquina.nome).all()
    
    maquinas_com_qr = []
    for maquina in maquinas:
        qr_data = generate_qr_code(maquina.codigo_qr)
        maquinas_com_qr.append({
            'maquina': maquina,
            'qr_code': qr_data
        })
    
    return render_template('admin_maquinas.html', maquinas_com_qr=maquinas_com_qr)

@app.route('/admin/usuarios')
def admin_usuarios_page():
    """Página de gerenciamento de usuários"""
    if session.get('usuario_tipo') != 'admin':
        return redirect('/')
    
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    
    usuarios_com_qr = []
    for usuario in usuarios:
        qr_data = generate_qr_code(usuario.codigo_qr)
        usuarios_com_qr.append({
            'usuario': usuario,
            'qr_code': qr_data
        })
    
    return render_template('admin_usuarios.html', usuarios_com_qr=usuarios_com_qr)

@app.route('/admin/motivos_parada')
def admin_motivos_parada_page():
    """Página de gerenciamento de motivos de parada"""
    if session.get('usuario_tipo') != 'admin':
        return redirect('/')
    
    motivos = MotivoParada.query.order_by(MotivoParada.categoria, MotivoParada.ordem_exibicao).all()
    
    return render_template('admin_motivos_parada.html', motivos=motivos)

@app.route('/admin/api_sync')
def admin_api_sync():
    """Página de sincronização com API"""
    if session.get('usuario_tipo') != 'admin':
        return redirect('/')
    
    # Últimas sincronizações
    logs = LogSincronizacao.query.order_by(LogSincronizacao.data_execucao.desc()).limit(10).all()
    
    # Estatísticas de sincronização
    total_sync = LogSincronizacao.query.filter_by(tipo='ops').count()
    sync_success = LogSincronizacao.query.filter_by(tipo='ops', status='sucesso').count()
    sync_error = LogSincronizacao.query.filter_by(tipo='ops', status='erro').count()
    
    # Última sincronização bem-sucedida
    last_success = LogSincronizacao.query.filter_by(
        tipo='ops', 
        status='sucesso'
    ).order_by(LogSincronizacao.data_execucao.desc()).first()
    
    # Configurações da API
    api_config = {
        'base_url': os.getenv('SYSTEXTIL_API_BASE_URL', 'Não configurado'),
        'client_id': os.getenv('SYSTEXTIL_CLIENT_ID', 'Não configurado')[:10] + '...' if os.getenv('SYSTEXTIL_CLIENT_ID') else 'Não configurado'
    }
    
    return render_template('admin_api_sync.html',
                         logs=logs,
                         total_sync=total_sync,
                         sync_success=sync_success,
                         sync_error=sync_error,
                         last_success=last_success,
                         api_config=api_config)

# ========== API PARA ADMIN ==========

@app.route('/api/admin/add_op', methods=['POST'])
def admin_add_op():
    """Adiciona nova OP manualmente"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    try:
        data = request.json
        
        nova_op = OrdemProducao(
            op=int(data['op']),
            produto=data['produto'],
            narrativa=data['narrativa'],
            grupo=data.get('grupo', ''),
            qtde_programado=float(data['qtde_programado']),
            qtde_carregado=float(data['qtde_carregado']),
            qtde_produzida=float(data.get('qtde_produzida', 0)),
            estagio_atual=data.get('estagio_atual', ''),
            estagio_posicao=data.get('estagio_posicao', ''),
            status_op=data.get('status_op', 'pendente'),
            unidade_medida=data.get('unidade_medida', 'M'),
            observacao=data.get('observacao', ''),
            origem_api=False
        )
        
        db.session.add(nova_op)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'OP adicionada com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@app.route('/api/admin/update_op/<int:op_id>', methods=['PUT'])
def update_op(op_id):
    """Atualiza uma OP existente"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    try:
        data = request.json
        
        op = OrdemProducao.query.get(op_id)
        if not op:
            return jsonify({'success': False, 'message': 'OP não encontrada'})
        
        # Verificar se número da OP foi alterado
        if 'op' in data and data['op'] != op.op:
            # Verificar se nova OP já existe
            existing = OrdemProducao.query.filter_by(op=data['op']).first()
            if existing and existing.id != op_id:
                return jsonify({'success': False, 'message': 'Já existe uma OP com este número'})
        
        # Atualizar campos
        if 'op' in data:
            op.op = data['op']
        if 'produto' in data:
            op.produto = data['produto']
        if 'narrativa' in data:
            op.narrativa = data['narrativa']
        if 'grupo' in data:
            op.grupo = data['grupo']
        if 'qtde_programado' in data:
            op.qtde_programado = data['qtde_programado']
        if 'qtde_carregado' in data:
            op.qtde_carregado = data['qtde_carregado']
        if 'qtde_produzida' in data:
            op.qtde_produzida = data['qtde_produzida']
        if 'unidade_medida' in data:
            op.unidade_medida = data['unidade_medida']
        if 'estagio_atual' in data:
            op.estagio_atual = data['estagio_atual']
        if 'estagio_posicao' in data:
            op.estagio_posicao = data['estagio_posicao']
        if 'status_op' in data:
            op.status_op = data['status_op']
        if 'maquina_atual' in data:
            op.maquina_atual = data['maquina_atual']
        if 'observacao' in data:
            op.observacao = data['observacao']
        
        # Atualizar datas conforme status
        if 'status_op' in data:
            if data['status_op'] == 'em_andamento' and not op.data_inicio:
                op.data_inicio = datetime.utcnow()
            elif data['status_op'] == 'finalizada' and not op.data_termino:
                op.data_termino = datetime.utcnow()
        
        op.sincronizado_em = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'OP atualizada com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@app.route('/api/admin/get_op/<int:op_id>')
def get_op(op_id):
    """Retorna dados de uma OP específica para edição"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    op = OrdemProducao.query.get(op_id)
    if not op:
        return jsonify({'success': False, 'message': 'OP não encontrada'})
    
    return jsonify({
        'success': True,
        'op': {
            'id': op.id,
            'op': op.op,
            'produto': op.produto,
            'narrativa': op.narrativa,
            'grupo': op.grupo,
            'qtde_programado': op.qtde_programado,
            'qtde_carregado': op.qtde_carregado,
            'qtde_produzida': op.qtde_produzida,
            'unidade_medida': op.unidade_medida,
            'estagio_atual': op.estagio_atual,
            'estagio_posicao': op.estagio_posicao,
            'status_op': op.status_op,
            'maquina_atual': op.maquina_atual,
            'observacao': op.observacao,
            'data_inicio': op.data_inicio.isoformat() if op.data_inicio else None,
            'data_termino': op.data_termino.isoformat() if op.data_termino else None,
            'data_importacao': op.data_importacao.isoformat() if op.data_importacao else None
        }
    })

@app.route('/api/admin/get_op_details/<int:op_id>')
def get_op_details(op_id):
    """Retorna detalhes completos de uma OP para visualização"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    op = OrdemProducao.query.get(op_id)
    if not op:
        return jsonify({'success': False, 'message': 'OP não encontrada'})
    
    maquina_nome = None
    if op.maquina_atual:
        maquina = Maquina.query.get(op.maquina_atual)
        if maquina:
            maquina_nome = maquina.nome
    
    return jsonify({
        'success': True,
        'op': {
            'id': op.id,
            'op': op.op,
            'produto': op.produto,
            'narrativa': op.narrativa,
            'grupo': op.grupo,
            'qtde_programado': float(op.qtde_programado),
            'qtde_carregado': float(op.qtde_carregado),
            'qtde_produzida': float(op.qtde_produzida),
            'unidade_medida': op.unidade_medida,
            'estagio_atual': op.estagio_atual,
            'estagio_posicao': op.estagio_posicao,
            'status_op': op.status_op,
            'maquina_atual': op.maquina_atual,
            'maquina_atual_nome': maquina_nome,
            'data_inicio': op.data_inicio.isoformat() if op.data_inicio else None,
            'data_termino': op.data_termino.isoformat() if op.data_termino else None,
            'data_importacao': op.data_importacao.isoformat() if op.data_importacao else None,
            'sincronizado_em': op.sincronizado_em.isoformat() if op.sincronizado_em else None,
            'observacao': op.observacao
        }
    })

@app.route('/api/admin/start_op/<int:op_id>', methods=['POST'])
def start_op(op_id):
    """Inicia produção de uma OP"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    try:
        op = OrdemProducao.query.get(op_id)
        if not op:
            return jsonify({'success': False, 'message': 'OP não encontrada'})
        
        op.status_op = 'em_andamento'
        if not op.data_inicio:
            op.data_inicio = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'OP iniciada com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@app.route('/api/admin/pause_op/<int:op_id>', methods=['POST'])
def pause_op(op_id):
    """Pausa produção de uma OP"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    try:
        op = OrdemProducao.query.get(op_id)
        if not op:
            return jsonify({'success': False, 'message': 'OP não encontrada'})
        
        op.status_op = 'pausado'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'OP pausada com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@app.route('/api/admin/resume_op/<int:op_id>', methods=['POST'])
def resume_op(op_id):
    """Retoma produção de uma OP"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    try:
        op = OrdemProducao.query.get(op_id)
        if not op:
            return jsonify({'success': False, 'message': 'OP não encontrada'})
        
        op.status_op = 'em_andamento'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'OP retomada com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@app.route('/api/admin/delete_op/<int:op_id>', methods=['DELETE'])
def delete_op(op_id):
    """Exclui uma OP"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    try:
        op = OrdemProducao.query.get(op_id)
        if not op:
            return jsonify({'success': False, 'message': 'OP não encontrada'})
        
        # Verificar se há apontamentos associados
        apontamentos = Apontamento.query.filter_by(op_id=op_id).count()
        if apontamentos > 0:
            return jsonify({
                'success': False, 
                'message': f'Não é possível excluir esta OP. Existem {apontamentos} apontamentos associados.'
            })
        
        db.session.delete(op)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'OP excluída com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@app.route('/api/admin/all_ops')
def get_all_ops():
    """Retorna todas as OPs para impressão"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    ops = OrdemProducao.query.order_by(OrdemProducao.op).all()
    
    ops_list = []
    for op in ops:
        ops_list.append({
            'op': op.op,
            'produto': op.produto,
            'qtde_carregado': float(op.qtde_carregado),
            'qtde_produzida': float(op.qtde_produzida),
            'unidade_medida': op.unidade_medida,
            'status_op': op.status_op
        })
    
    return jsonify(ops_list)

@app.route('/api/admin/add_maquina', methods=['POST'])
def admin_add_maquina():
    """Adiciona nova máquina"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    try:
        data = request.json
        
        nova_maquina = Maquina(
            codigo_qr=data['codigo_qr'],
            codigo=data['codigo'],
            nome=data['nome'],
            setor=data['setor'],
            tipo_maquina=data.get('tipo_maquina', ''),
            status=data.get('status', 'parada')
        )
        
        db.session.add(nova_maquina)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Máquina adicionada com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@app.route('/api/admin/add_usuario', methods=['POST'])
def admin_add_usuario():
    """Adiciona novo usuário"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    try:
        data = request.json
        
        novo_usuario = Usuario(
            codigo_qr=data['codigo_qr'],
            nome=data['nome'],
            tipo=data['tipo'],
            setor=data.get('setor', ''),
            ativo=data.get('ativo', True)
        )
        
        db.session.add(novo_usuario)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Usuário adicionado com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@app.route('/api/admin/add_motivo', methods=['POST'])
def admin_add_motivo():
    """Adiciona novo motivo de parada"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    try:
        data = request.json
        
        novo_motivo = MotivoParada(
            codigo=data['codigo'],
            descricao=data['descricao'],
            categoria=data['categoria'],
            cor=data['cor'],
            ordem_exibicao=data.get('ordem_exibicao', 0),
            requer_justificativa=data.get('requer_justificativa', False),
            ativo=data.get('ativo', True)
        )
        
        db.session.add(novo_motivo)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Motivo adicionado com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@app.route('/api/generate_qr')
def generate_qr():
    """Gera QR Code para visualização"""
    text = request.args.get('text', '')
    if not text:
        return jsonify({'error': 'Texto necessário'}), 400
    
    qr_code = generate_qr_code(text)
    return jsonify({'qr_code': qr_code})

@app.route('/api/generate_op_qr/<int:op_number>')
def generate_op_qr(op_number):
    """Gera QR Code para uma OP específica"""
    qr_code = generate_qr_code(f"OP{op_number}")
    # Converter base64 para imagem
    import base64
    qr_data = qr_code.split(',')[1]
    qr_bytes = base64.b64decode(qr_data)
    
    from flask import make_response
    response = make_response(qr_bytes)
    response.headers.set('Content-Type', 'image/png')
    response.headers.set('Content-Disposition', 'inline', filename=f'op_{op_number}_qr.png')
    return response

# ========== API SYNC ROUTES ==========

@app.route('/api/sync/ops', methods=['POST'])
def sync_ops():
    """Sincroniza OPs com API externa"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    try:
        client = SystextilAPIClient()
        result = client.sync_orders_to_database()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro na sincronização: {str(e)}'
        })

@app.route('/api/sync/test_connection', methods=['GET'])
def test_api_connection():
    """Testa conexão com API externa"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    try:
        client = SystextilAPIClient()
        client._get_access_token()
        
        return jsonify({
            'success': True,
            'message': 'Conexão com API estabelecida com sucesso!',
            'token_expiry': client.token_expiry.isoformat() if client.token_expiry else None
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Falha na conexão com API: {str(e)}'
        })

@app.route('/api/sync/logs')
def get_sync_logs():
    """Retorna logs de sincronização"""
    if session.get('usuario_tipo') != 'admin':
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    logs = LogSincronizacao.query.order_by(LogSincronizacao.data_execucao.desc()).limit(50).all()
    
    logs_list = []
    for log in logs:
        logs_list.append({
            'id': log.id,
            'tipo': log.tipo,
            'data_execucao': log.data_execucao.isoformat() if log.data_execucao else None,
            'registros_processados': log.registros_processados,
            'registros_novos': log.registros_novos,
            'registros_atualizados': log.registros_atualizados,
            'duracao_segundos': log.duracao_segundos,
            'status': log.status,
            'mensagem': log.mensagem
        })
    
    return jsonify(logs_list)

@app.route('/admin/op/<int:op_id>/print')
def print_op(op_id):
    """Página para impressão de uma OP específica"""
    if session.get('usuario_tipo') != 'admin':
        return redirect('/')
    
    op = OrdemProducao.query.get(op_id)
    if not op:
        return "OP não encontrada", 404
    
    # Gerar QR Code
    qr_code = generate_qr_code(f"OP{op.op}")
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>OP {op.op} - Impressão</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                padding: 20px;
                max-width: 800px;
                margin: 0 auto;
            }}
            .print-header {{
                text-align: center;
                margin-bottom: 30px;
                border-bottom: 2px solid #333;
                padding-bottom: 20px;
            }}
            .company-info {{
                margin-bottom: 20px;
            }}
            .op-info {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 30px;
            }}
            .info-box {{
                border: 1px solid #ddd;
                padding: 15px;
                border-radius: 5px;
            }}
            .qr-container {{
                text-align: center;
                margin: 20px 0;
            }}
            .status-badge {{
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-weight: bold;
                margin-top: 10px;
            }}
            .status-pendente {{ background: #fff3cd; color: #856404; }}
            .status-em_andamento {{ background: #d1ecf1; color: #0c5460; }}
            .status-finalizada {{ background: #d4edda; color: #155724; }}
            .status-pausado {{ background: #f8d7da; color: #721c24; }}
            
            @media print {{
                body {{ padding: 0; }}
                .no-print {{ display: none; }}
                .print-header {{ border-bottom: 2px solid #000; }}
            }}
        </style>
    </head>
    <body>
        <div class="print-header">
            <div class="company-info">
                <h1>LEAN PRODUCTION SYSTEM</h1>
                <h2>ORDEM DE PRODUÇÃO</h2>
            </div>
            
            <div class="qr-container">
                <img src="{qr_code}" alt="QR Code OP {op.op}" width="150">
                <h3>OP {op.op}</h3>
            </div>
            
            <div class="status-badge status-{op.status_op}">
                {op.status_op.upper()}
            </div>
        </div>
        
        <div class="op-info">
            <div class="info-box">
                <h4>Informações da OP</h4>
                <p><strong>Produto:</strong> {op.produto}</p>
                <p><strong>Descrição:</strong> {op.narrativa}</p>
                <p><strong>Grupo:</strong> {op.grupo or 'N/A'}</p>
                <p><strong>Unidade:</strong> {op.unidade_medida}</p>
            </div>
            
            <div class="info-box">
                <h4>Quantidades</h4>
                <p><strong>Programado:</strong> {op.qtde_programado} {op.unidade_medida}</p>
                <p><strong>Carregado:</strong> {op.qtde_carregado} {op.unidade_medida}</p>
                <p><strong>Produzido:</strong> {op.qtde_produzida} {op.unidade_medida}</p>
                <p><strong>Disponível:</strong> {op.qtde_carregado - op.qtde_produzida} {op.unidade_medida}</p>
            </div>
        </div>
        
        <div class="op-info">
            <div class="info-box">
                <h4>Status e Localização</h4>
                <p><strong>Estágio Atual:</strong> {op.estagio_atual or 'N/A'}</p>
                <p><strong>Posição:</strong> {op.estagio_posicao or 'N/A'}</p>
                <p><strong>Data Início:</strong> {op.data_inicio.strftime('%d/%m/%Y') if op.data_inicio else 'N/A'}</p>
                <p><strong>Data Término:</strong> {op.data_termino.strftime('%d/%m/%Y') if op.data_termino else 'N/A'}</p>
            </div>
            
            <div class="info-box">
                <h4>Informações Técnicas</h4>
                <p><strong>Código QR:</strong> OP{op.op}</p>
                <p><strong>ID no Sistema:</strong> {op.id}</p>
                <p><strong>Data de Criação:</strong> {op.data_importacao.strftime('%d/%m/%Y') if op.data_importacao else 'N/A'}</p>
                <p><strong>Última Atualização:</strong> {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}</p>
            </div>
        </div>
        
        <div class="no-print" style="margin-top: 40px; text-align: center;">
            <button onclick="window.print()" style="padding: 10px 20px; font-size: 16px;">
                🖨️ Imprimir
            </button>
            <button onclick="window.close()" style="padding: 10px 20px; font-size: 16px; margin-left: 10px;">
                ❌ Fechar
            </button>
        </div>
        
        <script>
            window.onload = function() {{
                // Auto-print em alguns casos
                const urlParams = new URLSearchParams(window.location.search);
                if (urlParams.get('auto') === 'true') {{
                    window.print();
                    setTimeout(function() {{
                        window.close();
                    }}, 1000);
                }}
            }};
        </script>
    </body>
    </html>
    """

# ========== INICIALIZAÇÃO ==========

if __name__ == '__main__':
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)