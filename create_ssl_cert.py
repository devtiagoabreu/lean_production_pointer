import os
import subprocess
from datetime import datetime, timedelta

def create_ssl_certificate():
    """Cria certificado SSL autoassinado para desenvolvimento"""
    
    # Verificar se openssl está instalado
    try:
        subprocess.run(['openssl', 'version'], capture_output=True, check=True)
    except:
        print("❌ OpenSSL não está instalado. Instale primeiro.")
        print("No Ubuntu/Debian: sudo apt-get install openssl")
        print("No macOS: brew install openssl")
        print("No Windows: Baixe do https://slproweb.com/products/Win32OpenSSL.html")
        return False
    
    # Criar diretório para certificados
    cert_dir = 'ssl_certs'
    os.makedirs(cert_dir, exist_ok=True)
    
    # Criar chave privada
    key_path = os.path.join(cert_dir, 'server.key')
    subprocess.run([
        'openssl', 'genrsa', '-out', key_path, '2048'
    ], check=True)
    
    # Criar certificado autoassinado
    cert_path = os.path.join(cert_dir, 'server.crt')
    subprocess.run([
        'openssl', 'req', '-new', '-x509',
        '-key', key_path,
        '-out', cert_path,
        '-days', '365',
        '-subj', '/C=BR/ST=Sao_Paulo/L=Sao_Paulo/O=Company/CN=localhost'
    ], check=True)
    
    print(f"✅ Certificado SSL criado em {cert_dir}/")
    print(f"   Chave privada: {key_path}")
    print(f"   Certificado: {cert_path}")
    return True

if __name__ == '__main__':
    create_ssl_certificate()