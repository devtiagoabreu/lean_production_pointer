# test_api.py

import requests
import base64
import json
from datetime import datetime

# Configurações
TOKEN_URL = "https://promoda.systextil.com.br/apexbd/erp/oauth/token"
CLIENT_ID = "vM_z3JIQSR7fMml912X4Wg.."
CLIENT_SECRET = "v6CnE7I6vI6JkYn7DOIQ6A.."
API_URL = "https://promoda.systextil.com.br/apexbd/erp/systextil-intg-plm/api_pcp_ops"

def get_access_token():
    """Obtém token OAuth2"""
    auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_encoded = base64.b64encode(auth_string.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {auth_encoded}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'grant_type': 'client_credentials'
    }
    
    try:
        response = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
        
        if response.status_code == 200:
            token_data = response.json()
            print("✅ Token obtido com sucesso!")
            return token_data['access_token']
        else:
            print(f"❌ Erro ao obter token: {response.status_code}")
            print(f"Resposta: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Erro de conexão: {str(e)}")
        return None

def test_api_connection(access_token):
    """Testa a conexão com a API de OPs"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(API_URL, headers=headers, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Conexão com API bem-sucedida!")
            print(f"Total de OPs recebidas: {len(data.get('items', []))}")
            
            # Mostrar algumas OPs de exemplo
            if data.get('items'):
                print("\n📋 Exemplo de OPs recebidas:")
                for i, item in enumerate(data['items'][:3]):  # Mostrar apenas 3
                    print(f"\nOP {item.get('OP', 'N/A')}:")
                    print(f"  Produto: {item.get('PRODUTO', 'N/A')}")
                    print(f"  Descrição: {item.get('NARRATIVA', 'N/A')}")
                    print(f"  Qtde Carregada: {item.get('QTDE_CARREGADO', 0)}")
                    print(f"  Qtde Produzida: {item.get('QTDE_PRODUZIDA', 0)}")
                    print(f"  Estágio: {item.get('ESTAGIO', 'N/A')}")
                    print(f"  Estágio Posição: {item.get('ESTAGIO_POSICAO', 'N/A')}")
                    print(f"  Máquina: {item.get('MAQUINA_OP', 'N/A')}")
            
            return True
        else:
            print(f"❌ Erro na API: {response.status_code}")
            print(f"Resposta: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erro de conexão com API: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔧 Testando conexão com API Systêxtil...")
    print(f"Token URL: {TOKEN_URL}")
    print(f"API URL: {API_URL}")
    
    # Obter token
    token = get_access_token()
    
    if token:
        # Testar conexão com a API
        test_api_connection(token)
    else:
        print("❌ Não foi possível obter token de acesso")