# start_easy.py

#!/usr/bin/env python3
"""
🚀 INICIAR TUDO AUTOMATICAMENTE - Versão Simplificada
"""

import subprocess
import threading
import time
import os
import webbrowser
import sys

def print_banner():
    print("="*60)
    print("📱 LEAN PRODUCTION POINTER - PRONTO PARA CELULAR!")
    print("="*60)

def start_flask():
    """Inicia o servidor Flask"""
    print("\n🎯 Iniciando servidor Flask na porta 5000...")
    os.system("python app.py")

def start_ngrok():
    """Inicia ngrok apontando para porta 5000"""
    print("\n🌐 Iniciando ngrok...")
    print("💡 Aguarde alguns segundos para obter a URL...")
    
    # Iniciar ngrok
    process = subprocess.Popen(
        ["ngrok", "http", "5000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # Aguardar e capturar URL
    time.sleep(5)
    
    url = None
    for i in range(10):  # Tentar por 20 segundos
        try:
            import requests
            response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
            data = response.json()
            
            for tunnel in data.get("tunnels", []):
                if tunnel.get("proto") == "https":
                    url = tunnel.get("public_url")
                    if url:
                        break
            
            if url:
                break
        except:
            pass
        
        time.sleep(2)
        print(".", end="", flush=True)
    
    return process, url

def main():
    print_banner()
    
    print("\n⚡ Iniciando todos os serviços...")
    
    # Iniciar Flask em thread separada
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    
    # Aguardar Flask iniciar
    time.sleep(3)
    
    # Iniciar ngrok
    ngrok_process, ngrok_url = start_ngrok()
    
    if ngrok_url:
        print("\n" + "="*60)
        print("✅ URL PRONTA PARA CELULAR!")
        print("="*60)
        print(f"\n📱 ACESSE:")
        print(f"🔗 {ngrok_url}")
        print("\n💡 A câmera funcionará perfeitamente!")
        
        # Copiar para área de transferência
        try:
            import pyperclip
            pyperclip.copy(ngrok_url)
            print("📋 URL copiada para área de transferência!")
        except:
            pass
        
        # Abrir no navegador
        webbrowser.open(ngrok_url)
        
        # Gerar QR code
        try:
            import qrcode
            qr = qrcode.QRCode()
            qr.add_data(ngrok_url)
            qr.make()
            img = qr.make_image(fill_color="black", back_color="white")
            img.save("celular_qr.png")
            print("📱 QR Code salvo como: celular_qr.png")
        except:
            print("💡 Instale: pip install qrcode[pil] para QR Code")
    
    else:
        print("\n⚠️  Não consegui obter URL automaticamente.")
        print("\n💡 FAÇA MANUALMENTE:")
        print("1. Certifique-se que o Flask está rodando")
        print("2. Abra OUTRO terminal PowerShell")
        print("3. Execute: ngrok http 5000")
        print("4. Use a URL que aparecer no celular")
    
    print("\n" + "="*60)
    print("⚙️  Serviços ativos:")
    print("   • Flask: http://localhost:5000")
    print("   • Ngrok: http://localhost:4040")
    if ngrok_url:
        print(f"   • Celular: {ngrok_url}")
    print("\n⏸️  Pressione Ctrl+C para parar tudo")
    print("="*60)
    
    # Manter rodando
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Encerrando serviços...")
        if ngrok_process:
            ngrok_process.terminate()

if __name__ == "__main__":
    main()